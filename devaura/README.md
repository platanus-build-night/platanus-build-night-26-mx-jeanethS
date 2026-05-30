# DevAura

Ambient music engine that samples developer behavioral telemetry every 30 seconds, classifies cognitive state via Claude, and plays procedurally generated music matching that state — all in pure Python, silently in the background.

## Features

- **Real-time Telemetry Collection**: Monitors keystrokes, mouse movement, window switching, and system metrics
- **AI-Powered State Classification**: Uses Claude to analyze developer behavior and classify cognitive states
- **Procedural Audio Generation**: Creates ambient music using pure Python synthesis (no audio files required)
- **Synthesized Drum Beats**: Each cognitive state has a unique rhythm pattern (kick, snare, hi-hat)
- **Session Logging**: Tracks your coding sessions with colored terminal output and detailed logs
- **Visual Dashboard**: ASCII art logo, state icons, waveform visualizer, and metrics display
- **Demo Mode**: Works offline for demonstrations and testing

## Cognitive States

DevAura recognizes five distinct developer cognitive states, each with its own sound and rhythm:

| State | Sound | BPM | Rhythm |
|-------|-------|-----|--------|
| **Flow** | C major pentatonic (bright) | 90 | Steady 4/4 groove |
| **Stuck** | A minor pentatonic (somber) | 60 | Sparse, glitchy |
| **Debugging** | D major pentatonic (focused) | 100 | Syncopated, analytical |
| **Reviewing** | F major pentatonic (low drone) | 70 | Minimal, meditative |
| **Context Switching** | G major pentatonic (open) | 110 | Busy, shifting |

## Installation

1. **Clone and navigate to the project:**
   ```bash
   cd devaura
   ```

2. **Create a Python 3.13 virtual environment (recommended):**
   ```bash
   py -3.13 -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Mac/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp ../.env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

## Usage

### Normal Mode (with Claude API)
```bash
python main.py
```
Requires `ANTHROPIC_API_KEY` in your environment.

### Demo Mode (offline)
```bash
python main.py --demo
```
Cycles through all states without requiring network access or API keys.

### Command Line Options

```bash
python main.py [OPTIONS]

Options:
  --demo              Run in demo mode (no API calls)
  --interval SECONDS  Sample interval (default: 30, demo: 5)
  --max-cycles N      Maximum cycles to run (default: unlimited)
  --no-drums          Disable drum beats (melody only)
  --drum-volume FLOAT Drum volume 0.0-1.0 (default: 0.4)
```

### Examples

```bash
# Quick demo with fast cycling
python main.py --demo --interval 3 --max-cycles 10

# Melody-only mode (no drums)
python main.py --demo --no-drums

# Louder drums
python main.py --demo --drum-volume 0.7
```

## Sample Output

```
╔══════════════════════════════════════════════════════════╗
║        ♪    ∿  D E V A U R A  ∿    ♪                     ║
║        Ambient Music Engine for Developers               ║
╚══════════════════════════════════════════════════════════╝

════════════════════════════════════════════════════════════
 ~[O]~  FLOW  confidence: 85%
     ∿ ▄▅▆▆▇▇▆▅▄▃▂▁▁  ▁▂▃▄▅▆▇▇▇▆▅▄▃▂▁ ∿
     → Steady typing with low backspace ratio
────────────────────────────────────────────────────────────
  WPM        ███████░░░░░░░░░░░░░   46.7
  Backspace  ██░░░░░░░░░░░░░░░░░░   0.08
  CPU        ████░░░░░░░░░░░░░░░░   21.4%
════════════════════════════════════════════════════════════
```

## State Icons

| State | Icon |
|-------|------|
| Flow | `~[O]~` |
| Stuck | `[???]` |
| Debugging | `[:*:]` |
| Reviewing | `(o_o)` |
| Context Switching | `<==>` |

## Project Structure

```
devaura/
├── main.py           # Main application entry point
├── collector.py      # Telemetry collection (keyboard, mouse, system)
├── classifier.py     # Claude API integration for state classification
├── audio.py          # Procedural audio + drum synthesis
├── logger.py         # Session logging with ANSI colors and visuals
├── config.py         # Configuration constants and chord mappings
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Audio Design

DevAura generates all audio procedurally using:
- **Layered oscillators**: Sine + triangle waves with harmonic overtones
- **ADSR envelopes**: 0.5s attack for pad-like sound
- **Tremolo & pulse LFO**: Subtle rhythmic movement synced to BPM
- **Synthesized drums**: Kick (pitch-dropping sine), snare (tone + noise), hi-hat (filtered noise)
- **State-specific patterns**: 16-step drum sequences unique to each cognitive state
- **Crossfading**: 3-second smooth transitions between states
- **Sub-bass enhancement**: Root/2 frequency for warmth
- **Stereo panning LFO**: Slow movement across the stereo field
- **Volume limiting**: Max 0.35 to stay background-appropriate

## Drum Patterns

Each state has a unique 16-step drum pattern:

- **Flow**: Classic 4/4 kick-snare-hat groove (productivity beat)
- **Stuck**: Sparse, irregular hits (reflecting uncertainty)
- **Debugging**: Syncopated kicks with busy hi-hats (problem-solving energy)
- **Reviewing**: Minimal kicks and occasional hats (meditative)
- **Context Switching**: Dense, shifting pattern (mental juggling)

## Requirements

- **Python 3.10+** (3.13 recommended for full audio support)
- **Operating System**: Windows, macOS, or Linux
- **Permissions**: Input monitoring access may be required for `pynput`
  - macOS: Grant Accessibility permissions when prompted
  - Linux: May need to run with appropriate permissions or add user to `input` group

## Session Logging

DevAura creates detailed session logs including:
- Real-time colored terminal output with ASCII visualizations
- Persistent session file (`session.log`)
- Final session summary with state percentages
- Detection of longest continuous flow windows

## Environment Variables

```bash
ANTHROPIC_API_KEY=your_claude_api_key_here
```

## Demo Script

1. Start DevAura: `python main.py --demo`
2. Watch the ASCII dashboard showing live state changes
3. Listen to audio and drum transitions between cognitive states
4. Stop with Ctrl+C to see session summary
5. Check `session.log` for detailed session data

## Troubleshooting

**Input monitoring fails**: Grant accessibility permissions on macOS or run with appropriate privileges on Linux.

**pygetwindow errors**: Window tracking may fail on some systems - this is handled gracefully with fallbacks.

**Audio clicks/pops**: Ensure no other applications are competing for audio resources.

**API errors**: Check your `ANTHROPIC_API_KEY` or use `--demo` mode for offline operation.

**No audio (Python 3.14+)**: pygame/numpy may not be available. Use Python 3.13 or earlier, or create a venv with the included `.venv`.

## Architecture

Five modules communicate via plain Python dictionaries:

```
collector.py  →  classifier.py  →  audio.py
                      ↓
                 logger.py
```

Data flows from telemetry collection through AI classification to audio generation and logging, with robust error handling at each stage.

## License

MIT License - Built for Platanus Build Night
