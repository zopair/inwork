from app.matching import rank_jobs


def test_language_gate_blocks_english_only_job():
    profile = {"skills": ["تواصل"], "languages": ["عربي"], "work_modes": ["من البيت"]}
    jobs = [{"id": "en", "title": "English", "skills": ["تواصل"], "languages": ["إنجليزي"], "modes": ["من البيت"]}]
    assert rank_jobs(profile, jobs) == []


def test_matching_is_explainable_and_deterministic():
    profile = {"skills": ["Excel"], "languages": ["عربي"], "work_modes": ["من البيت"]}
    jobs = [{"id": "a", "title": "Data", "skills": ["Excel"], "languages": ["عربي"], "modes": ["من البيت"], "remote": True}]
    result = rank_jobs(profile, jobs)
    assert result[0]["id"] == "a"
    assert result[0]["score"] > 0
    assert result[0]["reason"]
