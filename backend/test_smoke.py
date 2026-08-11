import unittest

from app.main import JOBS, Profile, health, jobs, match


class InWorkApiSmokeTest(unittest.TestCase):
    def test_health(self):
        self.assertEqual(health(), {"ok": True, "service": "inwork-api"})

    def test_jobs_catalog(self):
        payload = jobs()
        self.assertGreaterEqual(len(payload["jobs"]), 5)
        self.assertTrue(all(item["id"] for item in payload["jobs"]))

    def test_matching_prefers_relevant_job(self):
        profile = Profile(skills=["Excel", "كتابة"], languages=["عربي"], work_modes=["من البيت"])
        payload = match(profile)
        self.assertTrue(payload["results"])
        self.assertIn("إدخال بيانات", payload["results"][0]["title"])


if __name__ == "__main__":
    unittest.main()
