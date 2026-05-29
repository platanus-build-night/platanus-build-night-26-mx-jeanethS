# DevAura — Project Spec
**Hackathon:** CDMX 12-Hour Build  
**License:** MIT  
**Stack:** Python only  
**Solo build**

---

## One-Line Pitch

An ambient music engine that reads your cognitive state from behavioral telemetry and scores your coding session like a film — in real time.

---

## Problem

Developers context-switch constantly. Focus is fragile. No tool today reflects your actual mental state back at you in a non-intrusive, ambient way. Spotify playlists are static. Lo-fi is generic. Neither adapts to *you, right now*.

---

## Solution

DevAura runs silently in the background, samples your behavioral signals every 30 seconds, asks Claude to classify your cognitive state, and plays procedurally generated music that matches it — without ever interrupting you.

---

## Cognitive States

| State | Behavioral Signal Pattern | Music Signature |
|---|---|---|
| `flow` | Steady fast typing, single window, low errors | Slow warm consonant chords, minimal movement |
| `stuck` | Long pauses, repeated backspaces, low WPM | Dissonant tension, slow pulse, unresolved |
| `debugging` | Bursts of typing, frequent window switches, high CPU | Fast irregular rhythm, minor key, nervous energy |
| `reviewing` | Slow scroll, mouse movement dominant, rare keystrokes | Sparse, near-silent, single tone drone |
| `context_switching` | Rapid window changes, mixed short bursts | Layered chaotic textures, resolves slowly |

---

## Architecture

```
┌─────────────────────────────────┐
│         Signal Collector        │  ← runs every 30s
│  pynput · psutil · pygetwindow  │
└────────────────┬────────────────┘
                 │ raw metrics dict
                 ▼
┌─────────────────────────────────┐
│        Claude Classifier        │  ← Anthropic API
│   system prompt + metrics JSON  │
│   → returns state + confidence  │
└────────────────┬────────────────┘
                 │ state label
                 ▼
┌─────────────────────────────────┐
│         Audio Engine            │  ← pure Python
│   numpy sine wave synthesis     │
│   pygame mixer for playback     │
│   crossfade between states      │
└─────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│         Session Log             │  ← demo artifact
│   timeline of states + metrics  │
│   printed to terminal / saved   │
└─────────────────────────────────┘
```

---

## File Structure

```
devaura/
├── main.py               # entry point, main loop
├── collector.py          # signal sampling (pynput, psutil, pygetwindow)
├── classifier.py         # Claude API call, returns state label
├── audio.py              # numpy sine synthesis + pygame playback
├── logger.py             # session timeline log
├── config.py             # API key, intervals, tuning params
├── requirements.txt
└── README.md
```

---

## Module Specs

### `collector.py`

Samples every `SAMPLE_INTERVAL` seconds (default: 30).

Returns a dict:

```python
{
  "wpm": float,                  # keystrokes in window / elapsed time
  "backspace_ratio": float,      # backspaces / total keystrokes
  "active_window": str,          # window title
  "window_switches": int,        # title changes since last sample
  "mouse_distance": float,       # pixels traveled
  "cpu_percent": float,          # psutil system CPU %
  "idle_seconds": float          # seconds since last keystroke
}
```

Dependencies: `pynput`, `psutil`, `pygetwindow`

---

### `classifier.py`

Single Claude API call per sample cycle.

**System prompt:**
```
You are a cognitive state classifier for a developer productivity tool.
You receive behavioral telemetry from a developer's machine sampled over 30 seconds.
Classify their current cognitive state as exactly one of:
flow | stuck | debugging | reviewing | context_switching

Respond in JSON only:
{"state": "<label>", "confidence": <0.0-1.0>, "reason": "<one sentence>"}
```

**User message:** JSON dump of the metrics dict.

Returns: `state` string, `confidence` float, `reason` string for the log.

Model: `claude-opus-4-7` (use hackathon credits)  
Max tokens: 100  
Temperature: 0.2

---

### `audio.py`

Pure numpy + pygame. No audio files. No external synths.

**Chord map per state:**

All states use consonant, calming intervals. The music never creates tension — it only shifts in pace, density, and warmth to reflect state, while always staying pleasant.

```python
CHORDS = {
  "flow":               [261.63, 329.63, 392.00, 523.25],  # C major + octave, full warm
  "stuck":              [261.63, 311.13, 392.00],           # C minor, soft and slow — gentle nudge not tension
  "debugging":          [293.66, 369.99, 440.00],           # D major, slightly brighter pace
  "reviewing":          [174.61, 220.00, 261.63],           # F–A–C, low and airy drone
  "context_switching":  [261.63, 329.63, 440.00],           # C–E–A, open sus2 feel, unrushed
}
```

**Relaxation rules (apply to all states):**
- Max volume: 0.35 — always background, never foreground
- LFO tremolo depth: 0.03 (very subtle, breath-like)
- Attack always ≥ 0.5s — no sharp onsets
- Notes fade in slowly, never pop
- Crossfade between states: 3s (longer = smoother transitions)
- Add a soft sub-bass sine at root/2 frequency for grounding warmth

**Synthesis:**
- Generate 3-second sine wave buffers per frequency
- Mix into stereo numpy array
- Apply ADSR envelope (attack 0.3s, decay 0.2s, sustain 0.8, release 0.5s)
- Add slight tremolo (LFO at 0.5Hz, depth 0.05) for organic feel
- Crossfade on state change (1.5s linear blend between old and new buffer)
- Loop seamlessly using pygame `Sound` object with channel control

---

### `logger.py`

Appends each cycle to an in-memory list and a `.log` file:

```
[14:32:01] flow         (0.91) — Steady 68wpm, single window, low errors
[14:32:31] flow         (0.87) — Continued focus, minimal switches
[14:33:01] debugging    (0.83) — CPU spike, rapid window changes detected
[14:33:31] stuck        (0.79) — High backspace ratio, long pauses
```

Terminal output uses ANSI color codes per state (green=flow, red=stuck, yellow=debugging, etc.).

At session end, prints a summary:
```
Session: 47 minutes
States:  flow 52% · debugging 24% · stuck 14% · reviewing 7% · context_switching 3%
Peak focus window: 14:32 – 14:48
```

---

### `config.py`

```python
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SAMPLE_INTERVAL   = 30      # seconds between samples
CROSSFADE_SECONDS = 3.0     # longer = smoother, more ambient transitions
VOLUME            = 0.35    # always background, never foreground
LOG_FILE          = "session.log"
```

---

## Build Order (12 hours)

| Hour | Task |
|---|---|
| 0–1 | Repo setup, `requirements.txt`, `config.py`, verify API key works |
| 1–2 | `collector.py` — get metrics dict printing to terminal |
| 2–3 | `classifier.py` — Claude call working, returning state from live data |
| 3–5 | `audio.py` — sine wave synthesis, ADSR envelope, pygame loop |
| 5–6 | `main.py` — wire everything together, basic loop running |
| 6–7 | `logger.py` — terminal colors, session summary |
| 7–9 | Polish: crossfade between states, tune chord choices by ear |
| 9–11 | README, demo run, fix edge cases, prepare presentation |
| 11–12 | Presentation prep: record a 60s screen capture of it running |

---

## Demo Script (Presentation)

1. Start DevAura, show terminal
2. Open a code file and type steadily → `flow` kicks in, warm chords
3. Deliberately spam backspace and pause → `stuck` triggers, tension chord
4. Alt-tab rapidly between windows → `context_switching` detected
5. Show the session log timeline at the end
6. Show the Claude API call raw — the actual JSON in, JSON out

**The thesis line:**  
*"Your computer already knows when you're in the zone and when you're lost. This tool just listens, thinks, and scores your session accordingly."*

---

## Requirements

```
anthropic
pynput
psutil
pygetwindow
numpy
pygame
```

Install:
```bash
pip install anthropic pynput psutil pygetwindow numpy pygame
```

---

## MIT License

```
MIT License — Copyright (c) 2026
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software.
```

---

*Generated for CDMX Hackathon — 12-hour solo build*
