"""SQLite database module for auradev.

Uses sqlite3 from the stdlib. DB file: auradev.db in project root.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

_db_dir = os.getenv("DB_DIR")
DB_PATH = Path(_db_dir) / "auradev.db" if _db_dir else Path(__file__).with_name("auradev.db")


def init_db() -> None:
    """Create table if not exists. Call once at startup."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cycles (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT NOT NULL,
                timestamp        TEXT NOT NULL,
                state            TEXT NOT NULL,
                confidence       REAL,
                reason           TEXT,
                wpm              REAL,
                backspace_ratio  REAL,
                window_switches  INTEGER,
                mouse_distance   REAL,
                cpu_percent      REAL,
                idle_seconds     REAL,
                active_window    TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_cycle(session_id: str, metrics: dict, classification: dict) -> None:
    """Insert a cycle row. Called from SessionLogger.log_cycle()."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cycles
            (session_id, timestamp, state, confidence, reason,
             wpm, backspace_ratio, window_switches, mouse_distance,
             cpu_percent, idle_seconds, active_window)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                datetime.now().isoformat(),
                classification.get("state", "reviewing"),
                classification.get("confidence", 0.0),
                classification.get("reason", ""),
                metrics.get("wpm", 0.0),
                metrics.get("backspace_ratio", 0.0),
                metrics.get("window_switches", 0),
                metrics.get("mouse_distance", 0.0),
                metrics.get("cpu_percent", 0.0),
                metrics.get("idle_seconds", 0.0),
                metrics.get("active_window", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_session_cycles(session_id: str) -> list[dict]:
    """Return all rows for a session, ordered by timestamp ASC."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM cycles WHERE session_id = ? ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_insights() -> dict:
    """
    Aggregate stats across all sessions:
    - avg_flow_pct: percentage of cycles in 'flow' state
    - avg_wpm_by_state: dict mapping state -> avg wpm
    - peak_hours: list of hours (0-23) ranked by flow rate
    - total_sessions, total_cycles, avg_session_duration_minutes
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Total cycles and flow percentage
        cursor.execute("SELECT COUNT(*) as total FROM cycles")
        total_cycles = cursor.fetchone()["total"]
        if total_cycles == 0:
            return {
                "total_sessions": 0,
                "total_cycles": 0,
                "avg_flow_pct": 0.0,
                "avg_wpm_by_state": {},
                "peak_hours": [],
                "avg_session_duration_minutes": 0.0,
            }

        cursor.execute("SELECT COUNT(*) as flow_count FROM cycles WHERE state = 'flow'")
        flow_count = cursor.fetchone()["flow_count"]
        avg_flow_pct = round((flow_count / total_cycles) * 100, 1)

        # Avg WPM by state
        cursor.execute(
            """
            SELECT state, AVG(wpm) as avg_wpm
            FROM cycles
            GROUP BY state
            """
        )
        avg_wpm_by_state = {row["state"]: round(row["avg_wpm"], 1) for row in cursor.fetchall()}

        # Peak hours: extract hour from ISO timestamp, calc flow rate per hour
        cursor.execute(
            """
            SELECT
                CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) as hour,
                COUNT(*) as total,
                SUM(CASE WHEN state = 'flow' THEN 1 ELSE 0 END) as flow_count
            FROM cycles
            GROUP BY hour
            ORDER BY (CAST(flow_count AS REAL) / total) DESC
            """
        )
        peak_hours = [
            {"hour": row["hour"], "flow_rate": round(row["flow_count"] / row["total"] * 100, 1)}
            for row in cursor.fetchall()
        ]

        # Session count and avg duration
        cursor.execute(
            """
            SELECT COUNT(DISTINCT session_id) as session_count FROM cycles
            """
        )
        total_sessions = cursor.fetchone()["session_count"]

        cursor.execute(
            """
            SELECT
                session_id,
                MIN(timestamp) as started_at,
                MAX(timestamp) as ended_at
            FROM cycles
            GROUP BY session_id
            """
        )
        durations = []
        for row in cursor.fetchall():
            try:
                start = datetime.fromisoformat(row["started_at"])
                end = datetime.fromisoformat(row["ended_at"])
                durations.append((end - start).total_seconds() / 60.0)
            except (ValueError, TypeError):
                pass
        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

        return {
            "total_sessions": total_sessions,
            "total_cycles": total_cycles,
            "avg_flow_pct": avg_flow_pct,
            "avg_wpm_by_state": avg_wpm_by_state,
            "peak_hours": peak_hours,
            "avg_session_duration_minutes": avg_duration,
        }
    finally:
        conn.close()


def get_habits() -> dict:
    """
    Cross-session patterns:
    - flow_by_day: {0-6 (Mon-Sun)} -> flow rate
    - flow_by_hour: {0-23} -> flow rate
    - window_correlations: which active_window values correlate with flow
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM cycles")
        total = cursor.fetchone()["total"]
        if total == 0:
            return {
                "flow_by_day": {},
                "flow_by_hour": {},
                "window_correlations": [],
            }

        # Flow rate by day of week (0=Monday, 6=Sunday)
        # SQLite strftime %w: 0=Sunday, so we adjust
        cursor.execute(
            """
            SELECT
                CAST(strftime('%w', timestamp) AS INTEGER) as dow,
                COUNT(*) as total,
                SUM(CASE WHEN state = 'flow' THEN 1 ELSE 0 END) as flow_count
            FROM cycles
            GROUP BY dow
            """
        )
        flow_by_day_raw = {}
        for row in cursor.fetchall():
            # Convert SQLite %w (0=Sun) to ISO (0=Mon)
            dow_sqlite = row["dow"]
            dow_iso = (dow_sqlite + 6) % 7  # Sun=6, Mon=0, Tue=1, etc.
            flow_by_day_raw[dow_iso] = round(row["flow_count"] / row["total"] * 100, 1)
        flow_by_day = dict(sorted(flow_by_day_raw.items()))

        # Flow rate by hour
        cursor.execute(
            """
            SELECT
                CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) as hour,
                COUNT(*) as total,
                SUM(CASE WHEN state = 'flow' THEN 1 ELSE 0 END) as flow_count
            FROM cycles
            GROUP BY hour
            ORDER BY hour
            """
        )
        flow_by_hour = {
            row["hour"]: round(row["flow_count"] / row["total"] * 100, 1)
            for row in cursor.fetchall()
        }

        # Window correlations: which active_window values have highest flow rate
        # Only include windows with >= 3 cycles (statistical significance)
        cursor.execute(
            """
            SELECT
                active_window,
                COUNT(*) as total,
                SUM(CASE WHEN state = 'flow' THEN 1 ELSE 0 END) as flow_count,
                AVG(wpm) as avg_wpm
            FROM cycles
            WHERE active_window != ''
            GROUP BY active_window
            HAVING COUNT(*) >= 3
            ORDER BY (CAST(flow_count AS REAL) / total) DESC
            LIMIT 20
            """
        )
        window_correlations = [
            {
                "window": row["active_window"],
                "flow_rate": round(row["flow_count"] / row["total"] * 100, 1),
                "total_cycles": row["total"],
                "avg_wpm": round(row["avg_wpm"], 1),
            }
            for row in cursor.fetchall()
        ]

        return {
            "flow_by_day": flow_by_day,
            "flow_by_hour": flow_by_hour,
            "window_correlations": window_correlations,
        }
    finally:
        conn.close()


def get_all_sessions() -> list[dict]:
    """
    Return distinct session_ids with:
    - started_at (first timestamp)
    - ended_at (last timestamp)
    - cycle_count
    - state_breakdown as JSON string: {"flow": 5, "stuck": 3, ...}
    Ordered by started_at DESC.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                session_id,
                MIN(timestamp) as started_at,
                MAX(timestamp) as ended_at,
                COUNT(*) as cycle_count
            FROM cycles
            GROUP BY session_id
            ORDER BY started_at DESC
            """
        )
        session_rows = cursor.fetchall()

        result: list[dict] = []
        for row in session_rows:
            sid = row["session_id"]
            cursor.execute(
                """
                SELECT state, COUNT(*) as cnt
                FROM cycles
                WHERE session_id = ?
                GROUP BY state
                """,
                (sid,),
            )
            state_rows = cursor.fetchall()
            breakdown = {r["state"]: r["cnt"] for r in state_rows}
            result.append(
                {
                    "session_id": sid,
                    "started_at": row["started_at"],
                    "ended_at": row["ended_at"],
                    "cycle_count": row["cycle_count"],
                    "state_breakdown": json.dumps(breakdown),
                }
            )

        return result
    finally:
        conn.close()
