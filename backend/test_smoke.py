import unittest

from app.main import frontend, health
from pathlib import Path


class InWorkApiSmokeTest(unittest.TestCase):
    def test_frontend_entrypoint(self):
        response = frontend()
        self.assertTrue(Path(response.path).is_file())
        self.assertIn("InWork", Path(response.path).read_text(encoding="utf-8"))

    def test_health(self):
        self.assertEqual(
            health(),
            {"ok": True, "service": "inwork-api", "version": "0.2.0"},
        )


if __name__ == "__main__":
    unittest.main()
