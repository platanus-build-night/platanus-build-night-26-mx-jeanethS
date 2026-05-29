"""
Session Logger Module for DevAura

Handles terminal output with ANSI colors and file logging.
Tracks session statistics and generates final summaries.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from config import LOG_FILE


class SessionLogger:
    def __init__(self):
        self.session_entries: List[Dict[str, Any]] = []
        self.session_start_time = time.time()
        
        # ANSI color codes for terminal output
        self.state_colors = {
            "flow": "\033[92m",              # Green
            "stuck": "\033[91m",             # Red
            "debugging": "\033[93m",         # Yellow
            "reviewing": "\033[96m",         # Cyan
            "context_switching": "\033[95m", # Magenta
        }
        self.reset_color = "\033[0m"

        # Clear/create log file
        with open(LOG_FILE, "w") as f:
            f.write(f"DevAura Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    def log_cycle(self, metrics: Dict[str, Any], classification: Dict[str, Any]):
        """Log a single collection cycle to terminal and file."""
        timestamp = datetime.now()
        
        # Create entry
        entry = {
            "timestamp": timestamp,
            "metrics": metrics.copy(),
            "classification": classification.copy(),
        }
        self.session_entries.append(entry)
        
        # Terminal output with colors
        state = classification["state"]
        confidence = classification["confidence"]
        reason = classification["reason"]
        
        color = self.state_colors.get(state, "")
        state_display = f"{color}{state.upper()}{self.reset_color}"
        
        print(f"[{timestamp.strftime('%H:%M:%S')}] {state_display} "
              f"(conf: {confidence:.2f}) | "
              f"WPM: {metrics['wpm']:.1f} | "
              f"Backspace: {metrics['backspace_ratio']:.2f} | "
              f"Window: {metrics['active_window'][:30]}")
        print(f"  → {reason}")
        
        # File logging
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {state.upper()} "
                   f"(confidence: {confidence:.2f})\n")
            f.write(f"  Metrics: WPM={metrics['wpm']:.1f}, "
                   f"Backspace={metrics['backspace_ratio']:.2f}, "
                   f"Mouse={metrics['mouse_distance']:.1f}, "
                   f"CPU={metrics['cpu_percent']:.1f}%, "
                   f"Idle={metrics['idle_seconds']:.1f}s, "
                   f"Switches={metrics['window_switches']}\n")
            f.write(f"  Window: {metrics['active_window']}\n")
            f.write(f"  Reason: {reason}\n\n")
    
    def print_session_summary(self):
        """Print final session statistics and save to file."""
        if not self.session_entries:
            print("No session data to summarize.")
            return
        
        session_duration = time.time() - self.session_start_time
        total_cycles = len(self.session_entries)
        
        # Calculate state percentages
        state_counts = {}
        for entry in self.session_entries:
            state = entry["classification"]["state"]
            state_counts[state] = state_counts.get(state, 0) + 1
        
        state_percentages = {
            state: (count / total_cycles) * 100 
            for state, count in state_counts.items()
        }
        
        # Find longest continuous flow window
        flow_windows = self._find_flow_windows()
        longest_flow = max(flow_windows, key=len) if flow_windows else []
        
        # Format summary
        print("\n" + "="*60)
        print("SESSION SUMMARY")
        print("="*60)
        print(f"Duration: {timedelta(seconds=int(session_duration))}")
        print(f"Total cycles: {total_cycles}")
        print("\nState Distribution:")

        for state in ["flow", "stuck", "debugging", "reviewing", "context_switching"]:
            if state in state_percentages:
                color = self.state_colors[state]
                percentage = state_percentages[state]
                bar_length = int(percentage / 5)  # Scale to 20 chars max
                bar = "█" * bar_length + "░" * (20 - bar_length)
                print(f"  {color}{state.ljust(16)}{self.reset_color} {bar} {percentage:5.1f}%")

        if longest_flow:
            flow_start = longest_flow[0]["timestamp"].strftime('%H:%M:%S')
            flow_duration = len(longest_flow) * 30  # 30 second intervals
            print(f"\nLongest Flow Window: {flow_duration}s starting at {flow_start}")

        # Save summary to file
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n" + "="*60 + "\n")
            f.write("SESSION SUMMARY\n")
            f.write("="*60 + "\n")
            f.write(f"Duration: {timedelta(seconds=int(session_duration))}\n")
            f.write(f"Total cycles: {total_cycles}\n\n")
            f.write("State Distribution:\n")

            for state, percentage in state_percentages.items():
                f.write(f"  {state.ljust(16)}: {percentage:5.1f}%\n")

            if longest_flow:
                flow_start = longest_flow[0]["timestamp"].strftime('%H:%M:%S')
                flow_duration = len(longest_flow) * 30
                f.write(f"\nLongest Flow Window: {flow_duration}s starting at {flow_start}\n")
    
    def _find_flow_windows(self) -> List[List[Dict[str, Any]]]:
        """Find all continuous flow state windows."""
        windows = []
        current_window = []
        
        for entry in self.session_entries:
            if entry["classification"]["state"] == "flow":
                current_window.append(entry)
            else:
                if current_window:
                    windows.append(current_window)
                    current_window = []
        
        # Add final window if it ends in flow
        if current_window:
            windows.append(current_window)
        
        return windows