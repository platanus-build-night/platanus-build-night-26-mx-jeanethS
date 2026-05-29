import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SAMPLE_INTERVAL = 30
CROSSFADE_SECONDS = 3.0
VOLUME = 0.35
LOG_FILE = "session.log"

STATES = [
    "flow",
    "stuck",
    "debugging",
    "reviewing",
    "context_switching",
]

CHORDS = {
    "flow": [261.63, 329.63, 392.00, 523.25],  # C major + octave
    "stuck": [261.63, 311.13, 392.00],         # C minor, soft
    "debugging": [293.66, 369.99, 440.00],     # D major, brighter
    "reviewing": [174.61, 220.00, 261.63],     # F–A–C, low drone
    "context_switching": [261.63, 329.63, 440.00],  # C–E–A, open sus2
}