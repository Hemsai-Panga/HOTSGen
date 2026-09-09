"""Automated test suite for Syllabus Alignment and Content Classification (Phase 7)."""

import unittest
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.course import CourseInDB, Subtopic, Topic, Unit
from app.models.extracted_content import ExtractedContentInDB
from app.models.material import MaterialInDB, ProcessingStatus, SourceType
from app.models.syllabus_alignment import ScopeStatus
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
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

    def find_one_and_update(self, query: Dict[str, Any], update: Dict[str, Any], return_document: bool = True) -> Optional[Dict[str, Any]]:
        code = query.get("course_code")
        if code in self.docs:
            if "$set" in update:
                self.docs[code].update(update["$set"])
            return dict(self.docs[code])
        return None

    def find(self, query: Dict[str, Any] = None) -> Any:
        items = [dict(d) for d in self.docs.values()]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = items

            def skip(self, n: int) -> Any:
                self.items = self.items[n:]
                return self

            def limit(self, n: int) -> Any:
                self.items = self.items[:n]
                return self

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, ""), reverse=(direction == -1))
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

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        modified = 0
        if "_id" in query:
            _id = query["_id"]
            for d in self.docs.values():
                if d.get("_id") == _id:
                    if "$set" in update:
                        d.update(update["$set"])
                    modified = 1

        class UpdateResult:
            def __init__(self, count: int):
                self.modified_count = count

        return UpdateResult(modified)


class InMemoryExtractedCollection:
    """Mock in-memory collection simulating MongoDB extracted_content collection."""

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
        if query and "material_id" in query:
            mat_id = query["material_id"]
            items = [d for d in items if d.get("material_id") == mat_id]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = [dict(i) for i in items]

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
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

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(deleted)


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
            if "topic_id" in query:
                items = [d for d in items if d.get("topic_id") == query["topic_id"]]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = [dict(i) for i in items]

            def sort(self, key: str, direction: int = 1) -> Any:
                self.items.sort(key=lambda x: x.get(key, 0), reverse=(direction == -1))
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

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(deleted)


class TestSyllabusAlignment(unittest.TestCase):
    """Test suite covering Phase 7 Syllabus Alignment & Content Classification."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up admin credentials and developer token."""
        cls.test_username = "align_admin"
        cls.test_password = "SecureAlignPassword123!"
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
        self.mock_extracted_coll = InMemoryExtractedCollection()
        self.mock_alignments_coll = InMemoryAlignmentsCollection()

        self.patcher_course = patch(
            "app.repositories.course_repository.get_courses_collection",
            return_value=self.mock_courses_coll,
        )
        self.patcher_mat = patch(
            "app.repositories.material_repository.get_materials_collection",
            return_value=self.mock_materials_coll,
        )
        self.patcher_ext = patch(
            "app.repositories.extracted_content_repository.get_extracted_content_collection",
            return_value=self.mock_extracted_coll,
        )
        self.patcher_align = patch(
            "app.repositories.syllabus_alignment_repository.get_syllabus_alignments_collection",
            return_value=self.mock_alignments_coll,
        )

        self.patcher_course.start()
        self.patcher_mat.start()
        self.patcher_ext.start()
        self.patcher_align.start()

        # Seed sample course BCSE301 with structured syllabus hierarchy
        self.mock_courses_coll.insert_one({
            "course_code": "BCSE301",
            "course_name": "Database Management Systems",
            "description": "Core DBMS course",
            "units": [
                {
                    "id": "BCSE301_U1",
                    "unit_number": 1,
                    "unit_name": "Relational Model & Algebra",
                    "topics": [
                        {
                            "id": "BCSE301_U1_T1",
                            "topic_name": "Relational Algebra Operations",
                            "subtopics": [
                                {"id": "BCSE301_U1_T1_S1", "title": "Selection and Projection"},
                                {"id": "BCSE301_U1_T1_S2", "title": "Join Operations and Cartesian Product"},
                            ],
                        },
                        {
                            "id": "BCSE301_U1_T2",
                            "topic_name": "SQL Queries and Aggregations",
                            "subtopics": [
                                {"id": "BCSE301_U1_T2_S1", "title": "DDL and DML Statements"},
                                {"id": "BCSE301_U1_T2_S2", "title": "Subqueries and Group By"},
                            ],
                        },
                    ],
                },
                {
                    "id": "BCSE301_U2",
                    "unit_number": 2,
                    "unit_name": "Database Design and Normalization",
                    "topics": [
                        {
                            "id": "BCSE301_U2_T1",
                            "topic_name": "Functional Dependencies",
                            "subtopics": [
                                {"id": "BCSE301_U2_T1_S1", "title": "Inference Rules and Minimal Cover"},
                            ],
                        },
                        {
                            "id": "BCSE301_U2_T2",
                            "topic_name": "Normal Forms and Decomposition",
                            "subtopics": [
                                {"id": "BCSE301_U2_T2_S1", "title": "First, Second, and Third Normal Form"},
                                {"id": "BCSE301_U2_T2_S2", "title": "Boyce-Codd Normal Form BCNF"},
                            ],
                        },
                    ],
                },
            ],
        })

    def tearDown(self) -> None:
        """Stop patches."""
        self.patcher_course.stop()
        self.patcher_mat.stop()
        self.patcher_ext.stop()
        self.patcher_align.stop()

    def test_1_align_unauthenticated_rejected(self) -> None:
        """Verify POST /dev/materials/{material_id}/align-syllabus requires developer JWT."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/align-syllabus")
            self.assertEqual(res.status_code, 401)

    def test_2_get_alignment_unauthenticated_rejected(self) -> None:
        """Verify GET /dev/materials/{material_id}/alignment requires developer JWT."""
        with TestClient(app) as client:
            res = client.get("/dev/materials/6a9cf9648fe403384c67ab2a/alignment")
            self.assertEqual(res.status_code, 401)

    def test_3_align_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when material does not exist."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_4_get_alignment_nonexistent_material_returns_404(self) -> None:
        """Verify GET alignment returns 404 for unknown material."""
        with TestClient(app) as client:
            res = client.get("/dev/materials/6a9cf9648fe403384c67ab2a/alignment", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_5_align_invalid_source_type_rejected(self) -> None:
        """Verify 400 is returned when material source_type is syllabus or exam_paper."""
        with TestClient(app) as client:
            # Seed syllabus material
            syl_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "syllabus.pdf",
                "stored_filename": "stored_syllabus.pdf",
                "source_type": "syllabus",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/syllabus.pdf",
                "processing_status": "processed",
            })
            syl_id = str(syl_res.inserted_id)

            res = client.post(f"/dev/materials/{syl_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("only [", res.json()["detail"].lower())

    def test_6_align_unprocessed_material_rejected(self) -> None:
        """Verify 400 is returned when material has no extracted content in MongoDB."""
        with TestClient(app) as client:
            # Seed lecture material without extracted text
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "lecture1.pptx",
                "stored_filename": "stored_lecture1.pptx",
                "source_type": "lecture_material",
                "file_type": "pptx",
                "storage_path": "./storage/BCSE301/lecture1.pptx",
                "processing_status": "uploaded",
            })
            mat_id = str(mat_res.inserted_id)

            res = client.post(f"/dev/materials/{mat_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("no extracted content records", res.json()["detail"].lower())

    def test_7_align_missing_course_syllabus_hierarchy_rejected(self) -> None:
        """Verify 400 is returned when the course does not have an analyzed syllabus."""
        with TestClient(app) as client:
            # Seed course without units
            self.mock_courses_coll.insert_one({
                "course_code": "EMPTY101",
                "course_name": "Empty Syllabus Course",
                "description": "No syllabus analyzed yet",
                "units": [],
            })

            # Seed lecture material for EMPTY101
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "EMPTY101",
                "original_filename": "lecture_empty.pdf",
                "stored_filename": "stored_lecture_empty.pdf",
                "source_type": "lecture_material",
                "file_type": "pdf",
                "storage_path": "./storage/EMPTY101/lecture.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            # Seed extracted text
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "EMPTY101",
                    "page_number": 1,
                    "text": "Introduction to computer architecture and memory.",
                    "extraction_method": "pymupdf",
                    "char_count": 48,
                }
            ])

            res = client.post(f"/dev/materials/{mat_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("does not have an analyzed syllabus", res.json()["detail"].lower())

    def test_8_align_lecture_material_success(self) -> None:
        """Verify lecture material content is correctly classified into in_syllabus, out_of_syllabus, and retrieved."""
        with TestClient(app) as client:
            # 1. Seed lecture material for BCSE301
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "lecture_relational_alg.pptx",
                "stored_filename": "stored_lecture_relational_alg.pptx",
                "source_type": "lecture_material",
                "file_type": "pptx",
                "storage_path": "./storage/BCSE301/lecture_relational_alg.pptx",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            # 2. Seed 3 slides:
            # Slide 1: In-syllabus (Relational Algebra & Selection/Projection)
            # Slide 2: Out-of-syllabus (Quantum Computing & Superposition)
            # Slide 3: In-syllabus (Functional Dependencies & BCNF Decomposition)
            p1_text = "Relational Algebra Operations: In this lecture we discuss Selection and Projection join operations."
            p2_text = "Quantum computing introduces qubits, quantum superposition, entanglement, and quantum logic gates."
            p3_text = "Functional Dependencies and Normal Forms: Boyce-Codd Normal Form BCNF decomposition rules."

            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": p1_text,
                    "extraction_method": "python-pptx",
                    "char_count": len(p1_text),
                },
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 2,
                    "text": p2_text,
                    "extraction_method": "python-pptx",
                    "char_count": len(p2_text),
                },
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 3,
                    "text": p3_text,
                    "extraction_method": "python-pptx",
                    "char_count": len(p3_text),
                },
            ])

            # 3. Post alignment
            res = client.post(f"/dev/materials/{mat_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["material_id"], mat_id)
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["total_pages_aligned"], 3)
            self.assertEqual(data["in_syllabus_count"], 2)
            self.assertEqual(data["out_of_syllabus_count"], 1)
            self.assertEqual(data["ambiguous_count"], 0)
            self.assertEqual(data["alignment_status"], "completed")

            # 4. Get detailed alignment records via GET /dev/materials/{material_id}/alignment
            detail_res = client.get(f"/dev/materials/{mat_id}/alignment", headers=self.auth_headers)
            self.assertEqual(detail_res.status_code, 200)
            detail = detail_res.json()
            self.assertEqual(detail["total_pages"], 3)
            self.assertEqual(detail["in_syllabus_count"], 2)
            self.assertEqual(detail["out_of_syllabus_count"], 1)
            self.assertEqual(len(detail["segments"]), 3)

            # Slide 1 verification
            s1 = detail["segments"][0]
            self.assertEqual(s1["page_number"], 1)
            self.assertEqual(s1["scope_status"], "in_syllabus")
            self.assertEqual(s1["unit_id"], "BCSE301_U1")
            self.assertEqual(s1["topic_id"], "BCSE301_U1_T1")
            self.assertIn("Relational Algebra", s1["topic_name"])
            self.assertTrue(s1["confidence"] >= 0.50)

            # Slide 2 verification (Out of syllabus)
            s2 = detail["segments"][1]
            self.assertEqual(s2["page_number"], 2)
            self.assertEqual(s2["scope_status"], "out_of_syllabus")
            self.assertIsNone(s2["unit_id"])
            self.assertIsNone(s2["topic_id"])
            self.assertEqual(s2["confidence"], 0.0)

            # Slide 3 verification
            s3 = detail["segments"][2]
            self.assertEqual(s3["page_number"], 3)
            self.assertEqual(s3["scope_status"], "in_syllabus")
            self.assertEqual(s3["unit_id"], "BCSE301_U2")
            self.assertTrue(s3["confidence"] >= 0.40)

    def test_9_idempotent_realignment_replaces_cleanly(self) -> None:
        """Verify aligning a material multiple times replaces old records without duplication."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "lecture_sql.pdf",
                "stored_filename": "stored_lecture_sql.pdf",
                "source_type": "lecture_material",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/lecture_sql.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            sql_text = "SQL Queries: DDL and DML Statements including Subqueries and Group By aggregations."
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": sql_text,
                    "extraction_method": "pymupdf",
                    "char_count": len(sql_text),
                }
            ])

            # Run alignment 1st time
            res1 = client.post(f"/dev/materials/{mat_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res1.status_code, 200)
            segments1 = SyllabusAlignmentRepository.get_alignments_by_material(mat_id)
            self.assertEqual(len(segments1), 1)

            # Run alignment 2nd time (re-alignment)
            res2 = client.post(f"/dev/materials/{mat_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res2.status_code, 200)
            segments2 = SyllabusAlignmentRepository.get_alignments_by_material(mat_id)
            self.assertEqual(len(segments2), 1)  # Still exactly 1 record, no duplicates

    def test_10_align_reference_book_success(self) -> None:
        """Verify reference_book material alignment works properly."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "korth_dbms.pdf",
                "stored_filename": "stored_korth_dbms.pdf",
                "source_type": "reference_book",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/korth_dbms.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            book_text = "Chapter 7: Normal Forms and Functional Dependencies. Boyce-Codd Normal Form BCNF decomposition rules."
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 142,
                    "text": book_text,
                    "extraction_method": "pymupdf",
                    "char_count": len(book_text),
                }
            ])

            res = client.post(f"/dev/materials/{mat_id}/align-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["in_syllabus_count"], 1)
            self.assertEqual(data["out_of_syllabus_count"], 0)


if __name__ == "__main__":
    unittest.main()
