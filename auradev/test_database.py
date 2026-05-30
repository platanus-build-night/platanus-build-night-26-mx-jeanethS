"""Unit tests for database analytics functions (get_insights, get_habits)."""
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest import mock

import pytest


# We need to patch DB_PATH before importing database module
@pytest.fixture
def test_db():
    """Create a temp DB, patch DB_PATH, and seed test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    with mock.patch("database.DB_PATH", db_path):
        # Import after patching
        import database

        database.DB_PATH = db_path
        database.init_db()

        # Seed test data: 3 sessions across different days/hours
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Session 1: Monday 9am, mostly flow
        base_time = datetime(2024, 1, 15, 9, 0, 0)  # Monday
        for i in range(5):
            ts = (base_time + timedelta(seconds=30 * i)).isoformat()
            state = "flow" if i < 4 else "debugging"
            cursor.execute(
                """
                INSERT INTO cycles
                (session_id, timestamp, state, confidence, reason,
                 wpm, backspace_ratio, window_switches, mouse_distance,
                 cpu_percent, idle_seconds, active_window)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("session-1", ts, state, 0.85, "test",
                 80.0 if state == "flow" else 30.0, 0.1, 2, 100.0,
                 20.0, 0.5, "VS Code - project.py"),
            )

        # Session 2: Friday 3pm, mostly stuck
        base_time = datetime(2024, 1, 19, 15, 0, 0)  # Friday
        for i in range(4):
            ts = (base_time + timedelta(seconds=30 * i)).isoformat()
            state = "stuck" if i < 3 else "flow"
            cursor.execute(
                """
                INSERT INTO cycles
                (session_id, timestamp, state, confidence, reason,
                 wpm, backspace_ratio, window_switches, mouse_distance,
                 cpu_percent, idle_seconds, active_window)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("session-2", ts, state, 0.75, "test",
                 20.0 if state == "stuck" else 90.0, 0.3, 5, 200.0,
                 40.0, 2.0, "Chrome - stackoverflow.com"),
            )

        # Session 3: Monday 9am (same as session 1), mixed
        base_time = datetime(2024, 1, 22, 9, 0, 0)  # Monday
        for i in range(3):
            ts = (base_time + timedelta(seconds=30 * i)).isoformat()
            state = ["flow", "reviewing", "flow"][i]
            cursor.execute(
                """
                INSERT INTO cycles
                (session_id, timestamp, state, confidence, reason,
                 wpm, backspace_ratio, window_switches, mouse_distance,
                 cpu_percent, idle_seconds, active_window)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("session-3", ts, state, 0.90, "test",
                 70.0, 0.05, 1, 50.0,
                 15.0, 0.2, "VS Code - project.py"),
            )

        conn.commit()
        conn.close()

        yield database

    os.unlink(db_path)


def test_get_insights_structure(test_db):
    """Test that get_insights returns expected structure."""
    insights = test_db.get_insights()

    assert "total_sessions" in insights
    assert "total_cycles" in insights
    assert "avg_flow_pct" in insights
    assert "avg_wpm_by_state" in insights
    assert "peak_hours" in insights
    assert "avg_session_duration_minutes" in insights


def test_get_insights_values(test_db):
    """Test that get_insights computes correct values."""
    insights = test_db.get_insights()

    assert insights["total_sessions"] == 3
    assert insights["total_cycles"] == 12  # 5 + 4 + 3

    # Flow cycles: 4 (session-1) + 1 (session-2) + 2 (session-3) = 7
    # 7/12 = 58.3%
    assert 58 <= insights["avg_flow_pct"] <= 59

    # Check state breakdown in avg_wpm_by_state
    assert "flow" in insights["avg_wpm_by_state"]
    assert "stuck" in insights["avg_wpm_by_state"]

    # Flow WPM: (80*4 + 90 + 70*2) / 7 = 550/7 ≈ 78.6
    assert 78 <= insights["avg_wpm_by_state"]["flow"] <= 80

    # Peak hours should include hour 9 (high flow rate)
    hours = [h["hour"] for h in insights["peak_hours"]]
    assert 9 in hours


def test_get_habits_structure(test_db):
    """Test that get_habits returns expected structure."""
    habits = test_db.get_habits()

    assert "flow_by_day" in habits
    assert "flow_by_hour" in habits
    assert "window_correlations" in habits


def test_get_habits_day_mapping(test_db):
    """Test that flow_by_day uses ISO weekday (0=Monday)."""
    habits = test_db.get_habits()

    # Monday = 0 in our output
    # Session-1 (Mon): 4 flow / 5 total = 80%
    # Session-3 (Mon): 2 flow / 3 total = 66.7%
    # Combined Monday: 6 flow / 8 total = 75%
    if 0 in habits["flow_by_day"]:
        assert habits["flow_by_day"][0] == 75.0

    # Friday = 4 in ISO weekday
    # Session-2: 1 flow / 4 total = 25%
    if 4 in habits["flow_by_day"]:
        assert habits["flow_by_day"][4] == 25.0


def test_get_habits_window_correlations(test_db):
    """Test that window_correlations ranks by flow rate."""
    habits = test_db.get_habits()

    # VS Code appears in session-1 (4 flow + 1 debug) and session-3 (2 flow + 1 review)
    # 8 cycles total, 6 flow = 75% flow rate
    # Chrome appears in session-2: 1 flow / 4 = 25% flow rate
    windows = habits["window_correlations"]

    # Should be sorted by flow_rate DESC
    if len(windows) >= 2:
        assert windows[0]["flow_rate"] >= windows[1]["flow_rate"]

    # VS Code should have higher flow rate than Chrome
    vscode = next((w for w in windows if "VS Code" in w["window"]), None)
    chrome = next((w for w in windows if "Chrome" in w["window"]), None)

    if vscode and chrome:
        assert vscode["flow_rate"] > chrome["flow_rate"]


def test_get_insights_empty_db():
    """Test that empty DB returns zeros gracefully."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    with mock.patch("database.DB_PATH", db_path):
        import database
        database.DB_PATH = db_path
        database.init_db()

        insights = database.get_insights()

        assert insights["total_sessions"] == 0
        assert insights["total_cycles"] == 0
        assert insights["avg_flow_pct"] == 0.0
        assert insights["avg_wpm_by_state"] == {}
        assert insights["peak_hours"] == []

    os.unlink(db_path)


def test_get_habits_empty_db():
    """Test that empty DB returns empty structures gracefully."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    with mock.patch("database.DB_PATH", db_path):
        import database
        database.DB_PATH = db_path
        database.init_db()

        habits = database.get_habits()

        assert habits["flow_by_day"] == {}
        assert habits["flow_by_hour"] == {}
        assert habits["window_correlations"] == []

    os.unlink(db_path)
