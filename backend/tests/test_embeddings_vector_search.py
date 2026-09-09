"""Automated test suite for Embedding Generation & MongoDB Atlas Vector Search (Phase 10)."""

import unittest
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.config import get_settings
from app.core.embeddings import EmbeddingGenerator, cosine_similarity
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.chunk import ChunkInDB
from app.models.course import CourseInDB, Subtopic, Topic, Unit
from app.models.material import MaterialInDB, ProcessingStatus, SourceType
from app.models.teaching_question import DifficultyLevel, ExamType, TeachingQuestionInDB
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository


class InMemoryCoursesCollection:
    """Mock in-memory collection simulating MongoDB courses collection."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def insert_one(self, doc: Dict[str, Any]) -> Any:
        code = doc.get("course_code")
        doc_copy = dict(doc)
        _id = ObjectId()
        doc_copy["_id"] = _id
        self.docs[code] = doc_copy

        class InsertResult:
            def __init__(self, inserted_id: ObjectId):
                self.inserted_id = inserted_id

        return InsertResult(_id)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        code = query.get("course_code")
        if code in self.docs:
            return dict(self.docs[code])
        return None

    def find(self, query: Dict[str, Any] = None) -> Any:
        items = [dict(d) for d in self.docs.values()]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = items

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, ""), reverse=(direction == -1))
                return self

            def limit(self, count: int) -> Any:
                self.items = self.items[:count]
                return self

            def __iter__(self) -> Any:
                return iter(self.items)

        return Cursor(items)


class InMemoryMaterialsCollection:
    """Mock in-memory collection simulating MongoDB materials collection."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def insert_one(self, doc: Dict[str, Any]) -> Any:
        doc_copy = dict(doc)
        _id = ObjectId()
        doc_copy["_id"] = _id
        id_str = str(_id)
        self.docs[id_str] = doc_copy

        class InsertResult:
            def __init__(self, inserted_id: ObjectId):
                self.inserted_id = inserted_id

        return InsertResult(_id)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "_id" in query:
            _id = query["_id"]
            for d in self.docs.values():
                if d.get("_id") == _id:
                    return dict(d)
        if "course_code" in query and "original_filename" in query:
            code = query["course_code"]
            fn = query["original_filename"]
            for d in self.docs.values():
                if d.get("course_code") == code and d.get("original_filename") == fn:
                    return dict(d)
        return None


class InMemoryChunksCollection:
    """Mock in-memory collection simulating MongoDB chunks collection."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def insert_many(self, docs: List[Dict[str, Any]]) -> Any:
        inserted_ids = []
        for doc in docs:
            doc_copy = dict(doc)
            _id = ObjectId()
            doc_copy["_id"] = _id
            self.docs[str(_id)] = doc_copy
            inserted_ids.append(_id)

        class InsertManyResult:
            def __init__(self, ids: List[ObjectId]):
                self.inserted_ids = ids

        return InsertManyResult(inserted_ids)

    def find(self, query: Dict[str, Any] = None) -> Any:
        query = query or {}
        results = []
        for d in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "embedding" and isinstance(v, dict):
                    if "$ne" in v:
                        if v["$ne"] is None and d.get("embedding") is None:
                            match = False
                            break
                        elif d.get("embedding") == v["$ne"]:
                            match = False
                            break
                elif k in d:
                    if d[k] != v:
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                results.append(dict(d))

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = items

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, 0) or 0, reverse=(direction == -1))
                return self

            def limit(self, count: int) -> Any:
                self.items = self.items[:count]
                return self

            def __iter__(self) -> Any:
                return iter(self.items)

        return Cursor(results)

    def count_documents(self, query: Dict[str, Any]) -> int:
        return len(list(self.find(query)))

    def update_one(self, filter_doc: Dict[str, Any], update_doc: Dict[str, Any]) -> Any:
        matched = 0
        modified = 0
        if "_id" in filter_doc:
            target_id = str(filter_doc["_id"])
            if target_id in self.docs:
                matched = 1
                if "$set" in update_doc:
                    for k, v in update_doc["$set"].items():
                        self.docs[target_id][k] = v
                    modified = 1

        class UpdateResult:
            def __init__(self, matched_count: int, modified_count: int):
                self.matched_count = matched_count
                self.modified_count = modified_count

        return UpdateResult(matched, modified)

    def bulk_write(self, operations: List[Any], ordered: bool = False) -> Any:
        modified_count = 0
        for op in operations:
            filter_doc = getattr(op, "_filter", {})
            doc_update = getattr(op, "_doc", {})
            if "_id" in filter_doc:
                target_id = str(filter_doc["_id"])
                if target_id in self.docs:
                    if "$set" in doc_update:
                        for k, v in doc_update["$set"].items():
                            self.docs[target_id][k] = v
                        modified_count += 1

        class BulkWriteResult:
            def __init__(self, count: int):
                self.modified_count = count

        return BulkWriteResult(modified_count)

    def delete_many(self, query: Dict[str, Any]) -> Any:
        to_delete = []
        for k_id, d in self.docs.items():
            match = True
            for k, v in query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                to_delete.append(k_id)

        for k_id in to_delete:
            del self.docs[k_id]

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(len(to_delete))


class InMemoryTeachingQuestionsCollection:
    """Mock in-memory collection simulating MongoDB teaching_questions collection."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def insert_many(self, docs: List[Dict[str, Any]]) -> Any:
        inserted_ids = []
        for doc in docs:
            doc_copy = dict(doc)
            _id = ObjectId()
            doc_copy["_id"] = _id
            self.docs[str(_id)] = doc_copy
            inserted_ids.append(_id)

        class InsertManyResult:
            def __init__(self, ids: List[ObjectId]):
                self.inserted_ids = ids

        return InsertManyResult(inserted_ids)

    def find(self, query: Dict[str, Any] = None) -> Any:
        query = query or {}
        results = []
        for d in self.docs.values():
            match = True
            for k, v in query.items():
                if k == "embedding" and isinstance(v, dict):
                    if "$ne" in v:
                        if v["$ne"] is None and d.get("embedding") is None:
                            match = False
                            break
                        elif d.get("embedding") == v["$ne"]:
                            match = False
                            break
                elif k in d:
                    if d[k] != v:
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                results.append(dict(d))

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = items

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, 0) or 0, reverse=(direction == -1))
                return self

            def limit(self, count: int) -> Any:
                self.items = self.items[:count]
                return self

            def __iter__(self) -> Any:
                return iter(self.items)

        return Cursor(results)

    def count_documents(self, query: Dict[str, Any]) -> int:
        return len(list(self.find(query)))

    def update_one(self, filter_doc: Dict[str, Any], update_doc: Dict[str, Any]) -> Any:
        matched = 0
        modified = 0
        if "_id" in filter_doc:
            target_id = str(filter_doc["_id"])
            if target_id in self.docs:
                matched = 1
                if "$set" in update_doc:
                    for k, v in update_doc["$set"].items():
                        self.docs[target_id][k] = v
                    modified = 1

        class UpdateResult:
            def __init__(self, matched_count: int, modified_count: int):
                self.matched_count = matched_count
                self.modified_count = modified_count

        return UpdateResult(matched, modified)

    def bulk_write(self, operations: List[Any], ordered: bool = False) -> Any:
        modified_count = 0
        for op in operations:
            filter_doc = getattr(op, "_filter", {})
            doc_update = getattr(op, "_doc", {})
            if "_id" in filter_doc:
                target_id = str(filter_doc["_id"])
                if target_id in self.docs:
                    if "$set" in doc_update:
                        for k, v in doc_update["$set"].items():
                            self.docs[target_id][k] = v
                        modified_count += 1

        class BulkWriteResult:
            def __init__(self, count: int):
                self.modified_count = count

        return BulkWriteResult(modified_count)

    def delete_many(self, query: Dict[str, Any]) -> Any:
        to_delete = []
        for k_id, d in self.docs.items():
            match = True
            for k, v in query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                to_delete.append(k_id)

        for k_id in to_delete:
            del self.docs[k_id]

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(len(to_delete))


class TestEmbeddingAndVectorSearch(unittest.TestCase):
    """Test suite for Phase 10: Embedding Generation & MongoDB Atlas Vector Search."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.test_username = "embed_admin"
        cls.test_password = "EmbeddingTestPassword123!"
        cls.admin_hash = hash_password(cls.test_password)

        settings = get_settings()
        settings.ADMIN_USERNAME = cls.test_username
        settings.ADMIN_PASSWORD_HASH = cls.admin_hash

        cls.valid_token = create_access_token(subject=cls.test_username, role="developer")
        cls.auth_headers = {"Authorization": f"Bearer {cls.valid_token}"}
        cls.client = TestClient(app)

    def setUp(self) -> None:
        self.mock_courses = InMemoryCoursesCollection()
        self.mock_materials = InMemoryMaterialsCollection()
        self.mock_chunks = InMemoryChunksCollection()
        self.mock_teaching_questions = InMemoryTeachingQuestionsCollection()

        self.courses_patch = patch("app.repositories.course_repository.get_courses_collection", return_value=self.mock_courses)
        self.materials_patch = patch("app.repositories.material_repository.get_materials_collection", return_value=self.mock_materials)
        self.chunks_patch = patch("app.repositories.chunk_repository.get_chunks_collection", return_value=self.mock_chunks)
        self.tq_patch = patch("app.repositories.teaching_question_repository.get_teaching_questions_collection", return_value=self.mock_teaching_questions)

        self.courses_patch.start()
        self.materials_patch.start()
        self.chunks_patch.start()
        self.tq_patch.start()

        # Deterministic mock embedding generator: produces 384-dim normalized unit vectors
        self.mock_generator = MagicMock()

        def _mock_gen(text: str) -> List[float]:
            vec = [0.0] * 384
            if "b-tree" in text.lower() or "indexing" in text.lower():
                vec[0] = 1.0
            elif "acid" in text.lower() or "transaction" in text.lower():
                vec[1] = 1.0
            else:
                val = float(abs(hash(text)) % 1000 + 1) / 1000.0
                vec[2] = val
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            return [x / norm for x in vec]

        def _mock_gen_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
            return [_mock_gen(t) for t in texts]

        self.mock_generator.generate_embedding.side_effect = _mock_gen
        self.mock_generator.generate_embeddings_batch.side_effect = _mock_gen_batch
        self.mock_generator.dimension = 384
        self.mock_generator.embedding_dimension = 384
        self.mock_generator.model_name = "all-MiniLM-L6-v2"

        self.gen_patch = patch("app.core.embeddings.EmbeddingGenerator.get_instance", return_value=self.mock_generator)
        self.gen_patch.start()

    def tearDown(self) -> None:
        self.gen_patch.stop()
        self.tq_patch.stop()
        self.chunks_patch.stop()
        self.materials_patch.stop()
        self.courses_patch.stop()

    def _seed_course(self, course_code: str = "CSE3002") -> None:
        course_doc = {
            "course_code": course_code,
            "course_name": "Database Management Systems",
            "description": "Core DBMS course",
            "units": [
                {
                    "id": f"{course_code}_U1",
                    "unit_number": 1,
                    "unit_name": "Storage and Indexing",
                    "topics": [
                        {
                            "id": f"{course_code}_U1_T1",
                            "topic_name": "B-Tree Indexing",
                            "subtopics": [
                                {"id": f"{course_code}_U1_T1_S1", "title": "B+ Tree Insertion"}
                            ]
                        }
                    ]
                },
                {
                    "id": f"{course_code}_U2",
                    "unit_number": 2,
                    "unit_name": "Transaction Processing",
                    "topics": [
                        {
                            "id": f"{course_code}_U2_T1",
                            "topic_name": "ACID Properties",
                            "subtopics": []
                        }
                    ]
                }
            ]
        }
        self.mock_courses.insert_one(course_doc)

    def _seed_lecture_material(self, course_code: str = "CSE3002") -> str:
        mat_doc = {
            "course_code": course_code,
            "original_filename": "lecture_indexing.pdf",
            "stored_filename": "stored_indexing.pdf",
            "storage_path": "/storage/lecture_indexing.pdf",
            "file_type": "pdf",
            "source_type": "lecture_material",
            "processing_status": "processed",
        }
        res = self.mock_materials.insert_one(mat_doc)
        return str(res.inserted_id)

    def _seed_exam_material(self, course_code: str = "CSE3002") -> str:
        mat_doc = {
            "course_code": course_code,
            "original_filename": "cat1_2023.pdf",
            "stored_filename": "stored_cat1.pdf",
            "storage_path": "/storage/cat1_2023.pdf",
            "file_type": "pdf",
            "source_type": "exam_paper",
            "exam_type": "CAT1",
            "year": 2023,
            "processing_status": "processed",
        }
        res = self.mock_materials.insert_one(mat_doc)
        return str(res.inserted_id)

    def _seed_chunks(self, material_id: str, course_code: str = "CSE3002") -> List[str]:
        chunks = [
            {
                "course_code": course_code,
                "unit": 1,
                "unit_id": f"{course_code}_U1",
                "topic": "B-Tree Indexing",
                "topic_id": f"{course_code}_U1_T1",
                "subtopic": "B+ Tree Insertion",
                "subtopic_id": f"{course_code}_U1_T1_S1",
                "source_type": "lecture_material",
                "material_id": material_id,
                "page_number": 1,
                "scope_status": "in_syllabus",
                "chunk_type": "passage",
                "text": "B-Tree Indexing provides balanced search trees for fast data retrieval.",
                "char_count": 68,
                "token_count": 12,
                "chunk_index": 0,
                "embedding": None,
            },
            {
                "course_code": course_code,
                "unit": 2,
                "unit_id": f"{course_code}_U2",
                "topic": "ACID Properties",
                "topic_id": f"{course_code}_U2_T1",
                "subtopic": None,
                "subtopic_id": None,
                "source_type": "lecture_material",
                "material_id": material_id,
                "page_number": 2,
                "scope_status": "in_syllabus",
                "chunk_type": "passage",
                "text": "ACID properties guarantee that database transactions are processed reliably.",
                "char_count": 75,
                "token_count": 11,
                "chunk_index": 1,
                "embedding": None,
            }
        ]
        res = self.mock_chunks.insert_many(chunks)
        return [str(i) for i in res.inserted_ids]

    def _seed_teaching_questions(self, material_id: str, course_code: str = "CSE3002") -> List[str]:
        questions = [
            {
                "course_code": course_code,
                "source_material_id": material_id,
                "question_number": "1a",
                "question_text": "Explain B-Tree Indexing insertion algorithm with an example.",
                "marks": 5,
                "exam_type": "CAT1",
                "year": 2023,
                "unit": 1,
                "unit_id": f"{course_code}_U1",
                "topic": "B-Tree Indexing",
                "topic_id": f"{course_code}_U1_T1",
                "subtopic": None,
                "subtopic_id": None,
                "question_type": "theoretical",
                "difficulty": "medium",
                "page_number": 1,
                "embedding": None,
            },
            {
                "course_code": course_code,
                "source_material_id": material_id,
                "question_number": "2",
                "question_text": "Demonstrate ACID property violations during concurrent transaction execution.",
                "marks": 10,
                "exam_type": "CAT1",
                "year": 2023,
                "unit": 2,
                "unit_id": f"{course_code}_U2",
                "topic": "ACID Properties",
                "topic_id": f"{course_code}_U2_T1",
                "subtopic": None,
                "subtopic_id": None,
                "question_type": "scenario",
                "difficulty": "hard",
                "page_number": 1,
                "embedding": None,
            }
        ]
        res = self.mock_teaching_questions.insert_many(questions)
        return [str(i) for i in res.inserted_ids]

    # --- Test Cases ---

    def test_1_unauthenticated_requests_rejected(self) -> None:
        """Verify that all developer embedding endpoints reject unauthenticated requests with 401."""
        dummy_id = str(ObjectId())
        res1 = self.client.post(f"/dev/materials/{dummy_id}/generate-embeddings")
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.post("/dev/courses/CSE3002/generate-embeddings")
        self.assertEqual(res2.status_code, 401)

        res3 = self.client.get("/dev/embeddings/status")
        self.assertEqual(res3.status_code, 401)

        res4 = self.client.post("/dev/vector-search", json={"query": "test query", "course_code": "CSE3002"})
        self.assertEqual(res4.status_code, 401)

    def test_2_generate_embeddings_material_not_found(self) -> None:
        """Verify 404 is returned when attempting to generate embeddings for non-existent material."""
        dummy_id = str(ObjectId())
        response = self.client.post(
            f"/dev/materials/{dummy_id}/generate-embeddings",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_3_generate_embeddings_lecture_material_success(self) -> None:
        """Verify successful embedding generation for course content chunks."""
        self._seed_course("CSE3002")
        mat_id = self._seed_lecture_material("CSE3002")
        self._seed_chunks(mat_id, "CSE3002")

        response = self.client.post(
            f"/dev/materials/{mat_id}/generate-embeddings",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["material_id"], mat_id)
        self.assertEqual(data["course_code"], "CSE3002")
        self.assertEqual(data["source_type"], "lecture_material")
        self.assertEqual(data["embedded_count"], 2)
        self.assertEqual(data["dimension"], 384)

        # Verify chunks in repository have embedding vectors
        chunks = ChunkRepository.get_chunks_by_material(mat_id)
        self.assertEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertIsNotNone(chunk.embedding)
            self.assertEqual(len(chunk.embedding), 384)

    def test_4_generate_embeddings_exam_paper_success(self) -> None:
        """Verify successful embedding generation for teaching questions from exam papers."""
        self._seed_course("CSE3002")
        mat_id = self._seed_exam_material("CSE3002")
        self._seed_teaching_questions(mat_id, "CSE3002")

        response = self.client.post(
            f"/dev/materials/{mat_id}/generate-embeddings",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["material_id"], mat_id)
        self.assertEqual(data["course_code"], "CSE3002")
        self.assertEqual(data["source_type"], "exam_paper")
        self.assertEqual(data["embedded_count"], 2)
        self.assertEqual(data["dimension"], 384)

        # Verify teaching questions in repository have embedding vectors
        questions = TeachingQuestionRepository.get_questions_by_material(mat_id)
        self.assertEqual(len(questions), 2)
        for q in questions:
            self.assertIsNotNone(q.embedding)
            self.assertEqual(len(q.embedding), 384)

    def test_5_generate_embeddings_no_records_returns_400(self) -> None:
        """Verify 400 Bad Request when a material exists but has no chunks or questions extracted."""
        self._seed_course("CSE3002")
        mat_id = self._seed_lecture_material("CSE3002")
        # Do not seed chunks

        response = self.client.post(
            f"/dev/materials/{mat_id}/generate-embeddings",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("no prepared chunks", response.json()["detail"].lower())

    def test_6_bulk_generate_course_embeddings(self) -> None:
        """Verify bulk embedding generation across all chunks and exam questions for a course."""
        self._seed_course("CSE3002")
        mat1 = self._seed_lecture_material("CSE3002")
        self._seed_chunks(mat1, "CSE3002")
        mat2 = self._seed_exam_material("CSE3002")
        self._seed_teaching_questions(mat2, "CSE3002")

        response = self.client.post(
            "/dev/courses/CSE3002/generate-embeddings",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["course_code"], "CSE3002")
        self.assertEqual(data["chunks_embedded"], 2)
        self.assertEqual(data["questions_embedded"], 2)
        self.assertEqual(data["total_embedded"], 4)

    def test_7_bulk_generate_course_not_found(self) -> None:
        """Verify 404 when bulk generating embeddings for non-existent course."""
        response = self.client.post(
            "/dev/courses/NONEXISTENT/generate-embeddings",
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_8_embedding_status_reporting(self) -> None:
        """Verify coverage and embedding status reporting."""
        self._seed_course("CSE3002")
        mat1 = self._seed_lecture_material("CSE3002")
        self._seed_chunks(mat1, "CSE3002")  # 2 chunks without embedding

        # Check status before embedding
        res1 = self.client.get("/dev/embeddings/status?course_code=CSE3002", headers=self.auth_headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["total_chunks"], 2)
        self.assertEqual(data1["chunks_with_embeddings"], 0)
        self.assertFalse(data1["is_fully_embedded"])

        # Generate embeddings
        self.client.post(f"/dev/materials/{mat1}/generate-embeddings", headers=self.auth_headers)

        # Check status after embedding
        res2 = self.client.get("/dev/embeddings/status?course_code=CSE3002", headers=self.auth_headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["total_chunks"], 2)
        self.assertEqual(data2["chunks_with_embeddings"], 2)
        self.assertTrue(data2["is_fully_embedded"])
        self.assertIn("all-MiniLM-L6-v2", data2["model_name"])
        self.assertEqual(data2["dimension"], 384)

    def test_9_vector_search_chunks_with_metadata_filters(self) -> None:
        """Verify vector search on course content chunks with unit metadata filtering."""
        self._seed_course("CSE3002")
        mat1 = self._seed_lecture_material("CSE3002")
        self._seed_chunks(mat1, "CSE3002")

        # Generate embeddings
        self.client.post(f"/dev/materials/{mat1}/generate-embeddings", headers=self.auth_headers)

        # Search for B-Tree indexing in Unit 1
        search_payload = {
            "query": "B-Tree Indexing concepts and operations",
            "course_code": "CSE3002",
            "target": "course_content",
            "unit_id": "CSE3002_U1",
            "limit": 5,
        }
        response = self.client.post(
            "/dev/vector-search",
            json=search_payload,
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["course_code"], "CSE3002")
        self.assertEqual(data["target"], "course_content")
        self.assertGreaterEqual(data["total_results"], 1)
        # Top result should be in Unit 1 with positive score
        self.assertEqual(data["results"][0]["unit_id"], "CSE3002_U1")
        self.assertGreater(data["results"][0]["score"], 0.0)

    def test_10_vector_search_teaching_questions_with_exam_type(self) -> None:
        """Verify vector search on teaching questions with exam_type filter."""
        self._seed_course("CSE3002")
        mat1 = self._seed_exam_material("CSE3002")
        self._seed_teaching_questions(mat1, "CSE3002")

        # Generate embeddings
        self.client.post(f"/dev/materials/{mat1}/generate-embeddings", headers=self.auth_headers)

        search_payload = {
            "query": "Explain transaction ACID properties",
            "course_code": "CSE3002",
            "target": "teaching_questions",
            "exam_type": "CAT1",
            "limit": 5,
        }
        response = self.client.post(
            "/dev/vector-search",
            json=search_payload,
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target"], "teaching_questions")
        self.assertGreaterEqual(data["total_results"], 1)
        for result in data["results"]:
            self.assertEqual(result["exam_type"], "CAT1")
        self.assertGreater(data["results"][0]["score"], 0.0)

    def test_11_vector_search_course_not_found(self) -> None:
        """Verify 404 when executing vector search on non-existent course."""
        search_payload = {
            "query": "B-Tree Indexing",
            "course_code": "NONEXISTENT",
            "target": "course_content",
        }
        response = self.client.post(
            "/dev/vector-search",
            json=search_payload,
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_12_cosine_similarity_math(self) -> None:
        """Verify math correctness of cosine_similarity function."""
        # Identical vectors -> 1.0
        v1 = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v1), 1.0, places=5)

        # Orthogonal vectors -> 0.0
        v2 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v2), 0.0, places=5)

        # Opposite vectors -> -1.0
        v3 = [-1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v3), -1.0, places=5)

        # Zero vector -> 0.0
        v_zero = [0.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v_zero), 0.0, places=5)

        # Arbitrary vectors
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        expected = 32.0 / ((14.0 ** 0.5) * (77.0 ** 0.5))
        self.assertAlmostEqual(cosine_similarity(a, b), expected, places=5)


if __name__ == "__main__":
    unittest.main()
