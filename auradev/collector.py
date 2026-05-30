"""
Signal Collection Module for auradev

Collects developer behavioral telemetry including:
- Keyboard metrics (keystrokes, backspaces, WPM, idle time)
- Mouse movement distance
- Active window tracking and switches
- System CPU usage
"""

import math
import time
import threading
import psutil
from pynput import keyboard, mouse

try:
    import pygetwindow as gw
except ImportError:
    gw = None


class TelemetryCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self.last_keystroke_time = time.time()
        self.last_mouse_pos = None
        self.last_window_title = ""
        self.keyboard_listener = None
        self.mouse_listener = None
        self._window_poll_thread = None
        self._window_poll_running = False
        self._init_metrics()
        self.reset_metrics()

    def _init_metrics(self):
        """Initialize metric counters (called once at construction)."""
        self.keystroke_count = 0
        self.backspace_count = 0
        self.mouse_distance = 0.0
        self.window_switches = 0

    def reset_metrics(self):
        """Reset all metrics for the next sample window."""
        with self._lock:
            self._reset_metrics_unlocked()

    def _reset_metrics_unlocked(self):
        """Reset metrics without acquiring lock (caller must hold lock)."""
        self.keystroke_count = 0
        self.backspace_count = 0
        self.mouse_distance = 0.0
        self.window_switches = 0
        self.sample_start_time = time.time()
        self.last_keystroke_time = time.time()

    def start_listeners(self):
        """Start keyboard, mouse, and window polling listeners."""
        try:
            self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
            self.mouse_listener = mouse.Listener(on_move=self._on_mouse_move)

            self.keyboard_listener.start()
            self.mouse_listener.start()
        except Exception as e:
            print(f"Warning: Failed to start input listeners: {e}")

        # Start window polling thread for continuous window switch detection
        self._window_poll_running = True
        self._window_poll_thread = threading.Thread(target=self._window_poll_loop, daemon=True)
        self._window_poll_thread.start()

    def stop_listeners(self):
        """Stop keyboard, mouse, and window polling listeners."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

        self._window_poll_running = False
        if self._window_poll_thread:
            self._window_poll_thread.join(timeout=2.0)

    def _on_key_press(self, key):
        """Handle keyboard press events."""
        with self._lock:
            self.keystroke_count += 1
            self.last_keystroke_time = time.time()

            # Check for backspace
            try:
                if key == keyboard.Key.backspace:
                    self.backspace_count += 1
            except (AttributeError, TypeError):
                # key may not support comparison; ignore
                pass

    def _on_mouse_move(self, x, y):
        """Handle mouse movement events."""
        # Guard against invalid coordinates
        if not (math.isfinite(x) and math.isfinite(y)):
            return

        with self._lock:
            if self.last_mouse_pos is not None:
                dx = x - self.last_mouse_pos[0]
                dy = y - self.last_mouse_pos[1]
                self.mouse_distance += (dx * dx + dy * dy) ** 0.5
            self.last_mouse_pos = (x, y)

    def _window_poll_loop(self):
        """Background thread that polls the active window for switch detection."""
        while self._window_poll_running:
            try:
                self._check_window_switch()
            except Exception:
                # Swallow errors from window polling to keep thread alive
                pass
            time.sleep(1.0)

    def _check_window_switch(self):
        """Check active window and increment switch counter if changed."""
        try:
            current_window = self.get_active_window()
        except Exception:
            return
        if not current_window:
            return
        with self._lock:
            self._update_window_switch_unlocked(current_window)

    def _update_window_switch_unlocked(self, current_window):
        """Update window switch tracking (caller must hold lock)."""
        if self.last_window_title and current_window != self.last_window_title:
            self.window_switches += 1
        self.last_window_title = current_window

    def get_active_window(self):
        """Get the title of the currently active window."""
        if not gw:
            return ""

        try:
            active_window = gw.getActiveWindow()
            if active_window:
                return active_window.title or ""
        except Exception:
            pass
        return ""

    def collect_metrics(self):
        """Collect and return current metrics, then reset for next window."""
        with self._lock:
            # Ensure window state is up-to-date before collecting
            current_window = self.get_active_window()
            if current_window:
                self._update_window_switch_unlocked(current_window)

            # Calculate elapsed time for this sample window
            elapsed_time = time.time() - self.sample_start_time

            # Calculate WPM (assuming average of 5 characters per word)
            wpm = (
                (self.keystroke_count / 5.0) / (elapsed_time / 60.0)
                if elapsed_time > 0
                else 0.0
            )

            # Calculate backspace ratio
            backspace_ratio = (
                self.backspace_count / self.keystroke_count
                if self.keystroke_count > 0
                else 0.0
            )

            # Calculate idle time since last keystroke within this sample window
            idle_seconds = time.time() - self.last_keystroke_time

            # Get current active window (fallback to last known if API fails)
            active_window = current_window if current_window else self.last_window_title

            # Get CPU usage
            try:
                cpu_percent = psutil.cpu_percent(interval=None)
            except Exception:
                cpu_percent = 0.0

            # Prepare metrics dict
            metrics = {
                "wpm": round(wpm, 1),
                "backspace_ratio": round(backspace_ratio, 2),
                "active_window": active_window,
                "window_switches": self.window_switches,
                "mouse_distance": round(self.mouse_distance, 1),
                "cpu_percent": round(cpu_percent, 1),
                "idle_seconds": round(idle_seconds, 1),
            }

            # Reset for next sample (internal helper avoids re-acquiring lock)
            self._reset_metrics_unlocked()

            return metrics
