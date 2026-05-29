"""
DevAura - Ambient Music Engine for Developers

Samples developer behavioral telemetry, classifies cognitive state via Claude,
and plays procedurally generated music matching that state.

Usage:
    python main.py          # Normal mode with Claude classification
    python main.py --demo   # Demo mode (cycles through states, no Claude)
"""

import argparse
import signal
import sys
import time
from typing import Dict, Any

from collector import TelemetryCollector
from classifier import CognitiveClassifier
from audio import AudioEngine
from logger import SessionLogger
from config import SAMPLE_INTERVAL, STATES


class DevAura:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        self.running = False
        self.demo_state_index = 0
        
        # Initialize components
        self.collector = TelemetryCollector()
        self.audio_engine = AudioEngine()
        self.logger = SessionLogger()
        
        # Only initialize classifier in normal mode
        if not demo_mode:
            try:
                self.classifier = CognitiveClassifier()
            except ValueError as e:
                print(f"Error: {e}")
                print("Please set ANTHROPIC_API_KEY environment variable or use --demo mode")
                sys.exit(1)
        else:
            self.classifier = None
            print("Running in demo mode - no Claude API calls")
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print("\\nShutting down DevAura...")
        self.stop()
    
    def start(self):
        """Start the main application loop."""
        self.running = True
        
        print("DevAura starting...")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        # Start telemetry collection
        if not self.demo_mode:
            self.collector.start_listeners()
        
        try:
            self._main_loop()
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            self.stop()
    
    def _main_loop(self):
        """Main application loop - collect, classify, play, log."""
        while self.running:
            try:
                # Collect telemetry metrics
                if self.demo_mode:
                    metrics = self._get_demo_metrics()
                else:
                    metrics = self.collector.collect_metrics()
                
                # Classify cognitive state
                if self.demo_mode:
                    classification = self._get_demo_classification()
                else:
                    classification = self.classifier.classify_state(metrics)
                
                # Update audio
                self.audio_engine.play_state(classification["state"])
                
                # Log the cycle
                self.logger.log_cycle(metrics, classification)
                
                # Wait for next sample
                time.sleep(SAMPLE_INTERVAL)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in cycle: {e}")
                # Continue running despite errors
                time.sleep(SAMPLE_INTERVAL)
    
    def _get_demo_metrics(self) -> Dict[str, Any]:
        """Generate fake metrics for demo mode."""
        import random
        
        # Cycle through different metric patterns
        patterns = [
            # Flow pattern
            {
                "wpm": random.uniform(40, 60),
                "backspace_ratio": random.uniform(0.05, 0.15),
                "window_switches": random.randint(0, 1),
                "mouse_distance": random.uniform(100, 300),
                "cpu_percent": random.uniform(20, 40),
                "idle_seconds": random.uniform(0, 5),
            },
            # Stuck pattern
            {
                "wpm": random.uniform(5, 15),
                "backspace_ratio": random.uniform(0.3, 0.5),
                "window_switches": random.randint(0, 2),
                "mouse_distance": random.uniform(50, 150),
                "cpu_percent": random.uniform(10, 25),
                "idle_seconds": random.uniform(10, 30),
            },
            # Debugging pattern
            {
                "wpm": random.uniform(20, 35),
                "backspace_ratio": random.uniform(0.15, 0.25),
                "window_switches": random.randint(2, 4),
                "mouse_distance": random.uniform(200, 500),
                "cpu_percent": random.uniform(30, 60),
                "idle_seconds": random.uniform(2, 8),
            },
        ]
        
        pattern = patterns[self.demo_state_index % len(patterns)]
        pattern["active_window"] = "Demo Application"
        return pattern
    
    def _get_demo_classification(self) -> Dict[str, Any]:
        """Generate demo classification results."""
        states_cycle = ["flow", "stuck", "debugging", "reviewing", "context_switching"]
        current_state = states_cycle[self.demo_state_index % len(states_cycle)]
        
        # Advance to next state after each classification
        self.demo_state_index += 1
        
        return {
            "state": current_state,
            "confidence": 0.85,
            "reason": f"Demo mode cycling through {current_state} state"
        }
    
    def stop(self):
        """Stop the application and cleanup resources."""
        self.running = False
        
        # Stop telemetry collection
        if hasattr(self, 'collector'):
            self.collector.stop_listeners()
        
        # Stop audio
        if hasattr(self, 'audio_engine'):
            self.audio_engine.cleanup()
        
        # Print session summary
        if hasattr(self, 'logger'):
            self.logger.print_session_summary()
        
        print("DevAura stopped.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DevAura - Ambient Music Engine for Developers")
    parser.add_argument(
        "--demo", 
        action="store_true", 
        help="Run in demo mode (no telemetry collection or Claude API calls)"
    )
    
    args = parser.parse_args()
    
    app = DevAura(demo_mode=args.demo)
    app.start()


if __name__ == "__main__":
    main()