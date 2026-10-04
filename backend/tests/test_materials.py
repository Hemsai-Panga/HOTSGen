"""Automated test suite for Developer Material Management & Drop Box (Phase 4)."""

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.course import CourseInDB


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

    def find(self, query: Dict[str, Any] = None) -> Any:
        items = list(self.docs.values())
        if query and "course_code" in query:
            code = query["course_code"]
            items = [d for d in items if d.get("course_code") == code]

        class Cursor:
            def __init__(self, items: List[Dict[str, Any]]):
                self.items = [dict(i) for i in items]

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

    def delete_one(self, query: Dict[str, Any]) -> Any:
        deleted = 0
        if "_id" in query:
            _id = query["_id"]
            for k, d in list(self.docs.items()):
                if d.get("_id") == _id:
                    del self.docs[k]
                    deleted = 1

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(deleted)


class TestMaterialManagement(unittest.TestCase):
    """Test suite covering material upload, storage safety, and lifecycle management."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up admin credentials, developer token, and temporary storage directory."""
        cls.test_username = "material_admin"
        cls.test_password = "SecureMaterialPass123!"
        cls.test_password_hash = hash_password(cls.test_password)

        settings = get_settings()
        settings.ADMIN_USERNAME = cls.test_username
        settings.ADMIN_PASSWORD_HASH = cls.test_password_hash

        # Temporary storage directory for test isolation
        cls.temp_storage = tempfile.mkdtemp(prefix="hots_test_storage_")
        settings.EXTERNAL_STORAGE_PATH = cls.temp_storage

        cls.dev_token = create_access_token(subject=cls.test_username, role="developer")
        cls.auth_headers = {"Authorization": f"Bearer {cls.dev_token}"}

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up temporary test storage directory."""
        if os.path.exists(cls.temp_storage):
            shutil.rmtree(cls.temp_storage, ignore_errors=True)

    def setUp(self) -> None:
        """Patch database collections and course mock."""
        from unittest.mock import patch
        self.mock_materials_coll = InMemoryMaterialsCollection()
        self.patcher_mat = patch(
            "app.repositories.material_repository.get_materials_collection",
            return_value=self.mock_materials_coll,
        )
        self.patcher_mat.start()

        # Mock CourseRepository.get_course to return a valid course for "BCSE301"
        self.sample_course = CourseInDB(
            id=str(ObjectId()),
            course_code="BCSE301",
            course_name="Database Management Systems",
        )
        self.patcher_course = patch(
            "app.repositories.course_repository.CourseRepository.get_course",
            side_effect=lambda code: self.sample_course if code.strip().upper() == "BCSE301" else None,
        )
        self.patcher_course.start()

    def tearDown(self) -> None:
        """Stop patches."""
        self.patcher_mat.stop()
        self.patcher_course.stop()

    def test_1_upload_unauthenticated_rejected(self) -> None:
        """Verify POST /dev/materials requires developer authentication."""
        with TestClient(app) as client:
            file_content = b"PDF dummy content"
            files = {"file": ("syllabus.pdf", io.BytesIO(file_content), "application/pdf")}
            data = {"course_code": "BCSE301", "source_type": "syllabus"}

            res = client.post("/dev/materials", data=data, files=files)
            self.assertEqual(res.status_code, 401)

    def test_2_upload_authenticated_success(self) -> None:
        """Verify POST /dev/materials successfully saves file and records metadata."""
        with TestClient(app) as client:
            file_content = b"%PDF-1.4 Dummy Syllabus Content for DBMS"
            files = {"file": ("syllabus.pdf", io.BytesIO(file_content), "application/pdf")}
            data = {"course_code": "bcse301", "source_type": "syllabus"}

            res = client.post("/dev/materials", data=data, files=files, headers=self.auth_headers)
            self.assertEqual(res.status_code, 201)
            result = res.json()
            self.assertEqual(result["course_code"], "BCSE301")
            self.assertEqual(result["original_filename"], "syllabus.pdf")
            self.assertEqual(result["file_type"], "pdf")
            self.assertEqual(result["source_type"], "syllabus")
            self.assertEqual(result["processing_status"], "uploaded")
            self.assertEqual(result["file_size_bytes"], len(file_content))
            self.assertIn("id", result)

            # Check that file actually exists in storage
            course_dir = Path(self.temp_storage) / "BCSE301"
            self.assertTrue(course_dir.exists())
            stored_files = list(course_dir.glob("*_syllabus.pdf"))
            self.assertEqual(len(stored_files), 1)
            self.assertEqual(stored_files[0].read_bytes(), file_content)

    def test_3_upload_nonexistent_course_rejected(self) -> None:
        """Verify upload is rejected with 404 when course does not exist."""
        with TestClient(app) as client:
            files = {"file": ("lecture1.pptx", io.BytesIO(b"PPT content"), "application/vnd.ms-powerpoint")}
            data = {"course_code": "UNKNOWN999", "source_type": "lecture_material"}

            res = client.post("/dev/materials", data=data, files=files, headers=self.auth_headers)
            self.assertEqual(res.status_code, 404)
            self.assertIn("not found", res.json()["detail"].lower())

    def test_4_upload_unsupported_file_type_rejected(self) -> None:
        """Verify upload is rejected with 400 for unsupported file types (e.g., .exe, .zip)."""
        with TestClient(app) as client:
            files = {"file": ("malicious.exe", io.BytesIO(b"binary content"), "application/octet-stream")}
            data = {"course_code": "BCSE301", "source_type": "lecture_material"}

            res = client.post("/dev/materials", data=data, files=files, headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            self.assertIn("not supported", res.json()["detail"].lower())

    def test_4b_upload_legacy_ppt_rejected_with_conversion_hint(self) -> None:
        """Verify (ISSUE 2): Legacy binary .ppt uploads are rejected at upload time with conversion instructions."""
        with TestClient(app) as client:
            files = {"file": ("Module-1.ppt", io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1 legacy ppt"), "application/vnd.ms-powerpoint")}
            data = {"course_code": "BCSE301", "source_type": "lecture_material"}

            res = client.post("/dev/materials", data=data, files=files, headers=self.auth_headers)
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"].lower()
            self.assertIn("not supported", detail)
            self.assertIn("legacy binary '.ppt'", detail)
            self.assertIn("convert to '.pptx' or '.pdf'", detail)

    def test_5_upload_exam_paper_with_optional_metadata(self) -> None:
        """Verify upload for exam_paper accepts exam_type and year."""
        with TestClient(app) as client:
            files = {"file": ("CAT1_2024.pdf", io.BytesIO(b"Exam paper text"), "application/pdf")}
            data = {
                "course_code": "BCSE301",
                "source_type": "exam_paper",
                "exam_type": "CAT1",
                "year": "2024",
            }

            res = client.post("/dev/materials", data=data, files=files, headers=self.auth_headers)
            self.assertEqual(res.status_code, 201)
            result = res.json()
            self.assertEqual(result["source_type"], "exam_paper")
            self.assertEqual(result["exam_type"], "CAT1")
            self.assertEqual(result["year"], 2024)

    def test_6_upload_duplicate_material_rejected(self) -> None:
        """Verify duplicate filename in the same course returns 409 Conflict."""
        with TestClient(app) as client:
            files1 = {"file": ("unit1_notes.docx", io.BytesIO(b"Doc content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"course_code": "BCSE301", "source_type": "lecture_material"}

            res1 = client.post("/dev/materials", data=data, files=files1, headers=self.auth_headers)
            self.assertEqual(res1.status_code, 201)

            # Re-upload duplicate
            files2 = {"file": ("unit1_notes.docx", io.BytesIO(b"Doc content 2"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            res2 = client.post("/dev/materials", data=data, files=files2, headers=self.auth_headers)
            self.assertEqual(res2.status_code, 409)
            self.assertIn("already exists", res2.json()["detail"].lower())

    def test_7_list_materials_success(self) -> None:
        """Verify GET /dev/materials returns uploaded materials list."""
        with TestClient(app) as client:
            # Upload 2 materials
            f1 = {"file": ("doc1.pdf", io.BytesIO(b"Doc 1"), "application/pdf")}
            f2 = {"file": ("doc2.png", io.BytesIO(b"Image 2"), "image/png")}
            client.post("/dev/materials", data={"course_code": "BCSE301", "source_type": "syllabus"}, files=f1, headers=self.auth_headers)
            client.post("/dev/materials", data={"course_code": "BCSE301", "source_type": "reference_book"}, files=f2, headers=self.auth_headers)

            res = client.get("/dev/materials?course_code=BCSE301", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            materials = res.json()
            self.assertEqual(len(materials), 2)
            filenames = [m["original_filename"] for m in materials]
            self.assertIn("doc1.pdf", filenames)
            self.assertIn("doc2.png", filenames)

    def test_8_get_material_metadata_success(self) -> None:
        """Verify GET /dev/materials/{material_id} returns metadata."""
        with TestClient(app) as client:
            f = {"file": ("specific_doc.pdf", io.BytesIO(b"Sample Content"), "application/pdf")}
            up_res = client.post("/dev/materials", data={"course_code": "BCSE301", "source_type": "lecture_material"}, files=f, headers=self.auth_headers)
            self.assertEqual(up_res.status_code, 201)
            material_id = up_res.json()["id"]

            res = client.get(f"/dev/materials/{material_id}", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["id"], material_id)
            self.assertEqual(data["original_filename"], "specific_doc.pdf")

    def test_9_delete_material_removes_db_and_file(self) -> None:
        """Verify DELETE /dev/materials/{material_id} removes MongoDB document and file on disk."""
        with TestClient(app) as client:
            file_content = b"Content to be deleted"
            f = {"file": ("to_delete.pdf", io.BytesIO(file_content), "application/pdf")}
            up_res = client.post("/dev/materials", data={"course_code": "BCSE301", "source_type": "syllabus"}, files=f, headers=self.auth_headers)
            self.assertEqual(up_res.status_code, 201)
            material_id = up_res.json()["id"]
            stored_name = up_res.json()["stored_filename"]

            target_file = Path(self.temp_storage) / "BCSE301" / stored_name
            self.assertTrue(target_file.exists())

            # Delete
            del_res = client.delete(f"/dev/materials/{material_id}", headers=self.auth_headers)
            self.assertEqual(del_res.status_code, 200)
            self.assertIn("deleted successfully", del_res.json()["message"])

            # Verify file is deleted from disk
            self.assertFalse(target_file.exists())

            # Verify 404 on get
            get_res = client.get(f"/dev/materials/{material_id}", headers=self.auth_headers)
            self.assertEqual(get_res.status_code, 404)

    def test_10_no_public_materials_endpoint(self) -> None:
        """Verify there is no public /materials endpoint accessible by students."""
        with TestClient(app) as client:
            res = client.get("/materials")
            self.assertIn(res.status_code, [404, 405])


if __name__ == "__main__":
    unittest.main()
