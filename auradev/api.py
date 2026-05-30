"""FastAPI server for AURADEV session data."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_all_sessions, get_session_cycles, get_insights, get_habits, init_db, save_cycle
from config import API_PORT

# Initialize database on startup
init_db()

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"

app = FastAPI(title="AURADEV API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "session_id": getattr(app.state, "session_id", None),
    }


@app.get("/api/sessions")
def sessions():
    rows = get_all_sessions()
    for row in rows:
        row["state_breakdown"] = json.loads(row["state_breakdown"])
    return rows


@app.get("/api/sessions/latest")
def latest_session():
    rows = get_all_sessions()
    if not rows:
        return []
    return get_session_cycles(rows[0]["session_id"])


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str):
    return get_session_cycles(session_id)


@app.get("/api/insights")
def insights():
    """Aggregate stats across all sessions."""
    return get_insights()


@app.get("/api/habits")
def habits():
    """Cross-session behavioral patterns."""
    return get_habits()


# --- Sync endpoint for local app to push data to cloud ---

class CycleData(BaseModel):
    session_id: str
    state: str
    confidence: float = 0.0
    reason: str = ""
    wpm: float = 0.0
    backspace_ratio: float = 0.0
    window_switches: int = 0
    mouse_distance: float = 0.0
    cpu_percent: float = 0.0
    idle_seconds: float = 0.0
    active_window: str = ""


@app.post("/api/sync")
def sync_cycle(data: CycleData):
    """Receive cycle data from local app and save to cloud DB."""
    metrics = {
        "wpm": data.wpm,
        "backspace_ratio": data.backspace_ratio,
        "window_switches": data.window_switches,
        "mouse_distance": data.mouse_distance,
        "cpu_percent": data.cpu_percent,
        "idle_seconds": data.idle_seconds,
        "active_window": data.active_window,
    }
    classification = {
        "state": data.state,
        "confidence": data.confidence,
        "reason": data.reason,
    }
    save_cycle(data.session_id, metrics, classification)
    return {"status": "ok", "session_id": data.session_id}


if DASHBOARD_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    def dashboard_home():
        index = DASHBOARD_DIR / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return FileResponse(index, media_type="text/html")

    app.mount(
        "/",
        StaticFiles(directory=str(DASHBOARD_DIR), html=True),
        name="dashboard",
    )
