"""Automated test suite for RAG Chunking and Metadata Preparation (Phase 9)."""

import unittest
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.chunk import ChunkInDB
from app.models.course import CourseInDB, Subtopic, Topic, Unit
from app.models.material import MaterialInDB, ProcessingStatus, SourceType
from app.models.syllabus_alignment import AlignedSegmentInDB, ScopeStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.syllabus_alignment_repository import SyllabusAlignmentRepository


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


class InMemoryAlignmentsCollection:
    """Mock in-memory collection simulating MongoDB syllabus_alignments collection."""

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
        items = list(self.docs.values())
        if query:
            if "material_id" in query:
                items = [d for d in items if d.get("material_id") == query["material_id"]]
            if "course_code" in query:
                items = [d for d in items if d.get("course_code") == query["course_code"]]
            if "scope_status" in query:
                items = [d for d in items if d.get("scope_status") == query["scope_status"]]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = [dict(i) for i in items]

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
                return self

            def __iter__(self) -> Any:
                return iter(self.items)

        return Cursor(items)


class InMemoryChunksCollection:
    """Mock in-memory collection simulating MongoDB chunks collection."""

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

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "_id" in query:
            _id = query["_id"]
            for d in self.docs.values():
                if d.get("_id") == _id:
                    return dict(d)
        return None

    def find(self, query: Dict[str, Any] = None) -> Any:
        items = list(self.docs.values())
        if query:
            if "material_id" in query:
                items = [d for d in items if d.get("material_id") == query["material_id"]]
            if "course_code" in query:
                items = [d for d in items if d.get("course_code") == query["course_code"]]
            if "unit_id" in query:
                items = [d for d in items if d.get("unit_id") == query["unit_id"]]
            if "topic_id" in query:
                items = [d for d in items if d.get("topic_id") == query["topic_id"]]
            if "scope_status" in query:
                items = [d for d in items if d.get("scope_status") == query["scope_status"]]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = [dict(i) for i in items]

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
                return self

            def limit(self, n: int) -> Any:
                self.items = self.items[:n]
                return self

            def __iter__(self) -> Any:
                return iter(self.items)

        return Cursor(items)

    def delete_many(self, query: Dict[str, Any]) -> Any:
        deleted = 0
        if "material_id" in query:
            mat_id = query["material_id"]
            for k, d in list(self.docs.items()):
                if d.get("material_id") == mat_id:
                    del self.docs[k]
                    deleted += 1
        elif "course_code" in query:
            code = query["course_code"]
            for k, d in list(self.docs.items()):
                if d.get("course_code") == code:
                    del self.docs[k]
                    deleted += 1

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(deleted)


class TestRAGChunking(unittest.TestCase):
    """Test suite covering Phase 9 RAG Chunking and Metadata Preparation."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up admin credentials and developer token."""
        cls.test_username = "chunk_admin"
        cls.test_password = "SecureChunkPassword123!"
        cls.test_password_hash = hash_password(cls.test_password)

        settings = get_settings()
        settings.ADMIN_USERNAME = cls.test_username
        settings.ADMIN_PASSWORD_HASH = cls.test_password_hash

        cls.dev_token = create_access_token(subject=cls.test_username, role="developer")
        cls.auth_headers = {"Authorization": f"Bearer {cls.dev_token}"}

    def setUp(self) -> None:
        """Patch database collections."""
        from unittest.mock import patch

        self.mock_courses_coll = InMemoryCoursesCollection()
        self.mock_materials_coll = InMemoryMaterialsCollection()
        self.mock_alignments_coll = InMemoryAlignmentsCollection()
        self.mock_chunks_coll = InMemoryChunksCollection()

        self.patcher_course = patch(
            "app.repositories.course_repository.get_courses_collection",
            return_value=self.mock_courses_coll,
        )
        self.patcher_mat = patch(
            "app.repositories.material_repository.get_materials_collection",
            return_value=self.mock_materials_coll,
        )
        self.patcher_align = patch(
            "app.repositories.syllabus_alignment_repository.get_syllabus_alignments_collection",
            return_value=self.mock_alignments_coll,
        )
        self.patcher_chunk = patch(
            "app.repositories.chunk_repository.get_chunks_collection",
            return_value=self.mock_chunks_coll,
        )

        self.patcher_course.start()
        self.patcher_mat.start()
        self.patcher_align.start()
        self.patcher_chunk.start()

        # Seed sample course BCSE301
        self.mock_courses_coll.insert_one({
            "course_code": "BCSE301",
            "course_name": "Database Management Systems",
            "description": "Core DBMS course",
        })

    def tearDown(self) -> None:
        """Stop patches."""
        self.patcher_course.stop()
        self.patcher_mat.stop()
        self.patcher_align.stop()
        self.patcher_chunk.stop()

    def test_1_chunk_unauthenticated_rejected(self) -> None:
        """Verify POST /dev/materials/{material_id}/chunk requires developer authentication."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/chunk")
            self.assertEqual(res.status_code, 401)

    def test_2_get_chunks_unauthenticated_rejected(self) -> None:
        """Verify GET /dev/materials/{material_id}/chunks requires developer authentication."""
        with TestClient(app) as client:
            res = client.get("/dev/materials/6a9cf9648fe403384c67ab2a/chunks")
            self.assertEqual(res.status_code, 401)

    def test_3_delete_chunks_unauthenticated_rejected(self) -> None:
        """Verify DELETE /dev/materials/{material_id}/chunks requires developer authentication."""
        with TestClient(app) as client:
            res = client.delete("/dev/materials/6a9cf9648fe403384c67ab2a/chunks")
            self.assertEqual(res.status_code, 401)

    def test_4_chunk_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when material does not exist."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/chunk", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_5_get_chunks_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when retrieving chunks for nonexistent material."""
        with TestClient(app) as client:
            res = client.get("/dev/materials/6a9cf9648fe403384c67ab2a/chunks", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_6_delete_chunks_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when deleting chunks for nonexistent material."""
        with TestClient(app) as client:
            res = client.delete("/dev/materials/6a9cf9648fe403384c67ab2a/chunks", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_7_chunk_unsupported_source_type_rejected(self) -> None:
        """Verify 400 is returned when trying to chunk exam_paper or syllabus."""
        with TestClient(app) as client:
            # Seed exam paper
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "cat1.pdf",
                "stored_filename": "stored_cat1.pdf",
                "source_type": "exam_paper",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/cat1.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            res = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("only [", res.json()["detail"].lower())

    def test_8_chunk_unaligned_material_rejected(self) -> None:
        """Verify 400 is returned when material has no syllabus alignment records in MongoDB."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "lecture1.pptx",
                "stored_filename": "stored_lecture1.pptx",
                "source_type": "lecture_material",
                "file_type": "pptx",
                "storage_path": "./storage/BCSE301/lecture1.pptx",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            res = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("no syllabus alignment records", res.json()["detail"].lower())

    def test_9_chunk_lecture_material_filters_out_of_syllabus_and_preserves_metadata(self) -> None:
        """Verify in-syllabus segments are chunked with complete metadata and out-of-syllabus segments are filtered."""
        with TestClient(app) as client:
            # 1. Seed lecture material
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "lecture_dbms.pptx",
                "stored_filename": "stored_lecture_dbms.pptx",
                "source_type": "lecture_material",
                "file_type": "pptx",
                "storage_path": "./storage/BCSE301/lecture_dbms.pptx",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            # 2. Seed 3 aligned segments:
            # Segment 1: IN_SYLLABUS (Relational Algebra)
            # Segment 2: OUT_OF_SYLLABUS (Quantum Computing)
            # Segment 3: IN_SYLLABUS (Functional Dependencies)
            self.mock_alignments_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": "Relational Algebra Operations: In this slide we explore Selection, Projection, and Join operations on relational schemas.",
                    "scope_status": "in_syllabus",
                    "unit_id": "BCSE301_U1",
                    "topic_id": "BCSE301_U1_T1",
                    "unit_name": "Relational Model & Algebra",
                    "topic_name": "Relational Algebra Operations",
                    "subtopic_id": "BCSE301_U1_T1_S1",
                    "confidence": 0.85,
                    "matched_keywords": ["relational algebra", "selection", "projection"],
                },
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 2,
                    "text": "Quantum entanglement and superposition introduce qubit gates that operate outside conventional database architectures.",
                    "scope_status": "out_of_syllabus",
                    "unit_id": None,
                    "topic_id": None,
                    "unit_name": None,
                    "topic_name": None,
                    "subtopic_id": None,
                    "confidence": 0.0,
                    "matched_keywords": [],
                },
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 3,
                    "text": "Functional Dependencies: Closure of attribute sets and minimal cover inference rules.",
                    "scope_status": "in_syllabus",
                    "unit_id": "BCSE301_U2",
                    "topic_id": "BCSE301_U2_T1",
                    "unit_name": "Database Design & Normalization",
                    "topic_name": "Functional Dependencies",
                    "subtopic_id": "BCSE301_U2_T1_S1",
                    "confidence": 0.78,
                    "matched_keywords": ["functional dependencies", "closure"],
                },
            ])

            # 3. Trigger chunking
            res = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["material_id"], mat_id)
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["total_aligned_pages"], 3)
            self.assertEqual(data["in_syllabus_pages"], 2)
            self.assertEqual(data["chunks_created"], 2)
            self.assertEqual(data["status"], "completed")

            # 4. Verify chunks via GET /dev/materials/{material_id}/chunks
            get_res = client.get(f"/dev/materials/{mat_id}/chunks", headers=self.auth_headers)
            self.assertEqual(get_res.status_code, 200)
            detail = get_res.json()
            self.assertEqual(detail["total_chunks"], 2)

            c1 = detail["chunks"][0]
            self.assertEqual(c1["page_number"], 1)
            self.assertEqual(c1["unit_id"], "BCSE301_U1")
            self.assertEqual(c1["unit"], 1)
            self.assertEqual(c1["topic_id"], "BCSE301_U1_T1")
            self.assertEqual(c1["topic"], "Relational Algebra Operations")
            self.assertEqual(c1["source_type"], "lecture_material")
            self.assertEqual(c1["scope_status"], "in_syllabus")
            self.assertIsNone(c1["embedding"])  # Zero embeddings in this phase
            self.assertTrue(c1["char_count"] > 30)

            c2 = detail["chunks"][1]
            self.assertEqual(c2["page_number"], 3)
            self.assertEqual(c2["unit_id"], "BCSE301_U2")
            self.assertEqual(c2["unit"], 2)
            self.assertEqual(c2["topic_id"], "BCSE301_U2_T1")
            self.assertEqual(c2["topic"], "Functional Dependencies")

    def test_10_chunk_long_reference_book_splits_contextually(self) -> None:
        """Verify long reference book chapter page is split into cohesive chunks."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "dbms_textbook.pdf",
                "stored_filename": "stored_dbms_textbook.pdf",
                "source_type": "reference_book",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/dbms_textbook.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            long_text = """
Relational Algebra Operations form the mathematical foundation for SQL query processing and optimization. The fundamental operations include selection, projection, Cartesian product, set union, and set difference.

Selection denotes a unary operation denoted by the lowercase Greek letter sigma. It filters tuples that satisfy a given selection predicate. The predicate is a boolean expression composed of attribute names, constants, and relational operators such as equal, not equal, less than, or greater than.

Projection denotes a unary operation denoted by the Greek letter pi. It outputs specified columns from the input relation and removes duplicate tuples to preserve the formal mathematical definition of a set.

Natural Join denoted by the bowtie operator combines tuples from two relations on their common attributes while eliminating duplicate column projections. It is formally equivalent to a Cartesian product followed by a selection on equality of common attributes, followed by projection.
"""
            self.mock_alignments_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 45,
                    "text": long_text,
                    "scope_status": "in_syllabus",
                    "unit_id": "BCSE301_U1",
                    "topic_id": "BCSE301_U1_T1",
                    "unit_name": "Relational Model",
                    "topic_name": "Relational Algebra Operations",
                    "subtopic_id": "BCSE301_U1_T1_S1",
                    "confidence": 0.90,
                    "matched_keywords": ["relational algebra", "selection", "projection", "join"],
                }
            ])

            res = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["in_syllabus_pages"], 1)
            self.assertTrue(data["chunks_created"] >= 2)  # Successfully split into multiple chunks

            detail_res = client.get(f"/dev/materials/{mat_id}/chunks", headers=self.auth_headers)
            chunks = detail_res.json()["chunks"]
            for idx, ch in enumerate(chunks):
                self.assertEqual(ch["unit_id"], "BCSE301_U1")
                self.assertEqual(ch["topic_id"], "BCSE301_U1_T1")
                self.assertEqual(ch["chunk_index"], idx)
                self.assertEqual(ch["source_type"], "reference_book")

    def test_11_chunk_material_with_zero_in_syllabus_handles_gracefully(self) -> None:
        """Verify material where all segments are out_of_syllabus returns 0 chunks gracefully."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "out_of_scope_notes.pdf",
                "stored_filename": "stored_out_of_scope_notes.pdf",
                "source_type": "lecture_material",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/out_of_scope_notes.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            self.mock_alignments_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": "Quantum physics and string theory overview.",
                    "scope_status": "out_of_syllabus",
                    "unit_id": None,
                    "topic_id": None,
                    "unit_name": None,
                    "topic_name": None,
                    "subtopic_id": None,
                    "confidence": 0.0,
                    "matched_keywords": [],
                }
            ])

            res = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["total_aligned_pages"], 1)
            self.assertEqual(data["in_syllabus_pages"], 0)
            self.assertEqual(data["chunks_created"], 0)

    def test_12_idempotent_rechunking_no_duplicates(self) -> None:
        """Verify re-chunking an aligned material replaces old chunk records without duplication."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "rechunk_notes.pdf",
                "stored_filename": "stored_rechunk_notes.pdf",
                "source_type": "lecture_material",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/rechunk_notes.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            self.mock_alignments_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": "SQL Queries: DDL, DML, and Subqueries.",
                    "scope_status": "in_syllabus",
                    "unit_id": "BCSE301_U1",
                    "topic_id": "BCSE301_U1_T2",
                    "unit_name": "SQL",
                    "topic_name": "SQL Queries and Aggregations",
                    "subtopic_id": "BCSE301_U1_T2_S1",
                    "confidence": 0.85,
                    "matched_keywords": ["sql queries", "ddl", "dml"],
                }
            ])

            # Run 1st time
            res1 = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(len(ChunkRepository.get_chunks_by_material(mat_id)), 1)

            # Run 2nd time (re-chunk)
            res2 = client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(len(ChunkRepository.get_chunks_by_material(mat_id)), 1)  # Still exactly 1

    def test_13_delete_material_chunks_endpoint(self) -> None:
        """Verify DELETE /dev/materials/{material_id}/chunks removes all chunks for that material."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "chunks_to_delete.pdf",
                "stored_filename": "stored_chunks_to_delete.pdf",
                "source_type": "lecture_material",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/chunks.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            self.mock_alignments_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": "Relational Algebra Operations: Selection and Projection.",
                    "scope_status": "in_syllabus",
                    "unit_id": "BCSE301_U1",
                    "topic_id": "BCSE301_U1_T1",
                    "unit_name": "Relational Model",
                    "topic_name": "Relational Algebra Operations",
                    "subtopic_id": "BCSE301_U1_T1_S1",
                    "confidence": 0.85,
                    "matched_keywords": ["relational algebra"],
                }
            ])

            client.post(f"/dev/materials/{mat_id}/chunk", headers=self.auth_headers)
            self.assertEqual(len(ChunkRepository.get_chunks_by_material(mat_id)), 1)

            # Delete
            del_res = client.delete(f"/dev/materials/{mat_id}/chunks", headers=self.auth_headers)
            self.assertEqual(del_res.status_code, 200)
            self.assertEqual(del_res.json()["status"], "success")
            self.assertEqual(del_res.json()["deleted_count"], 1)

            # Verify empty list
            get_res = client.get(f"/dev/materials/{mat_id}/chunks", headers=self.auth_headers)
            self.assertEqual(get_res.status_code, 200)
            self.assertEqual(get_res.json()["total_chunks"], 0)


if __name__ == "__main__":
    unittest.main()
