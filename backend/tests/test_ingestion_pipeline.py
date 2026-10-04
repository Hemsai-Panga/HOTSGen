"""Automated test suite for Developer Ingestion Pipeline Integration (Phase 11)."""

import os
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.chunk import ChunkInDB, ChunkPreparationResponse
from app.models.course import CourseInDB, SyllabusAnalysisResponse
from app.models.extracted_content import ExtractedContentInDB, ExtractedPageContent, MaterialProcessResponse
from app.models.material import MaterialInDB, ProcessingStatus, SourceType
from app.models.pipeline import (
    IngestionPipelineResponse,
    IngestionStatusResponse,
    PipelineStageResult,
    StageName,
    StageStatus,
)
from app.models.syllabus_alignment import AlignedSegmentInDB, AlignmentSummaryResponse, ScopeStatus
from app.models.teaching_question import DifficultyLevel, ExamType, QuestionExtractionResponse, TeachingQuestionInDB
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.syllabus_alignment_repository import SyllabusAlignmentRepository
from app.repositories.teaching_question_repository import TeachingQuestionRepository
from app.services.ingestion_service import IngestionPipelineService


class InMemoryCoursesCollection:
    """Mock collection for courses."""

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

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        code = query.get("course_code")
        matched = 0
        modified = 0
        if code in self.docs:
            matched = 1
            if "$set" in update:
                for k, v in update["$set"].items():
                    self.docs[code][k] = v
                modified = 1

        class UpdateResult:
            def __init__(self, matched_count: int, modified_count: int):
                self.matched_count = matched_count
                self.modified_count = modified_count

        return UpdateResult(matched, modified)


class InMemoryMaterialsCollection:
    """Mock collection for materials."""

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

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        matched = 0
        modified = 0
        if "_id" in query:
            target_id = str(query["_id"])
            if target_id in self.docs:
                matched = 1
                if "$set" in update:
                    for k, v in update["$set"].items():
                        self.docs[target_id][k] = v
                    modified = 1

        class UpdateResult:
            def __init__(self, matched_count: int, modified_count: int):
                self.matched_count = matched_count
                self.modified_count = modified_count

        return UpdateResult(matched, modified)


class InMemoryExtractedContentCollection:
    """Mock collection for extracted content."""

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

    def insert_one(self, doc: Dict[str, Any]) -> Any:
        doc_copy = dict(doc)
        _id = ObjectId()
        doc_copy["_id"] = _id
        self.docs[str(_id)] = doc_copy

        class InsertResult:
            def __init__(self, inserted_id: ObjectId):
                self.inserted_id = inserted_id

        return InsertResult(_id)

    def find(self, query: Dict[str, Any] = None) -> Any:
        query = query or {}
        results = []
        for d in self.docs.values():
            match = True
            for k, v in query.items():
                if d.get(k) != v:
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

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cursor = self.find(query)
        items = list(cursor)
        return items[0] if items else None

    def delete_many(self, query: Dict[str, Any]) -> Any:
        to_delete = [k for k, d in self.docs.items() if all(d.get(qk) == qv for qk, qv in query.items())]
        for k in to_delete:
            del self.docs[k]

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(len(to_delete))


class InMemoryAlignmentsCollection:
    """Mock collection for syllabus alignments."""

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
                if d.get(k) != v:
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

    def delete_many(self, query: Dict[str, Any]) -> Any:
        to_delete = [k for k, d in self.docs.items() if all(d.get(qk) == qv for qk, qv in query.items())]
        for k in to_delete:
            del self.docs[k]

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(len(to_delete))


class InMemoryChunksCollection:
    """Mock collection for chunks."""

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
                if k == "embedding" and isinstance(v, dict) and "$ne" in v:
                    if v["$ne"] is None and d.get("embedding") is None:
                        match = False
                        break
                elif d.get(k) != v:
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
        to_delete = [k for k, d in self.docs.items() if all(d.get(qk) == qv for qk, qv in query.items())]
        for k in to_delete:
            del self.docs[k]

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(len(to_delete))


class InMemoryTeachingQuestionsCollection:
    """Mock collection for teaching questions."""

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
                if k == "embedding" and isinstance(v, dict) and "$ne" in v:
                    if v["$ne"] is None and d.get("embedding") is None:
                        match = False
                        break
                elif d.get(k) != v:
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
        to_delete = [k for k, d in self.docs.items() if all(d.get(qk) == qv for qk, qv in query.items())]
        for k in to_delete:
            del self.docs[k]

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(len(to_delete))


class TestIngestionPipeline(unittest.TestCase):
    """Test suite covering Phase 11: Developer Ingestion Pipeline Integration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.test_username = "pipeline_admin"
        cls.test_password = "PipelinePassword123!"
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
        self.mock_extracted = InMemoryExtractedContentCollection()
        self.mock_alignments = InMemoryAlignmentsCollection()
        self.mock_chunks = InMemoryChunksCollection()
        self.mock_tq = InMemoryTeachingQuestionsCollection()

        self.courses_patch = patch("app.repositories.course_repository.get_courses_collection", return_value=self.mock_courses)
        self.materials_patch = patch("app.repositories.material_repository.get_materials_collection", return_value=self.mock_materials)
        self.extracted_patch = patch("app.repositories.extracted_content_repository.get_extracted_content_collection", return_value=self.mock_extracted)
        self.alignments_patch = patch("app.repositories.syllabus_alignment_repository.get_syllabus_alignments_collection", return_value=self.mock_alignments)
        self.chunks_patch = patch("app.repositories.chunk_repository.get_chunks_collection", return_value=self.mock_chunks)
        self.tq_patch = patch("app.repositories.teaching_question_repository.get_teaching_questions_collection", return_value=self.mock_tq)

        self.courses_patch.start()
        self.materials_patch.start()
        self.extracted_patch.start()
        self.alignments_patch.start()
        self.chunks_patch.start()
        self.tq_patch.start()

        # Deterministic mock embedding generator: produces 384-dim normalized unit vectors
        self.mock_generator = MagicMock()
        self.mock_generator.generate_embedding.return_value = [1.0] + [0.0] * 383
        self.mock_generator.generate_embeddings_batch.side_effect = lambda texts, batch_size=32: [[1.0] + [0.0] * 383 for _ in texts]
        self.mock_generator.dimension = 384
        self.mock_generator.embedding_dimension = 384
        self.mock_generator.model_name = "all-MiniLM-L6-v2"

        self.gen_patch = patch("app.core.embeddings.EmbeddingGenerator.get_instance", return_value=self.mock_generator)
        self.gen_patch.start()

    def tearDown(self) -> None:
        self.gen_patch.stop()
        self.tq_patch.stop()
        self.chunks_patch.stop()
        self.alignments_patch.stop()
        self.extracted_patch.stop()
        self.materials_patch.stop()
        self.courses_patch.stop()

    def _seed_course(self, course_code: str = "BCSE301") -> None:
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

    def _seed_material(
        self,
        course_code: str = "BCSE301",
        source_type: SourceType = SourceType.LECTURE_MATERIAL,
        filename: str = "lecture1.pdf",
    ) -> str:
        mat_doc = {
            "course_code": course_code,
            "original_filename": filename,
            "stored_filename": f"stored_{filename}",
            "storage_path": f"/storage/{filename}",
            "file_type": "pdf",
            "source_type": source_type.value if hasattr(source_type, "value") else source_type,
            "processing_status": "uploaded",
            "exam_type": "CAT1" if source_type == SourceType.EXAM_PAPER else None,
            "year": 2023 if source_type == SourceType.EXAM_PAPER else None,
        }
        res = self.mock_materials.insert_one(mat_doc)
        return str(res.inserted_id)

    # --- Test Cases ---

    def test_1_unauthenticated_rejected(self) -> None:
        """Verify 401 Unauthorized when invoking pipeline endpoints without developer JWT."""
        dummy_id = str(ObjectId())
        res1 = self.client.post(f"/dev/materials/{dummy_id}/ingest")
        self.assertEqual(res1.status_code, 401)

        res2 = self.client.get(f"/dev/materials/{dummy_id}/pipeline-status")
        self.assertEqual(res2.status_code, 401)

    def test_2_ingest_material_not_found(self) -> None:
        """Verify 404 Not Found when triggering pipeline on non-existent material."""
        dummy_id = str(ObjectId())
        res1 = self.client.post(f"/dev/materials/{dummy_id}/ingest", headers=self.auth_headers)
        self.assertEqual(res1.status_code, 404)

        res2 = self.client.get(f"/dev/materials/{dummy_id}/pipeline-status", headers=self.auth_headers)
        self.assertEqual(res2.status_code, 404)

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_alignment_service.SyllabusAlignmentService.align_material")
    @patch("app.services.chunk_service.ChunkService.chunk_material")
    @patch("app.services.embedding_service.EmbeddingService.generate_material_embeddings")
    def test_3_end_to_end_lecture_material_ingestion_success(
        self,
        mock_embed: MagicMock,
        mock_chunk: MagicMock,
        mock_align: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Verify complete 4-stage pipeline execution for lecture materials."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.LECTURE_MATERIAL, "lecture_indexing.pdf")

        # Mock stage return values
        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=3,
            extraction_method="pymupdf",
            total_characters=1500,
        )
        mock_align.return_value = AlignmentSummaryResponse(
            material_id=mat_id,
            course_code="BCSE301",
            total_pages_aligned=6,
            in_syllabus_count=5,
            out_of_syllabus_count=1,
            ambiguous_count=0,
            alignment_status="completed",
            message="Material content aligned against course syllabus hierarchy successfully.",
        )
        mock_chunk.return_value = ChunkPreparationResponse(
            material_id=mat_id,
            course_code="BCSE301",
            source_type="lecture_material",
            total_aligned_pages=6,
            in_syllabus_pages=5,
            chunks_created=4,
            status="completed",
            message="Successfully generated 4 knowledge chunks from 5 in-syllabus segments.",
            chunks=[],
        )
        mock_embed.return_value = MagicMock(embedded_count=4, dimension=384)

        # Trigger pipeline
        response = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["material_id"], mat_id)
        self.assertEqual(data["overall_status"], "completed")
        self.assertIsNone(data["error_message"])

        # Validate stage sequence and completion
        stages = data["stages"]
        self.assertEqual(len(stages), 4)
        self.assertEqual(stages[0]["stage"], "extraction")
        self.assertEqual(stages[0]["status"], "completed")
        self.assertEqual(stages[0]["details"]["pages_processed"], 3)
        self.assertEqual(stages[1]["stage"], "syllabus_alignment")
        self.assertEqual(stages[1]["status"], "completed")
        self.assertEqual(stages[2]["stage"], "chunking")
        self.assertEqual(stages[2]["status"], "completed")
        self.assertEqual(stages[3]["stage"], "embeddings")
        self.assertEqual(stages[3]["status"], "completed")

        # Verify underlying services were invoked in order
        mock_extract.assert_called_once_with(mat_id)
        mock_align.assert_called_once_with(mat_id)
        mock_chunk.assert_called_once_with(mat_id)
        mock_embed.assert_called_once_with(mat_id)

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.teaching_question_service.TeachingQuestionService.extract_questions_from_material")
    @patch("app.services.embedding_service.EmbeddingService.generate_material_embeddings")
    def test_4_end_to_end_exam_paper_ingestion_success(
        self,
        mock_embed: MagicMock,
        mock_questions: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Verify complete 3-stage pipeline execution for past exam papers."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.EXAM_PAPER, "cat1_2023.pdf")

        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=2,
            extraction_method="pymupdf",
            total_characters=800,
        )
        mock_questions.return_value = MagicMock(questions_extracted=3, exam_type=ExamType.CAT1, year=2023)
        mock_embed.return_value = MagicMock(embedded_count=3, dimension=384)

        response = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["overall_status"], "completed")
        stages = data["stages"]
        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0]["stage"], "extraction")
        self.assertEqual(stages[1]["stage"], "question_structuring")
        self.assertEqual(stages[2]["stage"], "embeddings")
        for s in stages:
            self.assertEqual(s["status"], "completed")

        mock_extract.assert_called_once_with(mat_id)
        mock_questions.assert_called_once_with(mat_id)
        mock_embed.assert_called_once_with(mat_id)

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_service.SyllabusService.analyze_syllabus")
    def test_5_end_to_end_syllabus_ingestion_success(
        self,
        mock_syllabus: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Verify complete 2-stage pipeline execution for syllabus documents."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.SYLLABUS, "syllabus.pdf")

        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=2,
            extraction_method="pymupdf",
            total_characters=1200,
        )
        mock_syllabus.return_value = SyllabusAnalysisResponse(
            material_id=mat_id,
            course_code="BCSE301",
            units_count=2,
            topics_count=8,
            subtopics_count=4,
            status="analyzed",
            message="Successfully structured syllabus into 2 units and 8 topics.",
        )

        response = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["overall_status"], "completed")
        stages = data["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[0]["stage"], "extraction")
        self.assertEqual(stages[1]["stage"], "syllabus_analysis")
        self.assertEqual(stages[1]["details"]["units_count"], 2)
        self.assertEqual(stages[1]["details"]["topics_count"], 8)
        self.assertEqual(stages[1]["details"]["subtopics_count"], 4)
        for s in stages:
            self.assertEqual(s["status"], "completed")

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_alignment_service.SyllabusAlignmentService.align_material")
    @patch("app.services.chunk_service.ChunkService.chunk_material")
    @patch("app.services.embedding_service.EmbeddingService.generate_material_embeddings")
    def test_6_intermediate_stage_failure_handling(
        self,
        mock_embed: MagicMock,
        mock_chunk: MagicMock,
        mock_align: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Verify pipeline halts on intermediate stage failure and skips subsequent stages."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.LECTURE_MATERIAL, "lecture_corrupt.pdf")

        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=3,
            extraction_method="pymupdf",
            total_characters=1500,
        )
        mock_align.side_effect = RuntimeError("Alignment model timeout")

        response = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["overall_status"], "failed")
        self.assertEqual(data["current_stage"], "syllabus_alignment")
        self.assertIn("Alignment model timeout", data["error_message"])

        stages = data["stages"]
        self.assertEqual(stages[0]["stage"], "extraction")
        self.assertEqual(stages[0]["status"], "completed")
        self.assertEqual(stages[1]["stage"], "syllabus_alignment")
        self.assertEqual(stages[1]["status"], "failed")
        self.assertEqual(stages[2]["stage"], "chunking")
        self.assertEqual(stages[2]["status"], "skipped")
        self.assertEqual(stages[3]["stage"], "embeddings")
        self.assertEqual(stages[3]["status"], "skipped")

        # Verify subsequent stages were NOT invoked
        mock_chunk.assert_not_called()
        mock_embed.assert_not_called()

        # Verify material state in database is failed
        material = MaterialRepository.get_material(mat_id)
        self.assertIsNotNone(material)
        self.assertEqual(material.processing_status, ProcessingStatus.FAILED)
        self.assertIn("syllabus_alignment", material.error_message)

    def test_7_pipeline_status_reporting(self) -> None:
        """Verify GET /dev/materials/{material_id}/pipeline-status reports granular metrics."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.LECTURE_MATERIAL, "lecture_status.pdf")

        # 1. Initial status before any processing
        res1 = self.client.get(f"/dev/materials/{mat_id}/pipeline-status", headers=self.auth_headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["extracted_page_count"], 0)
        self.assertEqual(data1["chunk_count"], 0)
        self.assertEqual(data1["embeddings_count"], 0)
        self.assertFalse(data1["is_fully_ingested"])

        # 2. Seed extracted pages, chunks, and embeddings
        self.mock_extracted.insert_many([
            {
                "material_id": mat_id,
                "course_code": "BCSE301",
                "page_number": 1,
                "text": "Page 1 content",
                "extraction_method": "pymupdf",
                "char_count": 14,
            }
        ])
        self.mock_alignments.insert_many([
            {
                "material_id": mat_id,
                "course_code": "BCSE301",
                "page_number": 1,
                "scope_status": "in_syllabus",
                "text": "Page 1 content",
            }
        ])
        self.mock_chunks.insert_many([
            {
                "material_id": mat_id,
                "course_code": "BCSE301",
                "text": "Chunk 1",
                "embedding": [1.0] * 384,
                "scope_status": "in_syllabus",
                "chunk_index": 0,
            }
        ])
        # Mark material completed
        MaterialRepository.update_material_status(mat_id, ProcessingStatus.COMPLETED)

        # 3. Check status again
        res2 = self.client.get(f"/dev/materials/{mat_id}/pipeline-status", headers=self.auth_headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["extracted_page_count"], 1)
        self.assertEqual(data2["alignment_segment_count"], 1)
        self.assertEqual(data2["chunk_count"], 1)
        self.assertEqual(data2["embeddings_count"], 1)
        self.assertTrue(data2["is_fully_ingested"])

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_alignment_service.SyllabusAlignmentService.align_material")
    @patch("app.services.chunk_service.ChunkService.chunk_material")
    @patch("app.services.embedding_service.EmbeddingService.generate_material_embeddings")
    def test_8_idempotent_pipeline_rerun(
        self,
        mock_embed: MagicMock,
        mock_chunk: MagicMock,
        mock_align: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Verify re-running pipeline executes successfully and updates material state idempotently."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.LECTURE_MATERIAL, "lecture_rerun.pdf")

        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=2,
            extraction_method="pymupdf",
            total_characters=1000,
        )
        mock_align.return_value = AlignmentSummaryResponse(
            material_id=mat_id,
            course_code="BCSE301",
            total_pages_aligned=4,
            in_syllabus_count=4,
            out_of_syllabus_count=0,
            ambiguous_count=0,
            alignment_status="completed",
            message="Material content aligned against course syllabus hierarchy successfully.",
        )
        mock_chunk.return_value = ChunkPreparationResponse(
            material_id=mat_id,
            course_code="BCSE301",
            source_type="lecture_material",
            total_aligned_pages=4,
            in_syllabus_pages=4,
            chunks_created=2,
            status="completed",
            message="Successfully generated 2 knowledge chunks.",
            chunks=[],
        )
        mock_embed.return_value = MagicMock(embedded_count=2, dimension=384)

        # First run
        res1 = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["overall_status"], "completed")

        # Second run (re-run)
        res2 = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["overall_status"], "completed")

        self.assertEqual(mock_extract.call_count, 2)
        self.assertEqual(mock_align.call_count, 2)
        self.assertEqual(mock_chunk.call_count, 2)
        self.assertEqual(mock_embed.call_count, 2)

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_alignment_service.SyllabusAlignmentService.align_material")
    @patch("app.services.chunk_service.ChunkService.chunk_material")
    @patch("app.services.embedding_service.EmbeddingService.generate_material_embeddings")
    def test_9_extraction_stage_consumes_material_process_response_without_attribute_error(
        self,
        mock_embed: MagicMock,
        mock_chunk: MagicMock,
        mock_align: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Regression test: Ensure ingestion pipeline handles real MaterialProcessResponse instance without AttributeError."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.LECTURE_MATERIAL, "real_process_response.pdf")

        # Instantiate actual MaterialProcessResponse model matching Phase 5 contract
        real_response = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=3,
            extraction_method="pymupdf",
            total_characters=7084,
            message="Document processed and text extracted successfully",
        )
        mock_extract.return_value = real_response
        mock_align.return_value = AlignmentSummaryResponse(
            material_id=mat_id,
            course_code="BCSE301",
            total_pages_aligned=5,
            in_syllabus_count=5,
            out_of_syllabus_count=0,
            ambiguous_count=0,
            alignment_status="completed",
            message="Material content aligned against course syllabus hierarchy successfully.",
        )
        mock_chunk.return_value = ChunkPreparationResponse(
            material_id=mat_id,
            course_code="BCSE301",
            source_type="lecture_material",
            total_aligned_pages=5,
            in_syllabus_pages=5,
            chunks_created=3,
            status="completed",
            message="Successfully generated 3 knowledge chunks.",
            chunks=[],
        )
        mock_embed.return_value = MagicMock(embedded_count=3, dimension=384)

        res = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["overall_status"], "completed")
        extract_stage = data["stages"][0]
        self.assertEqual(extract_stage["stage"], "extraction")
        self.assertEqual(extract_stage["status"], "completed")
        self.assertEqual(extract_stage["details"]["pages_processed"], 3)
        self.assertEqual(extract_stage["details"]["total_characters"], 7084)
        self.assertEqual(extract_stage["details"]["extraction_method"], "pymupdf")
        self.assertEqual(extract_stage["message"], "Extracted 3 pages of text.")

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_service.SyllabusService.analyze_syllabus")
    def test_10_syllabus_analysis_stage_consumes_syllabus_analysis_response_without_attribute_error(
        self,
        mock_syllabus: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Regression test: Ensure ingestion pipeline handles real SyllabusAnalysisResponse instance without AttributeError."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.SYLLABUS, "real_syllabus_analysis_response.pdf")

        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=4,
            extraction_method="pymupdf",
            total_characters=8500,
            message="Document processed and text extracted successfully",
        )

        # Instantiate actual SyllabusAnalysisResponse matching Phase 6 canonical model
        real_syllabus_res = SyllabusAnalysisResponse(
            material_id=mat_id,
            course_code="BCSE301",
            units_count=6,
            topics_count=67,
            subtopics_count=38,
            status="analyzed",
            message="Successfully structured syllabus into 6 units and 67 topics.",
        )
        mock_syllabus.return_value = real_syllabus_res

        res = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["overall_status"], "completed")
        self.assertEqual(len(data["stages"]), 2)

        syllabus_stage = data["stages"][1]
        self.assertEqual(syllabus_stage["stage"], "syllabus_analysis")
        self.assertEqual(syllabus_stage["status"], "completed")
        self.assertEqual(syllabus_stage["details"]["units_count"], 6)
        self.assertEqual(syllabus_stage["details"]["topics_count"], 67)
        self.assertEqual(syllabus_stage["details"]["subtopics_count"], 38)
        self.assertEqual(syllabus_stage["message"], "Analyzed syllabus structure (6 units, 67 topics).")

    @patch("app.services.document_processing_service.DocumentProcessingService.process_material")
    @patch("app.services.syllabus_alignment_service.SyllabusAlignmentService.align_material")
    @patch("app.services.chunk_service.ChunkService.chunk_material")
    @patch("app.services.embedding_service.EmbeddingService.generate_material_embeddings")
    def test_11_syllabus_alignment_stage_consumes_alignment_summary_response_without_attribute_error(
        self,
        mock_embed: MagicMock,
        mock_chunk: MagicMock,
        mock_align: MagicMock,
        mock_extract: MagicMock,
    ) -> None:
        """Regression test (ISSUE 1): Ensure reference-book / lecture alignment consumes canonical AlignmentSummaryResponse without AttributeError."""
        self._seed_course("BCSE301")
        mat_id = self._seed_material("BCSE301", SourceType.REFERENCE_BOOK, "reference_text.pdf")

        mock_extract.return_value = MaterialProcessResponse(
            material_id=mat_id,
            course_code="BCSE301",
            processing_status=ProcessingStatus.PROCESSED,
            pages_processed=18,
            extraction_method="pymupdf",
            total_characters=23167,
            message="Document processed and text extracted successfully",
        )

        # Real canonical AlignmentSummaryResponse matching Phase 7 contract
        real_alignment_res = AlignmentSummaryResponse(
            material_id=mat_id,
            course_code="BCSE301",
            total_pages_aligned=18,
            in_syllabus_count=6,
            out_of_syllabus_count=8,
            ambiguous_count=4,
            alignment_status="completed",
            message="Material content aligned against course syllabus hierarchy successfully.",
        )
        mock_align.return_value = real_alignment_res

        real_chunk_res = ChunkPreparationResponse(
            material_id=mat_id,
            course_code="BCSE301",
            source_type="reference_book",
            total_aligned_pages=18,
            in_syllabus_pages=6,
            chunks_created=12,
            status="completed",
            message="Successfully generated 12 knowledge chunks from 6 in-syllabus segments.",
            chunks=[],
        )
        mock_chunk.return_value = real_chunk_res
        mock_embed.return_value = MagicMock(embedded_count=12, dimension=384)

        res = self.client.post(f"/dev/materials/{mat_id}/ingest", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["overall_status"], "completed")
        align_stage = data["stages"][1]
        self.assertEqual(align_stage["stage"], "syllabus_alignment")
        self.assertEqual(align_stage["status"], "completed")
        self.assertEqual(align_stage["details"]["total_pages_aligned"], 18)
        self.assertEqual(align_stage["details"]["in_syllabus_count"], 6)
        self.assertEqual(align_stage["details"]["out_of_syllabus_count"], 8)
        self.assertEqual(align_stage["details"]["ambiguous_count"], 4)
        self.assertEqual(align_stage["message"], "Aligned 18 segments (6 in-syllabus).")

        chunk_stage = data["stages"][2]
        self.assertEqual(chunk_stage["stage"], "chunking")
        self.assertEqual(chunk_stage["status"], "completed")
        self.assertEqual(chunk_stage["details"]["chunks_created"], 12)
        self.assertEqual(chunk_stage["details"]["in_syllabus_pages"], 6)
        self.assertEqual(chunk_stage["details"]["total_aligned_pages"], 18)
        self.assertEqual(chunk_stage["message"], "Prepared 12 context chunks.")


if __name__ == "__main__":
    unittest.main()

