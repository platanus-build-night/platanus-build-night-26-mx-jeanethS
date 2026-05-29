# OpenCode Delegation Guide

A comprehensive step-by-step guide for delegating coding tasks to OpenCode CLI within Hermes Agent workflows.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup & Verification](#setup--verification)
3. [Delegation Patterns](#delegation-patterns)
4. [Common Use Cases](#common-use-cases)
5. [TUI Controls](#tui-controls)
6. [Flags & Options](#flags--options)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Requirements

- **OpenCode CLI** installed
- **Git repository** (recommended for code tasks)
- **Provider authentication** configured
- **Hermes Agent** with terminal and process tools

### Installation

Install OpenCode globally:

```bash
# Via npm
npm i -g opencode-ai@latest

# Or via Homebrew (macOS)
brew install anomalyco/tap/opencode

# Verify installation
opencode --version
```

### Authentication Setup

Configure your AI provider credentials:

```bash
# Interactive login
opencode auth login

# Or set environment variables
export OPENROUTER_API_KEY=your_key_here
# Other providers: ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.
```

Verify authentication is configured:

```bash
opencode auth list
```

You should see at least one provider available.

---

## Setup & Verification

### 1. Check OpenCode Installation

```bash
terminal(command="opencode --version")
```

Expected output: Version number (e.g., `1.2.0`)

### 2. Verify Authentication

```bash
terminal(command="opencode auth list")
```

Expected output: List of configured providers

### 3. Run Smoke Test

```bash
terminal(command="opencode run 'Respond with exactly: OPENCODE_SMOKE_OK'")
```

Expected output: Contains `OPENCODE_SMOKE_OK` without errors

### 4. Check Binary Path (if issues occur)

```bash
terminal(command="which -a opencode")
terminal(command="opencode --version")
```

This helps diagnose cases where different shell environments resolve different binaries.

---

## Delegation Patterns

### Pattern 1: One-Shot Tasks (Recommended for Simple Work)

**When to use:**
- Bounded, well-defined tasks
- Tasks that don't require iteration
- Quick code generation or refactoring
- No user interaction needed

**Syntax:**

```bash
terminal(
  command="opencode run 'Your task description here'",
  workdir="~/your/project"
)
```

**Example 1: Basic task**

```bash
terminal(
  command="opencode run 'Add retry logic with exponential backoff to the API client'",
  workdir="~/devaura"
)
```

**Example 2: With file context**

```bash
terminal(
  command="opencode run 'Review this config for security issues' -f config.yaml -f .env.example",
  workdir="~/devaura"
)
```

**Example 3: With model thinking enabled**

```bash
terminal(
  command="opencode run 'Debug why the audio crossfade produces clicks' --thinking",
  workdir="~/devaura"
)
```

**Example 4: Force specific model**

```bash
terminal(
  command="opencode run 'Refactor the collector module for clarity' --model openrouter/anthropic/claude-sonnet-4",
  workdir="~/devaura"
)
```

**Advantages:**
- Simple, no PTY required
- Automatic exit when complete
- Good for CI/CD and automation
- Clear success/failure status

**Limitations:**
- Can't respond to interactive prompts
- No real-time progress updates
- All context must fit in initial prompt

---

### Pattern 2: Interactive Sessions (For Complex Work)

**When to use:**
- Multi-step tasks requiring iteration
- Tasks where you need to provide feedback
- Long-running work with progress checks
- Exploratory coding sessions

**Step 1: Start OpenCode in Background**

```bash
terminal(
  command="opencode",
  workdir="~/devaura",
  background=true,
  pty=true
)
```

This returns a `session_id`. Save it for subsequent commands.

**Step 2: Send Initial Prompt**

```bash
process(
  action="submit",
  session_id="<session_id>",
  data="Implement audio crossfading without clicks and add tests"
)
```

**Step 3: Monitor Progress**

Quick check:
```bash
process(action="poll", session_id="<session_id>")
```

Detailed logs:
```bash
process(action="log", session_id="<session_id>", limit=50)
```

**Step 4: Send Follow-Up Commands**

```bash
process(
  action="submit",
  session_id="<session_id>",
  data="Now add tremolo effect to the audio buffer"
)
```

**Step 5: Exit Session**

Gracefully with Ctrl+C:
```bash
process(action="write", session_id="<session_id>", data="\x03")
```

Or force kill if needed:
```bash
process(action="kill", session_id="<session_id>")
```

**Step 6: Resume Later (if needed)**

```bash
# Continue last session
terminal(
  command="opencode -c",
  workdir="~/devaura",
  background=true,
  pty=true
)

# Continue specific session
terminal(
  command="opencode -s <session_id>",
  workdir="~/devaura",
  background=true,
  pty=true
)
```

**Advantages:**
- Real-time iteration and feedback
- Progress updates available
- Can adapt based on intermediate results
- Good for exploratory work

**Limitations:**
- Requires PTY mode
- More complex to orchestrate
- Need to monitor progress manually
- Session management overhead

---

## Common Use Cases

### Use Case 1: Implement a New Feature

```bash
terminal(
  command="opencode run 'Add a --demo mode to main.py that cycles through cognitive states without Claude API calls. Include fallback metrics generation and state cycle logic.'",
  workdir="~/devaura"
)
```

### Use Case 2: Code Review

```bash
terminal(
  command="opencode pr 42",
  workdir="~/devaura",
  pty=true
)
```

Or review in isolated environment:

```bash
terminal(
  command="cd /tmp/review && git clone https://github.com/user/repo.git . && opencode run 'Review classifier.py and audio.py for bugs, edge cases, and performance issues. Report findings with severity levels.'",
  pty=true
)
```

### Use Case 3: Bug Fix with Tests

```bash
terminal(
  command="opencode run 'Fix the window switching counter in collector.py - it should only increment when switching to a different window, not on repeated checks. Add unit tests to verify correct behavior.'",
  workdir="~/devaura"
)
```

### Use Case 4: Refactoring with Validation

```bash
# Start interactive session for refactoring
terminal(
  command="opencode",
  workdir="~/devaura",
  background=true,
  pty=true
)
```

```bash
# Send refactoring task
process(
  action="submit",
  session_id="<session_id>",
  data="Refactor the TelemetryCollector class to use dataclasses for metrics, add type hints everywhere, and update all docstrings"
)
```

```bash
# Check progress
process(action="poll", session_id="<session_id>")

# After completion, ask for tests
process(
  action="submit",
  session_id="<session_id>",
  data="Now add comprehensive unit tests for the refactored TelemetryCollector"
)
```

### Use Case 5: Documentation Generation

```bash
terminal(
  command="opencode run 'Generate detailed docstrings for every function in audio.py. Include parameter descriptions, return types, and usage examples. Ensure docstrings follow Google style.'",
  workdir="~/devaura"
)
```

### Use Case 6: Performance Optimization

```bash
terminal(
  command="opencode run 'Profile the collector.py for performance bottlenecks. Optimize the metrics calculation and listener callbacks. Ensure no memory leaks. Report timing improvements.'",
  workdir="~/devaura"
)
```

---

## TUI Controls

When running OpenCode in interactive mode, these keyboard shortcuts are available:

| Key Combination | Action |
|---|---|
| `Enter` | Submit message (may need to press twice) |
| `Tab` | Switch between agents (build/plan) |
| `Ctrl+P` | Open command palette |
| `Ctrl+X L` | Switch session |
| `Ctrl+X M` | Switch model |
| `Ctrl+X N` | New session |
| `Ctrl+X E` | Open text editor |
| `Ctrl+C` | Exit OpenCode cleanly |

**Important:** Do NOT use `/exit` — it opens an agent selector instead of exiting.

---

## Flags & Options

### Core Flags

| Flag | Short | Purpose | Example |
|---|---|---|---|
| `run 'prompt'` | | Execute task and exit | `opencode run 'Add tests'` |
| `--continue` | `-c` | Continue last session | `opencode -c` |
| `--session <id>` | `-s` | Continue specific session | `opencode -s ses_abc123` |
| `--agent <name>` | | Choose agent (build/plan) | `opencode --agent build` |
| `--model provider/model` | | Force specific model | `--model openrouter/anthropic/claude-sonnet-4` |
| `--file <path>` | `-f` | Attach file to prompt | `-f config.yaml -f .env.example` |
| `--thinking` | | Show model reasoning | `--thinking` |
| `--variant <level>` | | Reasoning effort | `--variant high` or `--variant max` |
| `--title <name>` | | Name the session | `--title "auth-refactor"` |
| `--format json` | | Machine-readable output | `--format json` |

### Examples

**Attach multiple files:**
```bash
opencode run "Review security in these config files" -f config.yaml -f .env.example -f nginx.conf
```

**Show reasoning process:**
```bash
opencode run "Debug the audio clicks issue" --thinking
```

**Force high reasoning effort:**
```bash
opencode run "Design a distributed tracing solution" --variant max
```

**Use specific model:**
```bash
opencode run "Implement OAuth" --model openrouter/anthropic/claude-opus-4-20250805
```

**Name your session:**
```bash
opencode --title "feature-x-implementation"
```

---

## Best Practices

### 1. Write Clear, Specific Prompts

**Good:**
```
Add input validation to the user registration form with the following rules:
- Email must be valid format
- Password must be at least 12 characters with uppercase, lowercase, number, and symbol
- Username must be 3-20 alphanumeric characters
- Include proper error messages for each validation failure
- Add unit tests for all validation rules
```

**Avoid:**
```
Fix the registration form
```

### 2. Choose the Right Pattern

- **One-shot** for well-defined, bounded tasks
- **Interactive** for exploratory or multi-step work
- **PR reviews** for analyzing pull requests
- **Parallel tasks** with separate workdirs for independence

### 3. Provide Context When Needed

```bash
opencode run "Add retry logic to the API client with exponential backoff" \
  -f src/api_client.py \
  -f src/config.py \
  -f tests/test_api.py
```

### 4. Break Large Tasks Into Subtasks

Instead of one massive prompt:
```
Implement entire authentication system with OAuth2, JWT, sessions, password reset, 2FA, and tests
```

Break it into steps:
```
# Step 1
opencode run "Implement JWT token generation and validation with proper expiration handling"

# Step 2
opencode run "Add OAuth2 flow for Google and GitHub login"

# Step 3
opencode run "Implement password reset functionality with email verification"
```

### 5. Use Version Control for Safety

Always commit before delegating major changes:
```bash
git add -A && git commit -m "Before OpenCode refactoring"
opencode run "Refactor the entire codebase for clarity"
```

### 6. Monitor Long-Running Tasks

For interactive sessions lasting >5 minutes:
```bash
# Check progress every few minutes
process(action="poll", session_id="<session_id>")

# View full logs if something seems stuck
process(action="log", session_id="<session_id>", limit=100)
```

### 7. Verify Results

Always check the changes OpenCode made:
```bash
git diff
git status
npm test  # or your test command
```

### 8. Use Appropriate Models

- **Fast tasks (simple refactoring):** Claude Haiku or Opus 4
- **Complex tasks (architecture):** Claude Sonnet or Opus 4.1
- **PR reviews:** Claude Opus 4 (max reasoning)
- **General coding:** Claude Sonnet (good balance)

```bash
opencode run "Complex task" --model openrouter/anthropic/claude-opus-4-20250805
```

---

## Troubleshooting

### Issue: "Command not found: opencode"

**Solution:**
```bash
# Check if installed
which opencode

# If not found, reinstall
npm i -g opencode-ai@latest

# Or use full path
~/.npm/bin/opencode run "task"
```

### Issue: Authentication Failed

**Solution:**
```bash
# List configured providers
opencode auth list

# Re-authenticate
opencode auth login

# Set env var directly
export OPENROUTER_API_KEY=sk_...
opencode run "task"
```

### Issue: Binary Path Mismatch

Different shells may resolve different OpenCode versions:

**Solution:**
```bash
# Check all available paths
which -a opencode

# Use explicit path if needed
/usr/local/bin/opencode run "task"
```

### Issue: Interactive Session Appears Stuck

**Solution:**
```bash
# Check logs before killing
process(action="log", session_id="<session_id>")

# Give it more time if processing
time.sleep(10)
process(action="poll", session_id="<session_id>")

# Force exit with Ctrl+C
process(action="write", session_id="<session_id>", data="\x03")

# Or kill if necessary
process(action="kill", session_id="<session_id>")
```

### Issue: TUI Not Responding to Input

**Solution:**
- Ensure `pty=true` is set on the terminal call
- Try pressing Enter twice to submit
- Use Ctrl+C (`\x03`) to exit, not `/exit`

### Issue: "Enter may need to be pressed twice"

**Explanation:** In PTY mode, the first Enter finalizes text input, the second sends it.

**Solution:** Press Enter twice when submitting messages in interactive mode.

### Issue: Parallel OpenCode Sessions Interfering

**Solution:** Use separate working directories:
```bash
# Session 1
terminal(command="opencode run '...'", workdir="/tmp/task-1", background=true)

# Session 2
terminal(command="opencode run '...'", workdir="/tmp/task-2", background=true)
```

### Issue: Model or Provider Not Available

**Solution:**
```bash
# Check available models
opencode run "task" --model openrouter/anthropic/claude-sonnet-4

# Or let OpenCode choose default
opencode run "task"  # Uses default configured provider
```

---

## Quick Reference

### Start a One-Shot Task
```bash
terminal(command="opencode run 'Your task here'", workdir="~/project")
```

### Start Interactive Session
```bash
terminal(command="opencode", workdir="~/project", background=true, pty=true)
# Returns: session_id
```

### Submit to Interactive Session
```bash
process(action="submit", session_id="<session_id>", data="Your follow-up here")
```

### Check Progress
```bash
process(action="poll", session_id="<session_id>")
```

### View Logs
```bash
process(action="log", session_id="<session_id>")
```

### Exit Session
```bash
process(action="write", session_id="<session_id>", data="\x03")
```

### Review a PR
```bash
terminal(command="opencode pr 42", workdir="~/project", pty=true)
```

---

## Summary

**Choose one-shot for:** Simple, bounded tasks  
**Choose interactive for:** Complex, iterative work  
**Always provide:** Clear prompts with context  
**Always verify:** Results with `git diff` and tests  
**Remember:** Use Ctrl+C to exit, not `/exit`  

Happy delegating! 🚀