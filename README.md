# aiguard-strands

**Secure your Bedrock Application— AI Scanner + AI Guard on AWS Strands Agents**

## TL;DR

| Step | What | How |
|---|---|---|
| 1 | **Scan** — attack your own LLM before you ship | `python demo_app.py --dirty` → `tmas aiscan llm --config config-sample.yaml` |
| 2 | **Guard** — block threats in production | Two HTTP calls in `aig.py` wrapping every prompt in and every response out |
| 3 | **Demo** — see it live | `python demo.py` — pick a category, watch Allow/Block in real time |

Needs: Vision One API key · AWS Bedrock access (us-east-2) · Python 3.10+

---

## What's in This Repo

| File | What it does |
|---|---|
| `aig.py` | Core AI Guard helpers (input + output guardrails) |
| `demo_app.py` | Simulated enterprise AI app (FinSight) — Flask server wrapping Bedrock with a vulnerable system prompt; TMAS scan target |
| `demo.py` | Interactive CLI: pick a category, watch the full pipeline in real time |
| `test_batch.py` | 100-prompt batch test (70% benign / 30% malicious) via Strands parallel graph |
| `test_pii.py` | 40-prompt PII + jailbreak test corpus |
| `config-sample.yaml` | Ready-to-use TMAS AI Scanner config for this stack |

---

## Quick Start

```bash
# 1. Python 3.10+ required (strands-agents constraint)
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Set credentials
cp .env.example .env.sh   # fill in V1_API_KEY, V1_REGION, AWS_PROFILE
source .env.sh

# 3. Run the interactive demo
python demo.py
```

---

## Docs

→ **[Part 1 — AI Scanner](docs/ai-scanner.md)** — install TMAS, run 59 attacks against your LLM, read the results

→ **[Part 2 — AI Guard](docs/ai-guard.md)** — block threats at runtime: architecture, code, test results, performance

---

*Stack: AWS Strands Agents SDK · Amazon Bedrock Claude Haiku 4.5 · Trend Vision One AI Guard · TMAS v2.203.0 · Singapore XDR region · Bedrock region us-east-2*
