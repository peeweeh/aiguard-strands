# demo.py — Design Specification

Interactive CLI demo for the aiguard-strands integration.
Lets a user pick from a curated menu of prompts and watch the full
AI Guard → Strands/Bedrock → AI Guard pipeline in real time.

---

## Purpose

- Demonstrate the end-to-end security pipeline without any setup friction
- Show clearly what gets blocked vs. allowed, and why
- Suitable for a screen-share or live demo at a talk or meeting

---

## Architecture

```
main()
  └─ build_strands_agent()          ← once at startup
  └─ main_menu()
       └─ prompt_menu(category)
            └─ run_prompt(agent, prompt)
                 ├─ ai_guard_check_prompt()   ← Step 1
                 ├─ agent(prompt)             ← Step 2 (only if allowed)
                 └─ ai_guard_check_response() ← Step 3 (only if allowed)
```

Each step shows a live spinner while the HTTP/Bedrock call is in-flight.

---

## Prompt Catalogue

| Category | Key | Icon | Prompts | Expected outcome |
|---|---|---|---|---|
| Benign | `1` | ✅ | 4 general questions | All pass input + output guard |
| Harmful | `2` | 💣 | Pipe bomb, meth synthesis, ransomware, VX nerve agent | All blocked at input guard |
| Jailbreak | `3` | 🔓 | DAN override, Prometheus persona, red-team social engineering, grandma jailbreak | All blocked at input guard |
| PII Leak | `4` | 🪪 | Singapore NRIC, credit card, US SSN, AWS credentials dump | All blocked at input guard |

---

## User Flow

```
[startup]
  Clear screen → banner → "Building Strands agent…" spinner → "✅ Agent ready"

[main menu]
  Pick a category: 1 / 2 / 3 / 4 / q

[prompt menu]
  Pick a prompt: 1 / 2 / 3 / 4 / b (back)

[run_prompt]
  Display prompt (word-wrapped at 55 chars)

  ── AI Guard (input) ──────────────────
    ❌ BLOCKED
    ↳ Harmful Scanners exceeding threshold: SH, V
    ➜ Prompt never reached the LLM.

  OR (if allowed):

  ── AI Guard (input) ──────────────────
    ✅ ALLOWED

  ── Strands → Bedrock (Claude Haiku 4.5) ──
    ⠙ Calling Claude Haiku via Bedrock...
    [response text, capped at 20 display lines]

  ── AI Guard (output) ─────────────────
    ✅ ALLOWED
    ➜ Safe response delivered.

[after result]
  [Enter] try another   [q] quit
```

---

## Implementation Details

### Imports

All AI Guard and Strands logic is imported directly from `aig.py`:

```python
from aig import (
    APPLY_GUARDRAILS_URL,
    MODEL_ID,
    ai_guard_check_prompt,
    ai_guard_check_response,
    build_strands_agent,
)
```

### Spinner

`threading.Thread` running in daemon mode. Frames cycle through braille dots.
`stop()` clears the line with a carriage-return overwrite.

### Colour

Pure ANSI escape codes — no third-party library required:

| Colour | Use |
|---|---|
| `GREEN` | Allowed |
| `RED` | Blocked |
| `YELLOW` | Reasons / warnings |
| `CYAN` | Headers and loading |
| `DIM` | Secondary text, dividers |
| `BOLD` | Section titles |

### Agent lifecycle

`build_strands_agent()` is called **once** at startup, not per-prompt.
This avoids repeated boto3 session creation and shows realistic inference latency.

### Word wrap

Prompts and LLM responses are word-wrapped at 55 characters for clean
terminal display. LLM responses are capped at 20 display lines with a
`… (truncated)` indicator if longer.

---

## Files

| File | Role |
|---|---|
| `demo.py` | This demo — all UI, menus, spinner, display |
| `aig.py` | Core pipeline — imported by demo.py |
| `.env.sh` | Credentials — sourced before running (gitignored) |

---

## Running

```bash
source .env.sh
python demo.py
```

Requirements: Python 3.10+, `.venv` activated, `V1_API_KEY` and `AWS_PROFILE` set.

---

## Non-Goals

- No free-form text input — menu-driven only
- No conversation history — each prompt is one-shot
- No live policy editor — policy changes require the Vision One console
