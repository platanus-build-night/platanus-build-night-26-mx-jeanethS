"""
Unit tests for the collector module.

Validates the TelemetryCollector output contract and internal behavior.
"""

import math
import time
import unittest
from unittest.mock import patch, MagicMock

from collector import TelemetryCollector


class TestCollectorOutputContract(unittest.TestCase):
    """Validate that collect_metrics returns the expected format."""

    EXPECTED_KEYS = {
        "wpm",
        "backspace_ratio",
        "active_window",
        "window_switches",
        "mouse_distance",
        "cpu_percent",
        "idle_seconds",
    }

    def test_output_keys(self):
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        self.assertEqual(set(metrics.keys()), self.EXPECTED_KEYS)

    def test_output_types(self):
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        self.assertIsInstance(metrics["wpm"], float)
        self.assertIsInstance(metrics["backspace_ratio"], float)
        self.assertIsInstance(metrics["active_window"], str)
        self.assertIsInstance(metrics["window_switches"], int)
        self.assertIsInstance(metrics["mouse_distance"], float)
        self.assertIsInstance(metrics["cpu_percent"], float)
        self.assertIsInstance(metrics["idle_seconds"], float)

    def test_output_values_finite(self):
        """Ensure no NaN or Inf values in any metric."""
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        for key, value in metrics.items():
            if isinstance(value, float):
                self.assertTrue(
                    math.isfinite(value),
                    f"Metric '{key}' is not finite: {value}",
                )

    def test_zero_state_metrics(self):
        """With no activity, all counters should be zero."""
        collector = TelemetryCollector()
        # Allow a tiny elapsed time so division is safe
        time.sleep(0.01)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["wpm"], 0.0)
        self.assertEqual(metrics["backspace_ratio"], 0.0)
        self.assertEqual(metrics["window_switches"], 0)
        self.assertEqual(metrics["mouse_distance"], 0.0)
        self.assertGreaterEqual(metrics["idle_seconds"], 0.0)


class TestKeyboardTracking(unittest.TestCase):
    """Verify keystroke and backspace tracking."""

    def test_keystroke_count(self):
        collector = TelemetryCollector()
        for _ in range(10):
            collector._on_key_press(MagicMock())
        time.sleep(1.0)
        metrics = collector.collect_metrics()
        # 10 keystrokes in ~1 second = 2 words in 1/60 minute ≈ 120 WPM
        self.assertAlmostEqual(metrics["wpm"], 120.0, places=0)

    def test_backspace_tracking(self):
        collector = TelemetryCollector()
        # Simulate 4 regular keys + 1 backspace
        from pynput.keyboard import Key

        for _ in range(4):
            collector._on_key_press(MagicMock())
        collector._on_key_press(Key.backspace)

        metrics = collector.collect_metrics()
        # backspace_ratio = 1 / 5 = 0.2
        self.assertEqual(metrics["backspace_ratio"], 0.2)

    def test_backspace_ratio_zero_when_no_keystrokes(self):
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["backspace_ratio"], 0.0)

    def test_backspace_ratio_zero_when_no_backspaces(self):
        collector = TelemetryCollector()
        for _ in range(5):
            collector._on_key_press(MagicMock())
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["backspace_ratio"], 0.0)


class TestMouseDistance(unittest.TestCase):
    """Verify mouse distance calculation and edge-case handling."""

    def test_basic_distance(self):
        collector = TelemetryCollector()
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(3, 4)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["mouse_distance"], 5.0)

    def test_accumulated_distance(self):
        collector = TelemetryCollector()
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(0, 10)
        collector._on_mouse_move(0, 20)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["mouse_distance"], 20.0)

    def test_nan_coordinates_ignored(self):
        collector = TelemetryCollector()
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(float("nan"), 10)
        # last_mouse_pos should remain (0, 0) because NaN move is ignored
        collector._on_mouse_move(0, 10)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["mouse_distance"], 10.0)

    def test_inf_coordinates_ignored(self):
        collector = TelemetryCollector()
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(float("inf"), 10)
        collector._on_mouse_move(0, 10)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["mouse_distance"], 10.0)

    def test_negative_inf_coordinates_ignored(self):
        collector = TelemetryCollector()
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(float("-inf"), 10)
        collector._on_mouse_move(0, 10)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["mouse_distance"], 10.0)

    def test_no_nan_or_inf_in_output(self):
        """Inject NaN moves and ensure final metric is still finite."""
        collector = TelemetryCollector()
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(float("nan"), float("nan"))
        collector._on_mouse_move(float("inf"), float("inf"))
        collector._on_mouse_move(1, 1)
        metrics = collector.collect_metrics()
        self.assertTrue(math.isfinite(metrics["mouse_distance"]))


class TestWindowSwitching(unittest.TestCase):
    """Verify window switching detection."""

    @patch.object(TelemetryCollector, "get_active_window")
    def test_window_switch_count(self, mock_get_window):
        collector = TelemetryCollector()
        mock_get_window.return_value = "Window A"
        collector._check_window_switch()
        mock_get_window.return_value = "Window B"
        collector._check_window_switch()
        collector._check_window_switch()  # same window, no switch
        mock_get_window.return_value = "Window C"
        collector._check_window_switch()

        # Ensure collect_metrics doesn't see a different real window
        mock_get_window.return_value = "Window C"
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["window_switches"], 2)

    def test_window_switch_error_handling(self):
        """Errors from get_active_window should not crash the collector."""
        collector = TelemetryCollector()
        with patch.object(
            collector, "get_active_window", side_effect=Exception("gw failed")
        ):
            # Should not raise
            collector._check_window_switch()

    @patch.object(TelemetryCollector, "get_active_window")
    def test_window_switch_in_collect_metrics(self, mock_get_window):
        """collect_metrics should also detect a window switch when called."""
        collector = TelemetryCollector()
        # Seed last_window_title
        mock_get_window.return_value = "IDE"
        collector._check_window_switch()

        # Simulate a switch at collection time
        mock_get_window.return_value = "Browser"
        metrics = collector.collect_metrics()

        self.assertEqual(metrics["window_switches"], 1)
        self.assertEqual(metrics["active_window"], "Browser")


class TestCpuCollection(unittest.TestCase):
    """Verify CPU metric collection via psutil."""

    def test_cpu_percent_is_finite(self):
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        self.assertIsInstance(metrics["cpu_percent"], float)
        self.assertTrue(math.isfinite(metrics["cpu_percent"]))
        self.assertGreaterEqual(metrics["cpu_percent"], 0.0)

    @patch("collector.psutil.cpu_percent", return_value=42.5)
    def test_cpu_percent_value(self, mock_cpu):
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["cpu_percent"], 42.5)

    @patch("collector.psutil.cpu_percent", side_effect=Exception("psutil error"))
    def test_cpu_fallback_on_error(self, mock_cpu):
        collector = TelemetryCollector()
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["cpu_percent"], 0.0)


class TestMetricsReset(unittest.TestCase):
    """Verify counters are cleared after each sample."""

    def test_counters_reset(self):
        collector = TelemetryCollector()
        # Add some activity
        collector._on_key_press(MagicMock())
        collector._on_mouse_move(0, 0)
        collector._on_mouse_move(10, 0)

        # First collection
        metrics1 = collector.collect_metrics()
        self.assertGreater(metrics1["mouse_distance"], 0)

        # Second collection should be zeroed
        time.sleep(0.01)
        metrics2 = collector.collect_metrics()
        self.assertEqual(metrics2["wpm"], 0.0)
        self.assertEqual(metrics2["backspace_ratio"], 0.0)
        self.assertEqual(metrics2["window_switches"], 0)
        self.assertEqual(metrics2["mouse_distance"], 0.0)

    def test_keystroke_count_resets(self):
        collector = TelemetryCollector()
        for _ in range(5):
            collector._on_key_press(MagicMock())
        collector.collect_metrics()
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["wpm"], 0.0)
        self.assertEqual(metrics["backspace_ratio"], 0.0)

    @patch.object(TelemetryCollector, "get_active_window")
    def test_window_switches_reset(self, mock_get_window):
        collector = TelemetryCollector()
        mock_get_window.return_value = "Win1"
        collector._check_window_switch()
        mock_get_window.return_value = "Win2"
        collector._check_window_switch()

        # Prevent real window from causing an extra switch during collect_metrics
        mock_get_window.return_value = "Win2"
        m1 = collector.collect_metrics()
        self.assertEqual(m1["window_switches"], 1)

        mock_get_window.return_value = "Win2"
        m2 = collector.collect_metrics()
        self.assertEqual(m2["window_switches"], 0)


class TestWpmCalculation(unittest.TestCase):
    """Verify WPM formula under known conditions."""

    def test_wpm_calculation(self):
        collector = TelemetryCollector()
        # Simulate that the sample window started 60 seconds ago
        collector.sample_start_time = time.time() - 60.0
        # 60 keystrokes in 60 seconds = 12 words in 1 minute = 12 WPM
        for _ in range(60):
            collector._on_key_press(MagicMock())

        metrics = collector.collect_metrics()
        self.assertAlmostEqual(metrics["wpm"], 12.0, places=1)

    def test_wpm_zero_on_no_keystrokes(self):
        collector = TelemetryCollector()
        time.sleep(0.05)
        metrics = collector.collect_metrics()
        self.assertEqual(metrics["wpm"], 0.0)


if __name__ == "__main__":
    unittest.main()
