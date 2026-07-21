# aiguard-strands — map for agents

A small reference integration, not a framework: **Trend Vision One AI Guard**
wrapped around an **AWS Strands** agent on **Bedrock**. Two parts — scan an
LLM app for vulnerabilities (TMAS), then guard it in production (AI Guard).

## Layout

```
aig.py              ← THE LIBRARY. Only place that talks to the AI Guard API.
demo.py              interactive CLI walkthrough of the guarded pipeline
demo_app.py          ⚠️ deliberately vulnerable Flask app — TMAS scan target only,
                     never a usage example to copy from
evals/               live evals, NOT pytest unit tests (see below)
scanner/             TMAS AI Scanner config
docs/                deep-dive guides (ai-guard.md, ai-scanner.md)
images/              screenshots referenced by README
```

## Hard rules

- **`aig.py` is the only place that constructs the AI Guard request** (URL,
  headers, region-host logic). Everything else — `demo.py`, `evals/*` —
  imports `ai_guard_check_prompt`/`ai_guard_check_response` from it. Do not
  copy the HTTP call into a new script; that's exactly how this repo drifted
  before (three divergent copies, only one of which failed closed).
- **Fail closed, always.** `ai_guard_check_prompt`/`ai_guard_check_response`
  never raise — a missing key, timeout, or non-200 all return
  `{"action": "Block", "reasons": [...]}`. If you touch these functions,
  keep that contract: callers (`demo.py`'s `show_guard_result`) render
  whatever dict comes back generically, they don't branch on exceptions.
- **`evals/` scripts cost real money and hit a real API** — Bedrock +
  Trend Vision One, no mocks. They're named `*_eval.py`, not `test_*.py`,
  specifically so a test runner won't auto-discover and run them. Don't
  rename them back to `test_`.
- **Region-host gotcha:** the `us` Vision One region has no subdomain
  (`api.xdr.trendmicro.com`); every other region does
  (`api.{region}.xdr.trendmicro.com`). This lives in exactly one place —
  `aig.py`'s `_v1_host` construction — don't reintroduce a second copy.
- **`demo_app.py`'s system prompt is intentionally exploitable.** It exists
  so TMAS has something to attack. Never harden it and never use it as a
  pattern for a real app.

## Running things

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.sh   # fill in V1_API_KEY, V1_REGION, AWS_PROFILE
source .env.sh

python demo.py                              # interactive CLI
python evals/batch_eval.py                  # 100-prompt live eval ($, real calls)
python evals/pii_eval.py                    # 40-prompt PII/jailbreak eval (needs V1_REGION=sg)
python demo_app.py --dirty                  # scan target, then in another shell:
tmas aiscan llm --config scanner/config-sample.yaml
```

## Before editing

- Changing `aig.py`'s public function names/signatures breaks `demo.py` and
  both `evals/*` scripts — grep for the name across the repo first.
- No test suite exists (the evals aren't it — see above). Manual run is the
  only verification available; there are no mocked credentials.
