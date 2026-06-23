"""
FastAPI app entry point.

Mounts patron routes, admin routes, the SSE stream, and serves the
plain-HTML frontend as static files. Initialises the SQLite database
from schema.sql + seed.sql on first run if it doesn't already exist.
"""
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from adapters.inbound.http import patron_routes, admin_routes, session_routes

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def init_db_if_needed():
    db_exists = os.path.exists(settings.DB_PATH)

    # Ensure the db/ directory exists (handles both relative and absolute paths)
    db_dir = os.path.dirname(os.path.abspath(settings.DB_PATH))
    os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(settings.DB_PATH)
    schema_path = os.path.join(PROJECT_ROOT, "db", "schema.sql")
    with open(schema_path) as f:
        conn.executescript(f.read())

    if not db_exists:
        seed_path = os.path.join(PROJECT_ROOT, "db", "seed.sql")
        with open(seed_path) as f:
            conn.executescript(f.read())
        print(f"[startup] Initialised fresh DB with seed data at {settings.DB_PATH}")
    else:
        print(f"[startup] Using existing DB at {settings.DB_PATH}")

    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_if_needed()
    yield


app = FastAPI(title="CinemaFlo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patron_routes.router)
app.include_router(admin_routes.router)
app.include_router(session_routes.router)

# Serve the plain HTML/JS frontend with no build step.
frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.get("/")
def root():
    return {
        "service": "CinemaFlo",
        "patron_app": "/app/patron/index.html",
        "admin_app": "/app/admin/index.html",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
