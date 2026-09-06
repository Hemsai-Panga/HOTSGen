"""Automated test suite for Developer Authentication (Phase 2B)."""

import unittest
from datetime import timedelta
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import app


class TestDeveloperAuth(unittest.TestCase):
    """Test suite verifying developer authentication and route protection."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test admin credentials for testing."""
        cls.test_username = "testadmin"
        cls.test_password = "SecureTestPassword123!"
        cls.test_password_hash = hash_password(cls.test_password)

        # Configure settings for test
        settings = get_settings()
        settings.ADMIN_USERNAME = cls.test_username
        settings.ADMIN_PASSWORD_HASH = cls.test_password_hash

    def test_public_routes_accessible_without_token(self) -> None:
        """Verify that root and health endpoints remain public."""
        with TestClient(app) as client:
            res_root = client.get("/")
            self.assertEqual(res_root.status_code, 200)
            self.assertEqual(res_root.json(), {"message": "HOTS RAG Backend is running"})

            # /health should be accessible without auth (status code 200 or 503 depending on DB reachability)
            res_health = client.get("/health")
            self.assertIn(res_health.status_code, [200, 503])
            self.assertIn("api", res_health.json())

    def test_login_invalid_credentials_rejected(self) -> None:
        """Verify that login fails with 401 when invalid credentials are provided."""
        with TestClient(app) as client:
            # Wrong password
            res1 = client.post("/auth/login", json={
                "username": self.test_username,
                "password": "WrongPassword!",
            })
            self.assertEqual(res1.status_code, 401)
            self.assertIn("Invalid username or password", res1.json()["detail"])

            # Non-existent user
            res2 = client.post("/auth/login", json={
                "username": "unknown_user",
                "password": self.test_password,
            })
            self.assertEqual(res2.status_code, 401)
            self.assertIn("Invalid username or password", res2.json()["detail"])

    def test_login_valid_credentials_returns_jwt(self) -> None:
        """Verify that valid login returns a valid JWT access token."""
        with TestClient(app) as client:
            res = client.post("/auth/login", json={
                "username": self.test_username,
                "password": self.test_password,
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("access_token", data)
            self.assertEqual(data.get("token_type"), "bearer")
            self.assertTrue(len(data["access_token"]) > 20)

    def test_dev_test_without_token_rejected(self) -> None:
        """Verify that /dev/test rejects requests with missing token."""
        with TestClient(app) as client:
            res = client.get("/dev/test")
            self.assertEqual(res.status_code, 401)
            self.assertIn("detail", res.json())

    def test_dev_test_with_invalid_token_rejected(self) -> None:
        """Verify that /dev/test rejects malformed / corrupted tokens."""
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer invalid.token.value"}
            res = client.get("/dev/test", headers=headers)
            self.assertEqual(res.status_code, 401)
            self.assertIn("Invalid authentication token", res.json()["detail"])

    def test_dev_test_with_expired_token_rejected(self) -> None:
        """Verify that /dev/test rejects expired tokens."""
        expired_token = create_access_token(
            subject=self.test_username,
            role="developer",
            expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
        )
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {expired_token}"}
            res = client.get("/dev/test", headers=headers)
            self.assertEqual(res.status_code, 401)
            self.assertIn("expired", res.json()["detail"].lower())

    def test_dev_test_with_wrong_role_rejected(self) -> None:
        """Verify that /dev/test rejects tokens that do not possess the 'developer' role."""
        wrong_role_token = create_access_token(
            subject="some_user",
            role="student",
        )
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {wrong_role_token}"}
            res = client.get("/dev/test", headers=headers)
            self.assertEqual(res.status_code, 403)
            self.assertIn("developer role required", res.json()["detail"].lower())

    def test_dev_test_with_valid_token_success(self) -> None:
        """Verify that /dev/test successfully grants access with valid developer JWT."""
        with TestClient(app) as client:
            # 1. Login
            login_res = client.post("/auth/login", json={
                "username": self.test_username,
                "password": self.test_password,
            })
            self.assertEqual(login_res.status_code, 200)
            token = login_res.json()["access_token"]

            # 2. Access protected route
            headers = {"Authorization": f"Bearer {token}"}
            res = client.get("/dev/test", headers=headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["developer"], self.test_username)
            self.assertEqual(data["role"], "developer")


if __name__ == "__main__":
    unittest.main()
