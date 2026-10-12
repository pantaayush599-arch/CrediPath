"""CrediPath API entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .db import SessionLocal, backend_label
from .services.seed import SAMPLES_DIR, init_db, seed_demo, write_sample_files

log = logging.getLogger("credipath")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if not (SAMPLES_DIR / "raj_bakery_update_sep2026.csv").exists():
        write_sample_files()
    if os.environ.get("CREDIPATH_AUTO_SEED", "1") != "0":
        with SessionLocal() as db:
            created = seed_demo(db)
        if created:
            log.warning("Seeded demo businesses: %s", ", ".join(created))
    log.warning("CrediPath API using %s", backend_label())
    yield


app = FastAPI(
    title="CrediPath API",
    version="1.0.0",
    description=(
        "Explainable, rules-based MSME credit assessment prototype. All data is synthetic. "
        "Scores are not loan decisions and are not a validated credit-risk model."
    ),
    lifespan=lifespan,
)

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/")
def root():
    return {"name": "CrediPath API", "docs": "/docs", "health": "/api/health"}
