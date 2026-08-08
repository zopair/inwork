from __future__ import annotations

from typing import Any


def _norm(values: list[str] | None) -> set[str]:
    return {str(v).strip().casefold() for v in (values or []) if str(v).strip()}


def rank_jobs(profile: dict[str, Any], jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic, explainable matching with a strict language gate.

    Language is a hard constraint: a job that requires a language the user does
    not have is never returned. Everything else contributes to a transparent
    score so the UI can explain why a job was recommended.
    """
    skills = _norm(profile.get("skills"))
    langs = _norm(profile.get("languages"))
    modes = _norm(profile.get("work_modes"))
    experience = _norm(profile.get("experience"))
    interests = _norm(profile.get("interests"))
    governorate = str(profile.get("governorate", "")).strip().casefold()

    results: list[dict[str, Any]] = []
    for job in jobs:
        job_skills = _norm(job.get("skills"))
        job_langs = _norm(job.get("languages"))
        job_modes = _norm(job.get("modes"))
        job_exp = _norm(job.get("experience"))
        job_interests = _norm(job.get("interests"))
        job_governorates = _norm(job.get("governorates"))

        # Hard language gate. Arabic is treated like every other language.
        if job_langs and not (langs & job_langs):
            continue

        skill_hits = len(skills & job_skills)
        mode_hits = len(modes & job_modes)
        exp_hits = len(experience & job_exp)
        interest_hits = len(interests & job_interests)
        location_hit = bool(governorate and governorate in job_governorates)
        remote_bonus = bool(job.get("remote") and ("من البيت" in modes or "remote" in modes))

        score = (
            skill_hits * 5
            + mode_hits * 3
            + exp_hits * 2
            + interest_hits * 2
            + (2 if location_hit else 0)
            + (1 if remote_bonus else 0)
            + 3  # passed language gate
        )

        reasons: list[str] = []
        if skill_hits:
            reasons.append(f"{skill_hits} مهارة مناسبة")
        if mode_hits:
            reasons.append("نمط الشغل مناسب")
        if exp_hits:
            reasons.append("الخبرة مناسبة")
        if interest_hits:
            reasons.append("الاهتمامات متقاربة")
        if location_hit:
            reasons.append("المحافظة مناسبة")
        if remote_bonus:
            reasons.append("الشغل من البيت مناسب لك")
        reasons.append("اللغة مناسبة")

        category = "ممكن تناسبك"
        if score >= 14:
            category = "مناسبة ليك جدًا"
        elif score >= 9:
            category = "مناسبة ليك"
        elif score >= 5:
            category = "ممكن تناسبك"

        results.append({
            **job,
            "score": score,
            "category": category,
            "reason": reasons,
        })

    return sorted(results, key=lambda item: (-item["score"], item["id"]))
