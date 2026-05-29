# DevAura

Ambient music engine that samples developer behavioral telemetry every 30 seconds, classifies cognitive state via Claude, and plays procedurally generated music matching that state — all in pure Python, silently in the background.

## Features

- **Real-time Telemetry Collection**: Monitors keystrokes, mouse movement, window switching, and system metrics
- **AI-Powered State Classification**: Uses Claude to analyze developer behavior and classify cognitive states
- **Procedural Audio Generation**: Creates ambient music using pure Python synthesis (no audio files required)
- **Session Logging**: Tracks your coding sessions with colored terminal output and detailed logs
- **Demo Mode**: Works offline for demonstrations and testing

## Cognitive States

DevAura recognizes five distinct developer cognitive states:

- **Flow**: Steady, productive typing with minimal interruptions
- **Stuck**: Low typing activity, high backspace ratio, or long idle periods  
- **Debugging**: Variable typing patterns with moderate window switching
- **Reviewing**: Low typing activity, stable window focus, minimal backspaces
- **Context Switching**: High window switching with erratic mouse movement

Each state triggers a unique ambient soundscape designed to be pleasant background music.

## Installation

1. **Clone and navigate to the project:**
   ```bash
   cd devaura
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
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

## Sample Output

```
DevAura starting...
Press Ctrl+C to stop
--------------------------------------------------
[14:23:15] FLOW (conf: 0.89) | WPM: 45.2 | Backspace: 0.12 | Window: Visual Studio Code
  → Steady typing with low backspace ratio and no window switching.
[14:23:45] DEBUGGING (conf: 0.76) | WPM: 23.1 | Backspace: 0.28 | Window: Chrome - Stack Overflow
  → Increased backspace ratio and window switching suggests debugging.
```

## Project Structure

```
devaura/
├── main.py           # Main application entry point
├── collector.py      # Telemetry collection (keyboard, mouse, system)
├── classifier.py     # Claude API integration for state classification
├── audio.py          # Procedural audio generation with crossfading
├── logger.py         # Session logging with ANSI colors and file output
├── config.py         # Configuration constants and chord mappings
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Audio Design

DevAura generates all audio procedurally using:
- **Sine wave synthesis** with harmonic overtones
- **ADSR envelopes** for smooth attack and release
- **Tremolo effects** for subtle movement
- **Crossfading** for seamless state transitions
- **Sub-bass enhancement** for warmth
- **Volume limiting** to stay background-appropriate (max 0.35)

Each cognitive state has its own chord progression optimized for ambient listening.

## Requirements

- **Python 3.7+**
- **Operating System**: Windows, macOS, or Linux
- **Permissions**: Input monitoring access may be required for `pynput`
  - macOS: Grant Accessibility permissions when prompted
  - Linux: May need to run with appropriate permissions or add user to `input` group

## Session Logging

DevAura creates detailed session logs including:
- Real-time colored terminal output
- Persistent session file (`session.log`)
- Final session summary with state percentages
- Detection of longest continuous flow windows

## Environment Variables

```bash
ANTHROPIC_API_KEY=your_claude_api_key_here
```

## Demo Script

1. Start DevAura: `python main.py --demo`
2. Watch terminal output showing live state changes
3. Listen to audio transitions between different cognitive states
4. Stop with Ctrl+C to see session summary
5. Check `session.log` for detailed session data

## Troubleshooting

**Input monitoring fails**: Grant accessibility permissions on macOS or run with appropriate privileges on Linux.

**pygetwindow errors**: Window tracking may fail on some systems - this is handled gracefully with fallbacks.

**Audio clicks/pops**: Ensure no other applications are competing for audio resources.

**API errors**: Check your `ANTHROPIC_API_KEY` or use `--demo` mode for offline operation.

## Architecture

Five modules communicate via plain Python dictionaries:

```
collector.py  →  classifier.py  →  audio.py
                      ↓
                 logger.py
```

Data flows from telemetry collection through AI classification to audio generation and logging, with robust error handling at each stage.