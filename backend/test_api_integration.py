import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from app import api
from app.main import app
from app.marketplace import connect, utc_now


class MarketplaceApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "api.sqlite3")
        self.previous_db_path = api.DB_PATH
        api.DB_PATH = self.db_path
        self.client = TestClient(app)
        self.client.__enter__()
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO categories (id,name_ar,created_at) VALUES (1,'كهربائي',?)",
                (utc_now(),),
            )

    def tearDown(self):
        self.client.__exit__(None, None, None)
        api.DB_PATH = self.previous_db_path
        self.temp_dir.cleanup()

    def register(self, email, role, category_id=None):
        return self.client.post(
            "/v1/auth/register",
            headers={"X-InWork-Request": "1"},
            json={
                "email": email,
                "password": "Correct-Horse-Battery-12!",
                "display_name": email.split("@")[0],
                "role": role,
                "category_id": category_id,
            },
        )

    def test_authentication_required_and_admin_self_signup_blocked(self):
        self.assertEqual(self.client.get("/v1/requests/mine").status_code, 401)
        self.assertEqual(
            self.client.get("/v1/workers/search?category_id=1&latitude=30&longitude=31").status_code,
            401,
        )
        self.assertEqual(self.register("admin@example.test", "admin").status_code, 400)
        self.assertEqual(
            self.client.post("/v1/auth/register", json={
                "email": "no-csrf@example.test",
                "password": "Correct-Horse-Battery-12!",
                "display_name": "No CSRF",
                "role": "requester",
            }).status_code,
            403,
        )

    def test_admin_bootstrap_is_one_time_and_admin_controls_categories(self):
        token = "one-time-bootstrap-secret-value-123456"
        with patch.dict("os.environ", {"INWORK_ADMIN_BOOTSTRAP_TOKEN": token}):
            response = self.client.post(
                "/v1/admin/bootstrap", headers={"X-InWork-Request": "1"},
                json={"token": token, "email": "admin@example.test",
                      "password": "Admin-Strong-Password-2026!", "display_name": "مدير"})
            self.assertEqual(response.status_code, 200, response.text)
            second = self.client.post(
                "/v1/admin/bootstrap", headers={"X-InWork-Request": "1"},
                json={"token": token, "email": "other-admin@example.test",
                      "password": "Admin-Strong-Password-2026!", "display_name": "مدير آخر"})
            self.assertEqual(second.status_code, 409)
        login = self.client.post(
            "/v1/auth/login", headers={"X-InWork-Request": "1"},
            json={"email": "admin@example.test", "password": "Admin-Strong-Password-2026!"})
        self.assertEqual(login.status_code, 200, login.text)
        category = self.client.post(
            "/v1/admin/categories", headers={"X-InWork-Request": "1"},
            json={"name_ar": "سباك"})
        self.assertEqual(category.status_code, 200, category.text)
        self.assertEqual(category.json()["name_ar"], "سباك")

    def test_login_failures_are_rate_limited(self):
        self.register("lockout@example.test", "requester")
        for _ in range(5):
            response = self.client.post(
                "/v1/auth/login", headers={"X-InWork-Request": "1"},
                json={"email": "lockout@example.test", "password": "wrong-password"})
            self.assertEqual(response.status_code, 400)
        blocked = self.client.post(
            "/v1/auth/login", headers={"X-InWork-Request": "1"},
            json={"email": "lockout@example.test", "password": "Correct-Horse-Battery-12!"})
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("15 دقيقة", blocked.json()["detail"])

    def test_requester_worker_flow_and_contact_privacy(self):
        requester_client = TestClient(app)
        requester_client.__enter__()
        worker_client = TestClient(app)
        worker_client.__enter__()
        try:
            requester_response = requester_client.post(
                "/v1/auth/register",
                headers={"X-InWork-Request": "1"},
                json={"email": "requester@example.test", "password": "Correct-Horse-Battery-12!",
                      "display_name": "طالب الخدمة", "role": "requester"},
            )
            self.assertEqual(requester_response.status_code, 200, requester_response.text)
            requester_id = requester_response.json()["user"]["id"]

            worker_response = worker_client.post(
                "/v1/auth/register",
                headers={"X-InWork-Request": "1"},
                json={"email": "worker@example.test", "password": "Correct-Horse-Battery-12!",
                      "display_name": "الفني", "role": "worker", "category_id": 1},
            )
            self.assertEqual(worker_response.status_code, 200, worker_response.text)
            worker_id = worker_response.json()["user"]["id"]

            self.assertEqual(requester_client.put(
                "/v1/worker/profile", headers={"X-InWork-Request": "1"},
                json={"bio": "كهربائي منازل", "latitude": 30.0444, "longitude": 31.2357,
                      "available": True, "phone": "01000000000", "whatsapp": "01000000000"},
            ).status_code, 403)
            self.assertEqual(worker_client.put(
                "/v1/worker/profile", headers={"X-InWork-Request": "1"},
                json={"bio": "كهربائي منازل", "latitude": 30.0444, "longitude": 31.2357,
                      "available": True, "phone": "01000000000", "whatsapp": "01000000000"},
            ).status_code, 200)

            with connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO subscriptions
                       (worker_id,status,starts_at,ends_at,verified_by,verified_at,created_at)
                       VALUES (?,'active','2020-01-01T00:00:00+00:00',
                               '2999-01-01T00:00:00+00:00',NULL,?,?)""",
                    (worker_id, utc_now(), utc_now()),
                )

            created = requester_client.post(
                "/v1/requests", headers={"X-InWork-Request": "1"},
                json={"category_id": 1, "description": "إصلاح عطل كهربائي في المنزل",
                      "latitude": 30.045, "longitude": 31.236},
            )
            self.assertEqual(created.status_code, 200, created.text)
            request_id = created.json()["id"]

            public_workers = requester_client.get(
                "/v1/workers/search?category_id=1&latitude=30.0444&longitude=31.2357"
            ).json()["workers"]
            self.assertEqual(len(public_workers), 1)
            self.assertNotIn("phone", public_workers[0])
            self.assertNotIn("whatsapp", public_workers[0])
            self.assertNotEqual(public_workers[0]["latitude"], 30.0444)

            feed = worker_client.get("/v1/worker/requests")
            self.assertEqual(feed.status_code, 200, feed.text)
            self.assertEqual(feed.json()["requests"][0]["id"], request_id)
            accepted = worker_client.post(
                f"/v1/requests/{request_id}/accept", headers={"X-InWork-Request": "1"}
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)

            self.assertEqual(requester_client.get(f"/v1/requests/{request_id}/contact").status_code, 403)
            shared = requester_client.post(
                f"/v1/requests/{request_id}/share-contact", headers={"X-InWork-Request": "1"}
            )
            self.assertEqual(shared.status_code, 200, shared.text)
            contact = worker_client.get(f"/v1/requests/{request_id}/contact")
            self.assertEqual(contact.status_code, 200, contact.text)
            self.assertEqual(contact.json()["contact"]["whatsapp"], "01000000000")

            self.assertEqual(worker_client.post(
                f"/v1/requests/{request_id}/status", headers={"X-InWork-Request": "1"},
                json={"status": "in_progress"},
            ).status_code, 200)
            self.assertEqual(worker_client.post(
                f"/v1/requests/{request_id}/status", headers={"X-InWork-Request": "1"},
                json={"status": "completed"},
            ).status_code, 200)
            self.assertEqual(requester_client.get("/v1/requests/mine").json()["requests"][0]["status"], "completed")

            # Logout revokes the opaque server-side session, not just the browser cookie.
            self.assertEqual(requester_client.post(
                "/v1/auth/logout", headers={"X-InWork-Request": "1"}
            ).status_code, 200)
            self.assertEqual(requester_client.get("/v1/requests/mine").status_code, 401)
        finally:
            requester_client.__exit__(None, None, None)
            worker_client.__exit__(None, None, None)


if __name__ == "__main__":
    unittest.main()
