"""Automated test suite for CAT/FAT Exam Question Extraction and Structuring (Phase 8)."""

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
from app.models.teaching_question import DifficultyLevel, ExamType, TeachingQuestionInDB
from app.repositories.course_repository import CourseRepository
from app.repositories.extracted_content_repository import ExtractedContentRepository
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


class InMemoryTeachingQuestionsCollection:
    """Mock in-memory collection simulating MongoDB teaching_questions collection."""

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
            if "source_material_id" in query:
                items = [d for d in items if d.get("source_material_id") == query["source_material_id"]]
            if "course_code" in query:
                items = [d for d in items if d.get("course_code") == query["course_code"]]
            if "exam_type" in query:
                items = [d for d in items if d.get("exam_type") == query["exam_type"]]
            if "topic" in query:
                items = [d for d in items if d.get("topic") == query["topic"]]
            if "topic_id" in query:
                items = [d for d in items if d.get("topic_id") == query["topic_id"]]

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

    def delete_one(self, query: Dict[str, Any]) -> Any:
        deleted = 0
        if "_id" in query:
            _id = query["_id"]
            for k, d in list(self.docs.items()):
                if d.get("_id") == _id:
                    del self.docs[k]
                    deleted = 1
                    break

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(deleted)

    def delete_many(self, query: Dict[str, Any]) -> Any:
        deleted = 0
        if "source_material_id" in query:
            mat_id = query["source_material_id"]
            for k, d in list(self.docs.items()):
                if d.get("source_material_id") == mat_id:
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


class TestTeachingQuestions(unittest.TestCase):
    """Test suite covering Phase 8 Exam Question Extraction and Structuring."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up admin credentials and developer token."""
        cls.test_username = "exam_admin"
        cls.test_password = "SecureExamPassword123!"
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
        self.mock_tq_coll = InMemoryTeachingQuestionsCollection()

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
        self.patcher_tq = patch(
            "app.repositories.teaching_question_repository.get_teaching_questions_collection",
            return_value=self.mock_tq_coll,
        )

        self.patcher_course.start()
        self.patcher_mat.start()
        self.patcher_ext.start()
        self.patcher_tq.start()

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
        self.patcher_tq.stop()

    def test_1_extract_unauthenticated_rejected(self) -> None:
        """Verify POST /dev/materials/{material_id}/extract-questions requires developer authentication."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/extract-questions")
            self.assertEqual(res.status_code, 401)

    def test_2_get_questions_unauthenticated_rejected(self) -> None:
        """Verify GET /dev/materials/{material_id}/questions requires developer authentication."""
        with TestClient(app) as client:
            res = client.get("/dev/materials/6a9cf9648fe403384c67ab2a/questions")
            self.assertEqual(res.status_code, 401)

    def test_3_delete_questions_unauthenticated_rejected(self) -> None:
        """Verify DELETE /dev/materials/{material_id}/questions requires developer authentication."""
        with TestClient(app) as client:
            res = client.delete("/dev/materials/6a9cf9648fe403384c67ab2a/questions")
            self.assertEqual(res.status_code, 401)

    def test_4_extract_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when material does not exist."""
        with TestClient(app) as client:
            res = client.post("/dev/materials/6a9cf9648fe403384c67ab2a/extract-questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_5_get_questions_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when viewing questions for nonexistent material."""
        with TestClient(app) as client:
            res = client.get("/dev/materials/6a9cf9648fe403384c67ab2a/questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_6_delete_questions_nonexistent_material_returns_404(self) -> None:
        """Verify 404 is returned when deleting questions for nonexistent material."""
        with TestClient(app) as client:
            res = client.delete("/dev/materials/6a9cf9648fe403384c67ab2a/questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_7_extract_non_exam_paper_rejected(self) -> None:
        """Verify 400 is returned when material source_type is not 'exam_paper'."""
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

            res = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("only materials of source_type 'exam_paper'", res.json()["detail"].lower())

    def test_8_extract_unprocessed_exam_paper_rejected(self) -> None:
        """Verify 400 is returned when exam paper has not been processed for text extraction."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "cat1_2023.pdf",
                "stored_filename": "stored_cat1.pdf",
                "source_type": "exam_paper",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/cat1_2023.pdf",
                "processing_status": "uploaded",
                "exam_type": "CAT1",
                "year": 2023,
            })
            mat_id = str(mat_res.inserted_id)

            res = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("no extracted content records", res.json()["detail"].lower())

    def test_9_extract_cat1_exam_paper_success(self) -> None:
        """Verify CAT1 exam paper extraction parses numbered questions, subquestions, marks, and aligns to syllabus."""
        with TestClient(app) as client:
            # 1. Seed exam paper material
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "bcse301_cat1_2023.pdf",
                "stored_filename": "stored_bcse301_cat1.pdf",
                "source_type": "exam_paper",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/bcse301_cat1_2023.pdf",
                "processing_status": "processed",
                "exam_type": "CAT1",
                "year": 2023,
            })
            mat_id = str(mat_res.inserted_id)

            # 2. Seed extracted paper text
            paper_text = """
VELLORE INSTITUTE OF TECHNOLOGY
CONTINUOUS ASSESSMENT TEST - 1 (CAT-1)
Course Code: BCSE301 - Database Management Systems
Duration: 90 Mins    Max Marks: 50

1. Define relational integrity constraints and discuss domain constraints with examples. [5 Marks]

2. Consider the relational schema R(A, B, C, D) and functional dependencies F = {A -> B, B -> C}.
(a) Compute the closure of attribute set {A}. (5 Marks)
(b) Determine whether the decomposition into R1(A, B) and R2(B, C, D) is lossless join. [5 Marks]

3. Write SQL Queries for a university database:
(a) Find student names enrolled in DBMS course using DML Statements and Subqueries. [5 Marks]
(b) Calculate the average grade using Group By aggregation functions. [5 Marks]
"""
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": paper_text,
                    "extraction_method": "pymupdf",
                    "char_count": len(paper_text),
                }
            ])

            # 3. Trigger question extraction
            res = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["material_id"], mat_id)
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["exam_type"], "CAT1")
            self.assertEqual(data["year"], 2023)
            self.assertEqual(data["questions_extracted"], 3)
            self.assertEqual(data["status"], "completed")

            # 4. Verify questions via GET /dev/materials/{material_id}/questions
            get_res = client.get(f"/dev/materials/{mat_id}/questions", headers=self.auth_headers)
            self.assertEqual(get_res.status_code, 200)
            detail = get_res.json()
            self.assertEqual(detail["total_questions"], 3)

            q1 = detail["questions"][0]
            self.assertEqual(q1["question_number"], "1")
            self.assertEqual(q1["marks"], 5)
            self.assertEqual(q1["difficulty"], "easy")
            self.assertEqual(q1["exam_type"], "CAT1")

            q2 = detail["questions"][1]
            self.assertEqual(q2["question_number"], "2")
            self.assertEqual(q2["marks"], 10)
            self.assertIsNotNone(q2["subquestions"])
            self.assertEqual(len(q2["subquestions"]), 2)
            self.assertIn("(a)", q2["subquestions"][0])
            self.assertEqual(q2["unit_id"], "BCSE301_U2")
            self.assertEqual(q2["topic_id"], "BCSE301_U2_T1")

            q3 = detail["questions"][2]
            self.assertEqual(q3["question_number"], "3")
            self.assertEqual(q3["marks"], 10)
            self.assertEqual(q3["unit_id"], "BCSE301_U1")
            self.assertEqual(q3["topic_id"], "BCSE301_U1_T2")

    def test_10_extract_fat_paper_with_sections_and_mcqs(self) -> None:
        """Verify FAT exam paper extraction handles sections (Part A, Part B), MCQs, and design questions."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "fat_dbms_2024.pdf",
                "stored_filename": "stored_fat_dbms.pdf",
                "source_type": "exam_paper",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/fat_dbms_2024.pdf",
                "processing_status": "processed",
                "exam_type": "FAT",
                "year": 2024,
            })
            mat_id = str(mat_res.inserted_id)

            fat_text = """
FINAL ASSESSMENT TEST (FAT) - WINTER 2023-2024
Max Marks: 100

PART - A

1. Which normal form strictly eliminates multivalued dependencies? (A) 1NF (B) 2NF (C) 3NF (D) 4NF [2 Marks]

2. What is the fundamental difference between Primary Key and Unique Key constraints? [3 Marks]

SECTION - B

3. Design an ER diagram and relational schema for a hospital management database with doctors, patients, and appointments. Construct the tables and state key integrity constraints. [15 Marks]

4. Normalize the following relation into Boyce-Codd Normal Form BCNF and explain the decomposition algorithm. [15 Marks]
"""
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": fat_text,
                    "extraction_method": "pymupdf",
                    "char_count": len(fat_text),
                }
            ])

            res = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["questions_extracted"], 4)

            detail_res = client.get(f"/dev/materials/{mat_id}/questions", headers=self.auth_headers)
            questions = detail_res.json()["questions"]

            # MCQ question
            mcq_q = questions[0]
            self.assertEqual(mcq_q["section"], "Part A")
            self.assertEqual(mcq_q["marks"], 2)
            self.assertEqual(mcq_q["question_type"], "mcq")
            self.assertEqual(mcq_q["difficulty"], "easy")

            # High mark design question
            design_q = questions[2]
            self.assertEqual(design_q["section"], "Part B")
            self.assertEqual(design_q["marks"], 15)
            self.assertEqual(design_q["question_type"], "design")
            self.assertEqual(design_q["difficulty"], "hard")

            # Normalization question
            bcnf_q = questions[3]
            self.assertEqual(bcnf_q["section"], "Part B")
            self.assertEqual(bcnf_q["marks"], 15)
            self.assertEqual(bcnf_q["difficulty"], "hard")
            self.assertEqual(bcnf_q["unit_id"], "BCSE301_U2")
            self.assertEqual(bcnf_q["topic_id"], "BCSE301_U2_T2")

    def test_11_imperfect_ocr_exam_paper_text(self) -> None:
        """Verify noisy OCR text with line breaks and varied headers extracts cleanly."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "scanned_cat2.png",
                "stored_filename": "stored_scanned_cat2.png",
                "source_type": "exam_paper",
                "file_type": "png",
                "storage_path": "./storage/BCSE301/scanned_cat2.png",
                "processing_status": "processed",
                "exam_type": "CAT2",
                "year": 2022,
            })
            mat_id = str(mat_res.inserted_id)

            ocr_noisy_text = """
   VELLORE INSTITUTE OF TECHNOLOGY   
   SCHOOL OF COMPUTER SCIENCE   
   CONTINUOUS ASSESSMENT TEST - 2 (CAT-2) - FALL 2022   
   Reg. No.: 21BCE1001   Slot: B1   
   Course Code: BCSE301   Course Name: DBMS   
   
   Q. 1 Explain the two-phase locking protocol and discuss how it ensures conflict serializability. [10 Marks]
   
   Q. 2 Consider a scenario where multiple transactions execute concurrently.
   (a) Describe the lost update problem. (5M)
   (b) How does timestamp ordering prevent deadlocks? (5M)
"""
            self.mock_extracted_coll.insert_many([
                {
                    "material_id": mat_id,
                    "course_code": "BCSE301",
                    "page_number": 1,
                    "text": ocr_noisy_text,
                    "extraction_method": "tesseract",
                    "char_count": len(ocr_noisy_text),
                }
            ])

            res = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["questions_extracted"], 2)
            self.assertEqual(data["exam_type"], "CAT2")

            questions = data["questions"]
            self.assertEqual(questions[0]["marks"], 10)
            self.assertEqual(questions[1]["marks"], 10)
            self.assertEqual(len(questions[1]["subquestions"]), 2)

    def test_12_idempotent_re_extraction_no_duplicates(self) -> None:
        """Verify re-extracting an exam paper replaces old question records without duplication."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "exam_reextract.pdf",
                "stored_filename": "stored_exam_reextract.pdf",
                "source_type": "exam_paper",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/exam.pdf",
                "processing_status": "processed",
                "exam_type": "CAT1",
                "year": 2023,
            })
            mat_id = str(mat_res.inserted_id)

            text = "1. Explain Relational Algebra Operations: Selection and Projection joins. [10 Marks]"
            self.mock_extracted_coll.insert_many([
                {"material_id": mat_id, "course_code": "BCSE301", "page_number": 1, "text": text, "extraction_method": "pymupdf", "char_count": len(text)}
            ])

            # First extraction
            res1 = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(len(TeachingQuestionRepository.get_questions_by_material(mat_id)), 1)

            # Re-extraction
            res2 = client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(len(TeachingQuestionRepository.get_questions_by_material(mat_id)), 1)

    def test_13_delete_material_questions_endpoint(self) -> None:
        """Verify DELETE /dev/materials/{material_id}/questions deletes all questions for that material."""
        with TestClient(app) as client:
            mat_res = self.mock_materials_coll.insert_one({
                "course_code": "BCSE301",
                "original_filename": "exam_to_delete.pdf",
                "stored_filename": "stored_exam_to_delete.pdf",
                "source_type": "exam_paper",
                "file_type": "pdf",
                "storage_path": "./storage/BCSE301/exam.pdf",
                "processing_status": "processed",
                "exam_type": "FAT",
                "year": 2023,
            })
            mat_id = str(mat_res.inserted_id)

            text = "1. Write SQL Queries using DDL and DML statements. [10 Marks]"
            self.mock_extracted_coll.insert_many([
                {"material_id": mat_id, "course_code": "BCSE301", "page_number": 1, "text": text, "extraction_method": "pymupdf", "char_count": len(text)}
            ])

            client.post(f"/dev/materials/{mat_id}/extract-questions", headers=self.auth_headers)
            self.assertEqual(len(TeachingQuestionRepository.get_questions_by_material(mat_id)), 1)

            # Delete questions
            del_res = client.delete(f"/dev/materials/{mat_id}/questions", headers=self.auth_headers)
            self.assertEqual(del_res.status_code, 200)
            self.assertEqual(del_res.json()["status"], "success")
            self.assertEqual(del_res.json()["deleted_count"], 1)

            # Verify empty list returned
            get_res = client.get(f"/dev/materials/{mat_id}/questions", headers=self.auth_headers)
            self.assertEqual(get_res.status_code, 200)
            self.assertEqual(get_res.json()["total_questions"], 0)


if __name__ == "__main__":
    unittest.main()
