def rank_jobs(profile, jobs):
    skills = {s.strip().lower() for s in profile.get('skills', [])}
    langs = {s.strip().lower() for s in profile.get('languages', [])}
    modes = {s.strip().lower() for s in profile.get('work_modes', [])}
    out = []
    for job in jobs:
        job_skills = {s.lower() for s in job.get('skills', [])}
        job_langs = {s.lower() for s in job.get('languages', [])}
        job_modes = {s.lower() for s in job.get('modes', [])}
        skill_hits = len(skills & job_skills)
        lang_ok = not job_langs or bool(langs & job_langs) or 'عربي' in job_langs and 'عربي' in langs
        mode_hits = len(modes & job_modes)
        score = skill_hits * 4 + mode_hits * 2 + (3 if lang_ok else -100)
        if score < 0:
            continue
        reason = []
        if skill_hits: reason.append(f"{skill_hits} مهارة مناسبة")
        if mode_hits: reason.append("نمط الشغل مناسب")
        if lang_ok: reason.append("اللغة مناسبة")
        out.append({**job, 'score': score, 'reason': reason})
    return sorted(out, key=lambda x: x['score'], reverse=True)
