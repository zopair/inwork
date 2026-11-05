import os
from pathlib import Path

from fastapi.responses import FileResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as marketplace_router, initialize_api_database

app = FastAPI(title="InWork API", version="0.2.0")

allowed_origins = [
    item.strip().rstrip("/")
    for item in os.environ.get("INWORK_ALLOWED_ORIGINS", "").split(",")
    if item.strip()
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "X-InWork-Request", "Authorization"],
        max_age=600,
    )

app.include_router(marketplace_router)


@app.on_event("startup")
def startup():
    initialize_api_database()


@app.get("/health")
def health():
    return {"ok": True, "service": "inwork-api", "version": "0.2.0"}


FRONTEND_FILE = Path(__file__).resolve().parents[2] / "index.html"


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(FRONTEND_FILE)
