"""Automated test suite for Syllabus Analysis and Course Structure (Phase 6)."""

import io
import unittest
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.course import CourseInDB, Unit
from app.models.extracted_content import ExtractedContentInDB
from app.models.material import MaterialInDB, ProcessingStatus, SourceType
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
from app.repositories.material_repository import MaterialRepository


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


class TestSyllabusAnalysis(unittest.TestCase):
    """Test suite covering Phase 6 Syllabus Analysis and Hierarchy Extraction."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up admin credentials and developer token."""
        cls.test_username = "syllabus_admin"
        cls.test_password = "SecureSyllabusPassword123!"
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

        self.patcher_course.start()
        self.patcher_mat.start()
        self.patcher_ext.start()

        # Seed sample course BCSE301
        self.mock_courses_coll.insert_one({
            "course_code": "BCSE301",
            "course_name": "Database Management Systems",
            "description": "Core DBMS course",
            "units": [],
        })

    def tearDown(self) -> None:
        """Stop patches."""
        self.patcher_course.stop()
        self.patcher_mat.stop()
        self.patcher_ext.stop()

    def test_1_analyze_syllabus_unauthenticated_rejected(self) -> None:
        """Verify POST /dev/materials/{material_id}/analyze-syllabus requires developer authentication."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/analyze-syllabus")
            self.assertEqual(res.status_code, 401)

    def test_2_analyze_syllabus_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when material does not exist."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/analyze-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_3_analyze_non_syllabus_material_rejected(self) -> None:
        """Verify 400 is returned when material is not of source_type 'syllabus'."""
        with TestClient(app) as client:
            # Seed lecture material
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

            res = client.post(f"/dev/materials/{mat_id}/analyze-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("only materials of type 'syllabus'", res.json()["detail"].lower())

    def test_4_analyze_syllabus_without_extracted_content_rejected(self) -> None:
        """Verify 400 is returned when material has not been processed for text extraction."""
        with TestClient(app) as client:
            # Seed syllabus material without extracted content
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "syllabus.pdf",
                "stored_filename": "stored_syllabus.pdf",
                "source_type": "syllabus",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/syllabus.pdf",
                "processing_status": "uploaded",
            })
            mat_id = str(mat_res.inserted_id)

            res = client.post(f"/dev/materials/{mat_id}/analyze-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("no extracted content found", res.json()["detail"].lower())

    def test_5_analyze_syllabus_success_and_course_hierarchy_populated(self) -> None:
        """Verify valid syllabus text is correctly structured into units, topics, and subtopics."""
        with TestClient(app) as client:
            # 1. Seed syllabus material
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "dbms_syllabus.pdf",
                "stored_filename": "stored_syllabus.pdf",
                "source_type": "syllabus",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/syllabus.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            # 2. Seed extracted syllabus text
            syllabus_text = """
Course Code: BCSE301
Course Name: Database Management Systems

UNIT I: Introduction to Databases and Relational Model
Database System Concepts and Architecture; Data Models and Schemas.
Relational Model: Domains, Attributes, Tuples, Relations, Integrity Constraints.

UNIT II: SQL and Relational Algebra
Relational Algebra Operations: Selection, Projection, Joins, Division.
SQL Queries: DDL, DML, Subqueries, Complex Joins, Aggregation Functions.

UNIT III: Database Design and Normalization
Functional Dependencies: Inference Rules, Minimal Cover.
Normalization: 1NF, 2NF, 3NF, BCNF, Multivalued Dependencies.

UNIT IV: Transaction Processing and Concurrency Control
Transaction Concepts: ACID Properties, Transaction States.
Concurrency Control: Two-Phase Locking, Timestamp Ordering.
"""
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": syllabus_text,
                    "extraction_method": "pymupdf",
                    "char_count": len(syllabus_text),
                }
            ])

            # 3. Trigger analyze-syllabus
            res = client.post(f"/dev/materials/{mat_id}/analyze-syllabus", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["units_count"], 4)
            self.assertTrue(data["topics_count"] >= 8)
            self.assertTrue(data["subtopics_count"] >= 10)
            self.assertEqual(data["status"], "analyzed")

            # 4. Verify Course in MongoDB has structured units
            course = CourseRepository.get_course("BCSE301")
            self.assertIsNotNone(course)
            self.assertEqual(len(course.units), 4)

            # Verify Unit 1
            u1 = course.units[0]
            self.assertEqual(u1.unit_number, 1)
            self.assertIn("Introduction to Databases", u1.unit_name)
            self.assertEqual(u1.id, "BCSE301_U1")
            self.assertTrue(len(u1.topics) >= 2)

            # Verify Topic & Subtopics in Unit 2
            u2 = course.units[1]
            self.assertEqual(u2.unit_number, 2)
            topic_names = [t.topic_name for t in u2.topics]
            self.assertIn("Relational Algebra Operations", topic_names)
            rel_alg_topic = next(t for t in u2.topics if t.topic_name == "Relational Algebra Operations")
            subtopic_titles = [s.title for s in rel_alg_topic.subtopics]
            self.assertIn("Selection", subtopic_titles)
            self.assertIn("Projection", subtopic_titles)
            self.assertIn("Joins", subtopic_titles)

    def test_6_reanalysis_overwrites_cleanly_without_duplicates(self) -> None:
        """Verify that analyzing a syllabus a second time safely replaces the previous hierarchy."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "syllabus.pdf",
                "stored_filename": "stored_syllabus.pdf",
                "source_type": "syllabus",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/syllabus.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            syllabus_v1 = """
Module 1: Relational Foundations
Relational Algebra: Select, Project, Join.
Module 2: SQL Language
SQL Basics: DDL, DML.
"""
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": syllabus_v1,
                    "extraction_method": "pymupdf",
                    "char_count": len(syllabus_v1),
                }
            ])

            # First analysis
            res1 = client.post(f"/dev/materials/{mat_id}/analyze-syllabus", headers=self.auth_headers)
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(len(CourseRepository.get_course("BCSE301").units), 2)

            # Update extracted content with 3 modules
            self.mock_extracted_coll.delete_many({"material_id": mat_id})
            syllabus_v2 = """
Module 1: Relational Foundations
Relational Algebra: Select, Project, Join.
Module 2: SQL Language
SQL Basics: DDL, DML.
Module 3: Indexing and Hashing
B-Trees and B+ Trees; Static and Dynamic Hashing.
"""
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": syllabus_v2,
                    "extraction_method": "pymupdf",
                    "char_count": len(syllabus_v2),
                }
            ])

            # Second analysis (Re-analysis)
            res2 = client.post(f"/dev/materials/{mat_id}/analyze-syllabus", headers=self.auth_headers)
            self.assertEqual(res2.status_code, 200)
            course = CourseRepository.get_course("BCSE301")
            self.assertEqual(len(course.units), 3)  # Overwritten cleanly to 3 units, not 5

    def test_7_get_public_course_topics_hierarchy_without_auth(self) -> None:
        """Verify GET /courses/{course_code}/topics is completely public and returns sanitized syllabus hierarchy."""
        with TestClient(app) as client:
            # Seed syllabus on course
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "syllabus.pdf",
                "stored_filename": "stored_syllabus.pdf",
                "source_type": "syllabus",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/syllabus.pdf",
                "processing_status": "processed",
            })
            mat_id = str(mat_res.inserted_id)

            text = """
Unit 1: Relational Model
Relational Concepts: Domains, Tuples.
Unit 2: Query Processing
Query Optimization: Heuristics, Cost Estimation.
"""
            self.mock_extracted_coll.insert_many([
                {"material_id": mat_id, "course_code": "BCSE301", "page_number": 1, "text": text, "extraction_method": "pymupdf", "char_count": len(text)}
            ])

            client.post(f"/dev/materials/{mat_id}/analyze-syllabus", headers=self.auth_headers)

            # Public student request (no Authorization header)
            res = client.get("/courses/BCSE301/topics")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["course_name"], "Database Management Systems")
            self.assertEqual(len(data["units"]), 2)
            self.assertEqual(data["units"][0]["unit_number"], 1)
            self.assertIn("Relational Model", data["units"][0]["unit_name"])
            self.assertIn("topics", data["units"][0])
            self.assertNotIn("_id", data)
            self.assertNotIn("storage_path", data)

    def test_8_get_topics_for_nonexistent_course_returns_404(self) -> None:
        """Verify GET /courses/{course_code}/topics returns 404 for unknown course."""
        with TestClient(app) as client:
            res = client.get("/courses/NONEXISTENT999/topics")
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
