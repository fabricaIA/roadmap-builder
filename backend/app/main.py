"""Aplicação FastAPI do RoadmapBuilder (multiusuário).

Run:  uvicorn backend.app.main:app --reload --port 8000
Antes:  alembic upgrade head   (cria/atualiza o banco)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.routers import auth, profile, roadmap

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(title="RoadmapBuilder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(roadmap.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "oauth_configured": settings.oauth_configured}
