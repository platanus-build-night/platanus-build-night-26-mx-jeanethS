# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: AuraDev

Ambient music engine that samples developer behavioral telemetry every 30 seconds, classifies cognitive state via Claude, and plays procedurally generated music matching that state — all in pure Python, silently in the background.

**Stack:** Python only. No audio files. No external synths.  
**Entry point:** `python auradev/main.py`

## Setup

```bash
pip install anthropic pynput psutil pygetwindow numpy pygame
```

Requires `ANTHROPIC_API_KEY` in the environment. Copy `.env.example` to `.env` and fill in the key.

## Running

```bash
# Normal mode (live telemetry + Claude classification)
python auradev/main.py

# Demo mode (cycles through states without Claude or network)
python auradev/main.py --demo
```

## Architecture

Five modules wired together in `main.py`. Data flows as plain Python dicts — never raw Claude responses or raw listener objects.

```
collector.py  →  classifier.py  →  audio.py
                      ↓
                 logger.py
```

### Module Contracts

**`collector.py`** — samples every `SAMPLE_INTERVAL` seconds, returns:
```python
{
  "wpm": float,
  "backspace_ratio": float,
  "active_window": str,
  "window_switches": int,
  "mouse_distance": float,
  "cpu_percent": float,
  "idle_seconds": float
}
```
Metrics reset after each sample window. Telemetry failures must not crash the app.

**`classifier.py`** — one Claude API call per cycle using `claude-opus-4-7`, max 100 tokens, temperature 0.2. Returns:
```python
{"state": "flow", "confidence": 0.91, "reason": "<one sentence>"}
```
Fallback: keep previous state if one exists, else use `"reviewing"`. Log failures but don't stop the app.

**`audio.py`** — pure numpy + pygame synthesis. No audio files. Generates 3-second sine wave buffers, applies ADSR + tremolo, crossfades on state change (`CROSSFADE_SECONDS`). Does not restart audio if state is unchanged. Max volume: `0.35`.

**`logger.py`** — one entry per cycle to terminal (ANSI colors) and `session.log`. Prints final summary on shutdown: duration, state percentages, peak flow window.

**`config.py`** — single source of truth:
```python
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SAMPLE_INTERVAL   = 30
CROSSFADE_SECONDS = 3.0
VOLUME            = 0.35
LOG_FILE          = "session.log"
STATES            = ["flow", "stuck", "debugging", "reviewing", "context_switching"]
```

### Cognitive States → Chord Map
```python
CHORDS = {
    "flow":               [261.63, 329.63, 392.00, 523.25],  # C major + octave
    "stuck":              [261.63, 311.13, 392.00],           # C minor, soft
    "debugging":          [293.66, 369.99, 440.00],           # D major, brighter
    "reviewing":          [174.61, 220.00, 261.63],           # F–A–C, low drone
    "context_switching":  [261.63, 329.63, 440.00],           # C–E–A, open sus2
}
```

## Audio Rules

- Max volume: `0.35` — always background, never foreground
- ADSR: attack 0.3s, decay 0.2s, sustain 0.8, release 0.5s
- Tremolo: LFO at 0.5 Hz, depth 0.05
- Crossfade on state change: 3s linear blend
- Add soft sub-bass sine at root/2 for warmth
- No sharp onsets — notes always fade in

## Terminal Colors (logger.py)

| State | Color |
|---|---|
| `flow` | green |
| `stuck` | red |
| `debugging` | yellow |
| `reviewing` | cyan |
| `context_switching` | magenta |

## Known Risks

- `pynput` requires OS-level input monitoring permissions (macOS: Accessibility; Linux: may need root or `input` group).
- `pygetwindow` can fail in some environments — handle gracefully and fall back to an empty string.
- Claude may return malformed JSON — validate all three fields (`state`, `confidence`, `reason`) before using.
- Audio buffer restarts cause clicks — crossfade instead of stopping/starting.
- Demo mode must work entirely offline (no Claude calls).
