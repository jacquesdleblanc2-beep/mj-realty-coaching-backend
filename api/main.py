# api/main.py — MJ Realty Coaching API entry point
# Run with: uvicorn api.main:app --reload --port 8000
# Or:       ./run_api.sh

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import pipeline, realtors, auth, progress, coaches, admin

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MJ Realty Coaching API",
    version="2.0.0",
    description="Backend for the MJ Realty weekly coaching platform",
)

origins = [o for o in [
    "http://localhost:3000",
    "https://mj-realty-coaching-frontend.vercel.app",
    os.getenv("FRONTEND_URL", ""),
] if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(realtors.router, prefix="/api/realtors", tags=["realtors"])
app.include_router(progress.router, prefix="/api/progress", tags=["progress"])
app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(coaches.router,  prefix="/api/coaches",  tags=["coaches"])
app.include_router(admin.router,    prefix="/api/admin",    tags=["admin"])


@app.get("/")
def root():
    return {"status": "MJ Realty Coaching API is running", "version": "2.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
