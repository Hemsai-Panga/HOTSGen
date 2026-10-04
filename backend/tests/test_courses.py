"""Automated test suite for Course Management (Phase 3)."""

import unittest
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.course import CourseInDB


class InMemoryCoursesCollection:
    """Mock in-memory collection simulating MongoDB courses collection for isolated testing."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    def insert_one(self, doc: Dict[str, Any]) -> Any:
        code = doc.get("course_code")
        if code in self.docs:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError(f"Duplicate key: {code}")
        doc_copy = dict(doc)
        _id = ObjectId()
        doc_copy["_id"] = _id
        self.docs[code] = doc_copy

        class InsertResult:
            def __init__(self, inserted_id: ObjectId):
                self.inserted_id = inserted_id

        return InsertResult(_id)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "course_code" in query:
            code = query["course_code"]
            if code in self.docs:
                return dict(self.docs[code])
        if "_id" in query:
            _id = query["_id"]
            for d in self.docs.values():
                if d.get("_id") == _id:
                    return dict(d)
        return None

    def find(self, query: Dict[str, Any] = None) -> Any:
        results = [dict(d) for d in self.docs.values()]

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

        return Cursor(results)

    def find_one_and_update(
        self,
        query: Dict[str, Any],
        update: Dict[str, Any],
        return_document: bool = True,
    ) -> Optional[Dict[str, Any]]:
        code = query.get("course_code")
        if code in self.docs:
            if "$set" in update:
                self.docs[code].update(update["$set"])
            return dict(self.docs[code])
        return None

    def delete_one(self, query: Dict[str, Any]) -> Any:
        code = query.get("course_code")
        deleted = 0
        if code in self.docs:
            del self.docs[code]
            deleted = 1

        class DeleteResult:
            def __init__(self, count: int):
                self.deleted_count = count

        return DeleteResult(deleted)


class TestCourseManagement(unittest.TestCase):
    """Test suite covering all Course Management endpoints and security rules."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up admin credentials and developer token for testing."""
        cls.test_username = "course_admin"
        cls.test_password = "AdminCoursePassword123!"
        cls.test_password_hash = hash_password(cls.test_password)

        settings = get_settings()
        settings.ADMIN_USERNAME = cls.test_username
        settings.ADMIN_PASSWORD_HASH = cls.test_password_hash

        cls.dev_token = create_access_token(subject=cls.test_username, role="developer")
        cls.auth_headers = {"Authorization": f"Bearer {cls.dev_token}"}

    def setUp(self) -> None:
        """Patch database collection with in-memory collection for isolated testing."""
        from unittest.mock import patch
        self.mock_coll = InMemoryCoursesCollection()
        self.patcher = patch("app.repositories.course_repository.get_courses_collection", return_value=self.mock_coll)
        self.patcher.start()

    def tearDown(self) -> None:
        """Stop patches and clean up."""
        self.patcher.stop()

    def test_1_create_course_without_jwt_rejected(self) -> None:
        """Verify POST /dev/courses requires developer authentication."""
        with TestClient(app) as client:
            res = client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "Database Management Systems",
                "description": "Core DB course",
            })
            self.assertEqual(res.status_code, 401)

    def test_2_create_course_with_valid_jwt_success(self) -> None:
        """Verify POST /dev/courses creates course successfully with valid JWT."""
        with TestClient(app) as client:
            res = client.post("/dev/courses", json={
                "course_code": "bcse301",  # lowercase to test normalization
                "course_name": "Database Management Systems",
                "description": "Relational DB, SQL, and indexing",
            }, headers=self.auth_headers)
            self.assertEqual(res.status_code, 201)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["course_name"], "Database Management Systems")
            self.assertIn("created_at", data)
            self.assertIn("id", data)

    def test_3_create_duplicate_course_rejected(self) -> None:
        """Verify POST /dev/courses rejects duplicate course_code with 409 Conflict."""
        with TestClient(app) as client:
            # First creation
            res1 = client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "Database Management Systems",
            }, headers=self.auth_headers)
            self.assertEqual(res1.status_code, 201)

            # Duplicate creation
            res2 = client.post("/dev/courses", json={
                "course_code": "bcse301",  # lowercase duplicate
                "course_name": "Duplicate DBMS",
            }, headers=self.auth_headers)
            self.assertEqual(res2.status_code, 409)
            self.assertIn("already exists", res2.json()["detail"])

    def test_4_list_developer_courses_success(self) -> None:
        """Verify GET /dev/courses lists courses with admin metadata."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "DBMS",
            }, headers=self.auth_headers)
            client.post("/dev/courses", json={
                "course_code": "BCSE302",
                "course_name": "Operating Systems",
            }, headers=self.auth_headers)

            res = client.get("/dev/courses", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            courses = res.json()
            self.assertEqual(len(courses), 2)
            codes = [c["course_code"] for c in courses]
            self.assertIn("BCSE301", codes)
            self.assertIn("BCSE302", codes)
            self.assertIn("id", courses[0])
            self.assertIn("created_at", courses[0])

    def test_5_get_developer_course_success(self) -> None:
        """Verify GET /dev/courses/{course_code} returns specific course."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "DBMS",
                "description": "Full DB Course",
            }, headers=self.auth_headers)

            res = client.get("/dev/courses/bcse301", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["course_name"], "DBMS")
            self.assertEqual(data["description"], "Full DB Course")

    def test_6_update_course_success(self) -> None:
        """Verify PUT /dev/courses/{course_code} updates course name and description."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "Original Name",
                "description": "Original Description",
            }, headers=self.auth_headers)

            res = client.put("/dev/courses/BCSE301", json={
                "course_name": "Updated DBMS Name",
                "description": "Updated Description",
            }, headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["course_name"], "Updated DBMS Name")
            self.assertEqual(data["description"], "Updated Description")

    def test_7_attempt_to_change_course_code_not_allowed(self) -> None:
        """Verify PUT /dev/courses/{course_code} does not allow altering course_code."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "DBMS",
            }, headers=self.auth_headers)

            # Attempting to send course_code in body
            res = client.put("/dev/courses/BCSE301", json={
                "course_code": "NEWCODE999",
                "course_name": "DBMS Renamed",
            }, headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")  # Remains BCSE301

    def test_8_delete_course_success(self) -> None:
        """Verify DELETE /dev/courses/{course_code} safely deletes course."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "DBMS",
            }, headers=self.auth_headers)

            res = client.delete("/dev/courses/BCSE301", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            self.assertIn("deleted successfully", res.json()["message"])

            # Verify it's gone
            get_res = client.get("/dev/courses/BCSE301", headers=self.auth_headers)
            self.assertEqual(get_res.status_code, 404)

    def test_9_get_public_courses_without_auth_success(self) -> None:
        """Verify GET /courses is completely public and returns sanitized list."""
        with TestClient(app) as client:
            # Seed via developer route
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "DBMS",
                "description": "Database Systems",
            }, headers=self.auth_headers)

            # Access as public student (no headers)
            res = client.get("/courses")
            self.assertEqual(res.status_code, 200)
            courses = res.json()
            self.assertEqual(len(courses), 1)
            self.assertEqual(courses[0]["course_code"], "BCSE301")
            self.assertEqual(courses[0]["course_name"], "DBMS")

    def test_10_get_public_course_detail_without_auth_success(self) -> None:
        """Verify GET /courses/{course_code} is public and returns syllabus info."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "Database Management Systems",
                "description": "Public syllabus description",
            }, headers=self.auth_headers)

            res = client.get("/courses/bcse301")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["course_code"], "BCSE301")
            self.assertEqual(data["course_name"], "Database Management Systems")
            self.assertEqual(data["description"], "Public syllabus description")
            self.assertIn("units", data)

    def test_11_public_response_does_not_expose_internal_fields(self) -> None:
        """Verify student responses do NOT leak internal IDs or timestamps."""
        with TestClient(app) as client:
            client.post("/dev/courses", json={
                "course_code": "BCSE301",
                "course_name": "DBMS",
            }, headers=self.auth_headers)

            res = client.get("/courses/BCSE301")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertNotIn("id", data)
            self.assertNotIn("_id", data)
            self.assertNotIn("created_at", data)
            self.assertNotIn("updated_at", data)

    def test_12_get_nonexistent_course_returns_404(self) -> None:
        """Verify 404 is returned for non-existent courses on both public and dev endpoints."""
        with TestClient(app) as client:
            # Public
            res_pub = client.get("/courses/NONEXISTENT999")
            self.assertEqual(res_pub.status_code, 404)
            self.assertIn("not found", res_pub.json()["detail"].lower())

            # Developer
            res_dev = client.get("/dev/courses/NONEXISTENT999", headers=self.auth_headers)
            self.assertEqual(res_dev.status_code, 404)
            self.assertIn("not found", res_dev.json()["detail"].lower())

    def test_14_database_unavailable_returns_503_on_create(self) -> None:
        """Verify POST /dev/courses returns 503 instead of 409 Conflict when database is unavailable."""
        from unittest.mock import patch
        with patch("app.repositories.course_repository.get_courses_collection", return_value=None):
            with TestClient(app) as client:
                res = client.post("/dev/courses", json={
                    "course_code": "BACSE202",
                    "course_name": "Advanced Operating Systems",
                }, headers=self.auth_headers)
                self.assertEqual(res.status_code, 503)
                self.assertIn("database service unavailable", res.json()["detail"].lower())

    def test_15_database_unavailable_returns_503_on_list(self) -> None:
        """Verify GET /dev/courses and GET /courses return 503 instead of empty list when database is unavailable."""
        from unittest.mock import patch
        with patch("app.repositories.course_repository.get_courses_collection", return_value=None):
            with TestClient(app) as client:
                # Dev list
                res_dev = client.get("/dev/courses", headers=self.auth_headers)
                self.assertEqual(res_dev.status_code, 503)
                self.assertIn("database service unavailable", res_dev.json()["detail"].lower())

                # Public list
                res_pub = client.get("/courses")
                self.assertEqual(res_pub.status_code, 503)
                self.assertIn("database service unavailable", res_pub.json()["detail"].lower())

    def test_16_database_unavailable_returns_503_on_get(self) -> None:
        """Verify GET /dev/courses/{code} and GET /courses/{code} return 503 when database is unavailable."""
        from unittest.mock import patch
        with patch("app.repositories.course_repository.get_courses_collection", return_value=None):
            with TestClient(app) as client:
                res_dev = client.get("/dev/courses/BACSE202", headers=self.auth_headers)
                self.assertEqual(res_dev.status_code, 503)

                res_pub = client.get("/courses/BACSE202")
                self.assertEqual(res_pub.status_code, 503)


if __name__ == "__main__":
    unittest.main()
