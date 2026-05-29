# DevAura Team Roadmap

## Goal

Build DevAura as a Python-only ambient coding companion that collects developer behavior signals, classifies cognitive state with Claude, generates adaptive procedural music, and logs the session for a live demo.

The application should run silently in the background, sample telemetry on an interval, classify the current state, update the music without interrupting the user, and produce a readable session timeline.

## Supported Cognitive States

- `flow`
- `stuck`
- `debugging`
- `reviewing`
- `context_switching`

## Target File Structure

```text
devaura/
├── main.py
├── collector.py
├── classifier.py
├── audio.py
├── logger.py
├── config.py
├── requirements.txt
└── README.md
```

## Team Ownership

### Person 1: Signal Collection And Runtime Loop

Owns:

- `collector.py`
- `main.py`
- `config.py`
- local setup and integration flow

Responsibilities:

- Create the Python project structure.
- Add all configuration constants to `config.py`.
- Implement keyboard telemetry using `pynput`.
- Track total keystrokes during each sample window.
- Track backspace count during each sample window.
- Calculate approximate WPM.
- Track idle seconds since last keystroke.
- Implement mouse movement tracking.
- Calculate mouse distance traveled during each sample window.
- Track active window title using `pygetwindow`.
- Count active window switches.
- Read system CPU percent using `psutil`.
- Return a normalized metrics dictionary from `collector.py`.
- Build the main application loop in `main.py`.
- Wire collector, classifier, audio, and logger together.
- Handle graceful shutdown with `Ctrl+C`.
- Make sure telemetry failures do not crash the app.

Expected collector output:

```python
{
    "wpm": 0.0,
    "backspace_ratio": 0.0,
    "active_window": "Cursor",
    "window_switches": 0,
    "mouse_distance": 0.0,
    "cpu_percent": 0.0,
    "idle_seconds": 0.0,
}
```

Completion checklist:

- Metrics print successfully in the terminal.
- Metrics reset after each sample window.
- App can run continuously.
- App exits cleanly.
- `main.py` can call placeholder classifier, audio, and logger modules.

## Person 2: Claude Classifier And Session Logger

Owns:

- `classifier.py`
- `logger.py`
- classifier prompt
- response validation
- terminal and file logs

Responsibilities:

- Implement Anthropic client setup.
- Read `ANTHROPIC_API_KEY` from the environment.
- Send telemetry metrics to Claude as JSON.
- Use a strict system prompt that only allows the supported states.
- Request JSON-only output.
- Parse the Claude response.
- Validate that the returned state is supported.
- Validate that confidence is a float between `0.0` and `1.0`.
- Validate that the response includes a one-sentence reason.
- Add fallback behavior when the Claude call fails.
- Log each cycle to the terminal.
- Log each cycle to `session.log`.
- Add ANSI terminal colors per state.
- Store session entries in memory.
- Print a final session summary on shutdown.
- Include state percentages in the summary.
- Detect and print the strongest continuous `flow` window.

Classifier response contract:

```python
{
    "state": "flow",
    "confidence": 0.91,
    "reason": "Steady typing with low backspace ratio and no window switching."
}
```

Recommended classifier fallback:

- If Claude fails and a previous state exists, keep the previous state.
- If Claude fails and no previous state exists, use `reviewing`.
- Log the failure reason.
- Do not stop the application.

Completion checklist:

- Claude API call works with live metrics.
- Invalid JSON responses are handled safely.
- Unsupported states are rejected.
- Logs are readable during a demo.
- Final session summary prints on shutdown.

## Person 3: Procedural Audio Engine And Demo Polish

Owns:

- `audio.py`
- sound design
- generated audio buffers
- playback and transition smoothness
- demo mode support

Responsibilities:

- Initialize `pygame.mixer`.
- Define one chord map per cognitive state.
- Generate sine waves with `numpy`.
- Mix multiple frequencies into a stereo buffer.
- Add a soft sub-bass root layer.
- Apply an ADSR envelope.
- Apply subtle tremolo.
- Normalize output to avoid clipping.
- Convert generated buffers into `pygame.Sound` objects.
- Loop the current state continuously.
- Avoid clicks and pops during playback.
- Implement smooth state transitions.
- Crossfade when the state changes.
- Do not restart audio if the state is unchanged.
- Tune every state so the result stays pleasant and background-safe.
- Add a manual demo mode if live telemetry or API access fails.

Chord map:

```python
CHORDS = {
    "flow": [261.63, 329.63, 392.00, 523.25],
    "stuck": [261.63, 311.13, 392.00],
    "debugging": [293.66, 369.99, 440.00],
    "reviewing": [174.61, 220.00, 261.63],
    "context_switching": [261.63, 329.63, 440.00],
}
```

Audio rules:

- Maximum volume should be `0.35`.
- Attacks should be soft.
- Notes should fade in and out.
- State changes should crossfade.
- The music should never become harsh or distracting.
- All audio should be generated in Python.
- No external audio files should be required.

Completion checklist:

- Audio plays continuously.
- Each state has a distinct sound.
- State changes are smooth.
- Volume stays low.
- Demo mode can force state changes.

## Shared Technical Contracts

Put shared constants in `config.py`:

```python
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
```

All modules should communicate using plain Python dictionaries. Avoid passing raw Claude responses or raw listener objects between modules.

## Build Sequence

### Phase 1: Project Setup

- Create the `devaura/` directory.
- Add the target files.
- Add `requirements.txt`.
- Add `.env.example`.
- Add basic `README.md`.
- Confirm dependencies install.
- Confirm the app can start from `main.py`.

### Phase 2: Collector Prototype

- Implement keyboard listener.
- Implement mouse listener.
- Implement active window sampling.
- Implement CPU sampling.
- Print metrics every sample cycle.
- Confirm values reset after each sample.

### Phase 3: Classifier Prototype

- Implement Anthropic client.
- Add strict classification prompt.
- Send metrics to Claude.
- Parse JSON response.
- Validate response fields.
- Print state, confidence, and reason.

### Phase 4: Audio Prototype

- Initialize audio playback.
- Generate one chord buffer.
- Loop the buffer.
- Generate buffers for all states.
- Add envelope and tremolo.
- Add volume control.

### Phase 5: Integration

- Connect collector output to classifier input.
- Connect classifier state to audio engine.
- Connect classifier result to logger.
- Keep previous audio state when classification fails.
- Keep app running during recoverable errors.

### Phase 6: Session Logging

- Write one log entry per cycle.
- Add colored terminal output.
- Save entries to `session.log`.
- Track session start and end.
- Print final summary.

### Phase 7: Transition Polish

- Add crossfades.
- Prevent repeated audio restarts.
- Smooth state changes.
- Tune chord density and volume.
- Test all states manually.

### Phase 8: Demo Preparation

- Add a `--demo` mode.
- Let demo mode cycle through states without Claude.
- Add optional keyboard shortcuts for forced states.
- Add example output to `README.md`.
- Prepare a short demo script.
- Verify the app works without network access in demo mode.

## Demo Script

1. Start DevAura from the terminal.
2. Show the terminal printing live telemetry.
3. Type steadily in a code file to demonstrate `flow`.
4. Pause and use repeated backspaces to demonstrate `stuck`.
5. Switch windows rapidly to demonstrate `context_switching`.
6. Trigger or simulate `debugging`.
7. Show `session.log`.
8. Stop the app and show the session summary.

## Risk Checklist

- `pynput` may need OS permissions.
- `pygetwindow` may fail depending on the environment.
- Claude API may fail or return malformed JSON.
- Audio can click if buffers are restarted too aggressively.
- The live demo should not depend entirely on network access.
- A manual demo mode is required for reliability.

## Definition Of Done

- App starts from `main.py`.
- Live telemetry is collected.
- Claude classification works.
- Audio changes based on state.
- Logs are written to terminal and file.
- App exits cleanly.
- Final summary is printed.
- Demo mode works without Claude.
- README explains setup, environment variables, and demo flow.
