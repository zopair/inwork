import unittest

from app.main import health


class InWorkApiSmokeTest(unittest.TestCase):
    def test_health(self):
        self.assertEqual(
            health(),
            {"ok": True, "service": "inwork-api", "version": "0.2.0"},
        )


if __name__ == "__main__":
    unittest.main()
