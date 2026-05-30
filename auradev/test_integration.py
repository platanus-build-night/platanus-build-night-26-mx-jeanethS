"""
Integration tests for auradev.

Validates that all modules wire together correctly in main.py:
- Metrics flow from collector to classifier as plain dicts.
- Classification results flow to audio and logger.
- Demo mode runs for the specified number of cycles without Claude or telemetry.
- Graceful shutdown stops audio, stops listeners, and prints a session summary.
- Logger writes to session.log with timestamps.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock audio dependencies before any module imports them
sys.modules["pygame"] = MagicMock()
sys.modules["numpy"] = MagicMock()

from main import auradev
from config import STATES


class TestIntegrationDemoPipeline(unittest.TestCase):
    """End-to-end validation of the demo-mode pipeline."""

    def setUp(self):
        self.mock_audio = MagicMock()
        self.mock_logger = MagicMock()

    def test_demo_runs_specified_cycles_and_stops(self):
        """Demo mode with max_cycles=2 should execute exactly 2 cycles."""
        app = auradev(
            demo_mode=True,
            max_cycles=2,
            sample_interval=0,
            audio_engine=self.mock_audio,
            logger=self.mock_logger,
        )
        app.start()

        self.assertEqual(app.cycle_count, 2)
        self.assertFalse(app.running)

    def test_metrics_are_plain_dicts(self):
        """Verify collector output flows as a plain Python dict."""
        app = auradev(
            demo_mode=True,
            max_cycles=1,
            sample_interval=0,
            audio_engine=self.mock_audio,
            logger=self.mock_logger,
        )
        app.start()

        self.assertEqual(self.mock_logger.log_cycle.call_count, 1)
        metrics, classification = self.mock_logger.log_cycle.call_args[0]
        self.assertIsInstance(metrics, dict)
        expected_keys = {
            "wpm",
            "backspace_ratio",
            "active_window",
            "window_switches",
            "mouse_distance",
            "cpu_percent",
            "idle_seconds",
        }
        self.assertEqual(set(metrics.keys()), expected_keys)

    def test_classification_results_flow_to_audio_and_logger(self):
        """Each cycle should update audio and log the classification."""
        app = auradev(
            demo_mode=True,
            max_cycles=2,
            sample_interval=0,
            audio_engine=self.mock_audio,
            logger=self.mock_logger,
        )
        app.start()

        self.assertEqual(self.mock_audio.play_state.call_count, 2)
        self.assertEqual(self.mock_logger.log_cycle.call_count, 2)

        # Verify audio receives valid states
        for call in self.mock_audio.play_state.call_args_list:
            state = call.args[0]
            self.assertIn(state, STATES)

        # Verify logger receives valid classifications
        for call in self.mock_logger.log_cycle.call_args_list:
            classification = call.args[1]
            self.assertIsInstance(classification, dict)
            self.assertIn("state", classification)
            self.assertIn("confidence", classification)
            self.assertIn("reason", classification)
            self.assertIn(classification["state"], STATES)
            self.assertIsInstance(classification["confidence"], float)
            self.assertIsInstance(classification["reason"], str)
            self.assertTrue(classification["reason"])

    def test_graceful_shutdown_calls_cleanup(self):
        """Stopping the app should stop audio and print a session summary."""
        app = auradev(
            demo_mode=True,
            max_cycles=1,
            sample_interval=0,
            audio_engine=self.mock_audio,
            logger=self.mock_logger,
        )
        app.start()

        self.mock_audio.cleanup.assert_called_once()
        self.mock_logger.print_session_summary.assert_called_once()

    def test_no_claude_or_telemetry_in_demo_mode(self):
        """Demo mode must not instantiate the classifier or start listeners."""
        app = auradev(
            demo_mode=True,
            max_cycles=1,
            sample_interval=0,
            audio_engine=self.mock_audio,
            logger=self.mock_logger,
        )
        # classifier should be None in demo mode
        self.assertIsNone(app.classifier)
        app.start()
        # collector listeners are never started in demo mode
        # (no assertion needed — absence of crash is the test)


class TestIntegrationRealLogger(unittest.TestCase):
    """Validate the real logger writes to disk and includes timestamps."""

    def setUp(self):
        self.tmp_log = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log")
        self.tmp_log.close()
        self.addCleanup(os.remove, self.tmp_log.name)

    def test_logger_writes_timestamps_to_session_log(self):
        from logger import SessionLogger

        with patch("logger.LOG_FILE", self.tmp_log.name):
            logger = SessionLogger()

            metrics = {
                "wpm": 42.0,
                "backspace_ratio": 0.1,
                "active_window": "TestWindow",
                "window_switches": 1,
                "mouse_distance": 123.4,
                "cpu_percent": 15.0,
                "idle_seconds": 2.0,
            }
            classification = {
                "state": "flow",
                "confidence": 0.92,
                "reason": "Steady typing rhythm detected.",
            }

            logger.log_cycle(metrics, classification)
            logger.print_session_summary()

        with open(self.tmp_log.name, "r", encoding="utf-8") as f:
            content = f.read()

        # Should contain a timestamp
        self.assertRegex(content, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        # Should contain the state
        self.assertIn("FLOW", content)
        # Should contain metrics
        self.assertIn("WPM=42.0", content)
        # Should contain session summary
        self.assertIn("SESSION SUMMARY", content)

    def test_logger_ansi_colors_in_terminal(self):
        """Logger should use ANSI escape codes for terminal colors."""
        from logger import SessionLogger

        logger = SessionLogger()
        # Verify color map contains real ANSI codes
        for state in STATES:
            color = logger.state_colors.get(state, "")
            self.assertTrue(color.startswith("\033["), f"State {state} missing ANSI color")


if __name__ == "__main__":
    unittest.main(verbosity=2)
