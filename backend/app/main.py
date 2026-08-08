from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
from .matching import rank_jobs

app = FastAPI(title="InWork API", version="0.1.0")

class Profile(BaseModel):
    name: str = ""
    governorate: str = ""
    age_group: str = ""
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    work_modes: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)

class Job(BaseModel):
    id: str
    title: str
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    modes: List[str] = Field(default_factory=list)
    governorates: List[str] = Field(default_factory=list)
    remote: bool = False
    income: str = ""
    url: Optional[str] = None

JOBS = [
    Job(id="va-001", title="مساعد افتراضي", skills=["تنظيم","Excel","مكتب"], languages=["عربي","إنجليزي"], modes=["من البيت","Freelance"], remote=True, income="8,000–15,000 جنيه"),
    Job(id="data-001", title="إدخال بيانات", skills=["Excel","كتابة","مكتب"], languages=["عربي"], modes=["من البيت","جزئي"], remote=True, income="6,000–10,000 جنيه"),
    Job(id="support-001", title="Customer Support", skills=["تواصل","خدمة عملاء"], languages=["إنجليزي"], modes=["من البيت","دوام كامل"], remote=True, income="$500–900"),
    Job(id="design-001", title="مصمم UI/UX مبتدئ", skills=["تصميم","Figma","إبداعي"], languages=["عربي","إنجليزي"], modes=["Freelance","مشروع"], remote=True, income="$300–700"),
    Job(id="book-001", title="مساعد محاسب", skills=["Excel","محاسبة","مكتب"], languages=["عربي"], modes=["دوام كامل","جزئي"], remote=False, income="9,000–16,000 جنيه"),
]

@app.get("/health")
def health():
    return {"ok": True, "service": "inwork-api"}

@app.post("/v1/match")
def match(profile: Profile):
    return {"results": rank_jobs(profile.model_dump(), [j.model_dump() for j in JOBS])}

@app.get("/v1/jobs")
def jobs():
    return {"jobs": [j.model_dump() for j in JOBS]}
