import os
import sqlite3
import unittest
from unittest.mock import patch

from app.marketplace import connect


class DatabaseModeTests(unittest.TestCase):
    def test_remote_turso_connection_is_selected_when_configured(self):
        fake = type("FakeConnection", (), {
            "row_factory": None,
            "in_transaction": False,
            "closed": False,
            "execute": lambda self, sql: self,
            "commit": lambda self: None,
            "rollback": lambda self: None,
            "close": lambda self: setattr(self, "closed", True),
        })()
        env = {
            "TURSO_DATABASE_URL": "libsql://inwork-test.turso.io",
            "TURSO_AUTH_TOKEN": "test-token",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("turso_serverless.connect", return_value=fake) as remote:
                with patch("app.marketplace.sqlite3.connect") as local:
                    with connect() as actual:
                        self.assertIs(actual, fake)
                        self.assertIs(actual.row_factory, sqlite3.Row)
                    remote.assert_called_once_with(
                        "libsql://inwork-test.turso.io",
                        auth_token="test-token",
                        isolation_level=None,
                    )
                    local.assert_not_called()
        self.assertTrue(fake.closed)

    def test_remote_database_is_required_when_host_policy_enables_it(self):
        with patch.dict(os.environ, {"INWORK_REQUIRE_REMOTE_DB": "true"}, clear=False):
            os.environ.pop("TURSO_DATABASE_URL", None)
            with self.assertRaisesRegex(RuntimeError, "TURSO_DATABASE_URL"):
                with connect():
                    pass

    def test_remote_turso_requires_auth_token(self):
        with patch.dict(os.environ, {"TURSO_DATABASE_URL": "libsql://inwork-test.turso.io"}, clear=False):
            os.environ.pop("TURSO_AUTH_TOKEN", None)
            with self.assertRaisesRegex(RuntimeError, "TURSO_AUTH_TOKEN"):
                with connect():
                    pass


if __name__ == "__main__":
    unittest.main()
