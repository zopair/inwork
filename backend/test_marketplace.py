import tempfile
import threading
import unittest
from pathlib import Path

from app.marketplace import (
    MarketplaceError,
    accept_request,
    connect,
    create_request,
    initialize_database,
    transition_request,
)


class MarketplaceDomainTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.sqlite3")
        initialize_database(self.db_path)
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO categories (id, name_ar, created_at) VALUES (1, 'كهربائي', '2026-01-01T00:00:00+00:00')"
            )
            for user_id, role in (
                ("requester-1", "requester"),
                ("worker-1", "worker"),
                ("worker-2", "worker"),
                ("wrong-role", "requester"),
            ):
                conn.execute(
                    "INSERT INTO users (id, role, display_name, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, role, user_id, "2026-01-01T00:00:00+00:00"),
                )
            for worker_id in ("worker-1", "worker-2"):
                conn.execute(
                    """INSERT INTO worker_profiles
                       (user_id, category_id, latitude, longitude, is_available, whatsapp_private, updated_at)
                       VALUES (?, 1, 30.0444, 31.2357, 1, 'PRIVATE_NUMBER', '2026-01-01T00:00:00+00:00')""",
                    (worker_id,),
                )
                conn.execute(
                    """INSERT INTO subscriptions
                       (worker_id, status, starts_at, ends_at, created_at)
                       VALUES (?, 'active', '2020-01-01T00:00:00+00:00',
                               '2999-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')""",
                    (worker_id,),
                )

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_request(self):
        return create_request(
            self.db_path, "requester-1", 1, "إصلاح عطل كهربائي", 30.0444, 31.2357
        )

    def test_request_requires_description_and_valid_requester(self):
        with self.assertRaises(MarketplaceError):
            create_request(self.db_path, "requester-1", 1, "   ", 30.0, 31.0)
        with self.assertRaises(MarketplaceError):
            create_request(self.db_path, "worker-1", 1, "إصلاح", 30.0, 31.0)

    def test_request_is_created_open(self):
        request_id = self.make_request()
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, worker_id FROM service_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        self.assertEqual(row["status"], "open")
        self.assertIsNone(row["worker_id"])

    def test_only_one_worker_can_accept_request(self):
        request_id = self.make_request()
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def claim(worker_id):
            try:
                barrier.wait()
                results.append(accept_request(self.db_path, worker_id, request_id))
            except Exception as exc:  # surfaced to the test thread
                errors.append(exc)

        threads = [
            threading.Thread(target=claim, args=("worker-1",)),
            threading.Thread(target=claim, args=("worker-2",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors, errors)
        self.assertEqual(sorted(results), [False, True])
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, worker_id FROM service_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        self.assertEqual(row["status"], "accepted")
        self.assertIn(row["worker_id"], ("worker-1", "worker-2"))

    def test_wrong_category_and_inactive_subscription_cannot_accept(self):
        request_id = self.make_request()
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO categories (id, name_ar, created_at) VALUES (2, 'سباك', '2026-01-01T00:00:00+00:00')"
            )
            conn.execute("UPDATE worker_profiles SET category_id = 2 WHERE user_id = 'worker-1'")
        self.assertFalse(accept_request(self.db_path, "worker-1", request_id))

        with connect(self.db_path) as conn:
            conn.execute("UPDATE worker_profiles SET category_id = 1 WHERE user_id = 'worker-1'")
            conn.execute("UPDATE subscriptions SET status = 'expired' WHERE worker_id = 'worker-1'")
        with self.assertRaises(MarketplaceError):
            accept_request(self.db_path, "worker-1", request_id)

    def test_only_assigned_worker_can_advance_lifecycle(self):
        request_id = self.make_request()
        self.assertTrue(accept_request(self.db_path, "worker-1", request_id))
        self.assertFalse(transition_request(self.db_path, request_id, "worker-2", "in_progress"))
        self.assertTrue(transition_request(self.db_path, request_id, "worker-1", "in_progress"))
        self.assertTrue(transition_request(self.db_path, request_id, "worker-1", "completed"))
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT status, completed_at FROM service_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        self.assertEqual(row["status"], "completed")
        self.assertIsNotNone(row["completed_at"])


if __name__ == "__main__":
    unittest.main()
