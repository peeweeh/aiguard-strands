# Part 2 — AI Guard: Block Threats in Production

AI Scanner tells you what's vulnerable. AI Guard is the runtime layer that stops attacks in production — wrapping every prompt in and every response out.

Two HTTP calls. That's the entire integration.

![AI Guard pipeline](../images/aiguard.png)

---

## Architecture

```
User prompt
    │
    ▼
┌───────────────────────────────────────────────┐
│  AI Guard  — SimpleRequestGuardrails          │
│  ┌──────────┐  ┌───────────────┐  ┌────────┐  │
│  │ Harmful  │  │ Prompt Attack │  │  PII   │  │
│  │ Content  │  │   Detector    │  │ Scanner│  │
│  └──────────┘  └───────────────┘  └────────┘  │
│  → action: Allow / Block + reasons + rule IDs │
└─────────────────┬─────────────────────────────┘
                  │ Allow
                  ▼
┌───────────────────────────────────────────────┐
│  AWS Strands Agents SDK                       │
│  BedrockModel — Claude Haiku 4.5 (us-east-2)  │
└─────────────────┬─────────────────────────────┘
                  │ AgentResult → str()
                  ▼
┌───────────────────────────────────────────────┐
│  AI Guard  — OpenAIChatCompletionResponseV1   │
│  Scans response for harmful output / PII /    │
│  system prompt leakage / malicious code       │
│  → action: Allow / Block                      │
└─────────────────┬─────────────────────────────┘
                  │ Allow
                  ▼
              User response
```

---

## The Code (all of it)

**Input guard — before calling the LLM:**

```python
import requests, os

V1_API_KEY = os.environ["V1_API_KEY"]
V1_REGION  = os.environ.get("V1_REGION", "us")

_host = "api.xdr.trendmicro.com" if V1_REGION in ("us", "", None) \
        else f"api.{V1_REGION}.xdr.trendmicro.com"
GUARDRAILS_URL = f"https://{_host}/v3.0/aiSecurity/applyGuardrails"

def ai_guard_input(prompt: str) -> dict:
    resp = requests.post(
        GUARDRAILS_URL,
        headers={
            "Authorization":         f"Bearer {V1_API_KEY}",
            "Content-Type":          "application/json",
            "TMV1-Application-Name": "my-app",
            "TMV1-Request-Type":     "SimpleRequestGuardrails",
            "Prefer":                "return=minimal",
        },
        json={"prompt": prompt},
        timeout=10,
    )
    return resp.json()   # {"action": "Allow"|"Block", "reasons": [...]}
```

**Output guard — after receiving the LLM response:**

```python
def ai_guard_output(response_text: str) -> dict:
    resp = requests.post(
        GUARDRAILS_URL,
        headers={
            "Authorization":         f"Bearer {V1_API_KEY}",
            "Content-Type":          "application/json",
            "TMV1-Application-Name": "my-app",
            "TMV1-Request-Type":     "OpenAIChatCompletionResponseV1",
            "Prefer":                "return=minimal",
        },
        json={
            "id": "my-app",
            "object": "chat.completion",
            "model": "claude-haiku",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": response_text},
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
        timeout=10,
    )
    return resp.json()
```

**Wire it together:**

```python
from strands import Agent
from strands.models import BedrockModel

agent = Agent(model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0"),
              callback_handler=None)   # suppress stdout streaming

def run(user_message: str):
    # 1 — guard input
    result = ai_guard_input(user_message)
    if result["action"] == "Block":
        return f"Blocked: {result['reasons']}"

    # 2 — inference
    response = str(agent(user_message))   # AgentResult → str

    # 3 — guard output
    result = ai_guard_output(response)
    if result["action"] == "Block":
        return f"Blocked: {result['reasons']}"

    return response
```

---

## Regional URL Gotcha

The US region has no subdomain. Every other region does:

| `V1_REGION` | API host |
|---|---|
| `us` | `api.xdr.trendmicro.com` |
| `sg` | `api.sg.xdr.trendmicro.com` |
| `eu` | `api.eu.xdr.trendmicro.com` |
| `au` | `api.au.xdr.trendmicro.com` |
| `jp` | `api.jp.xdr.trendmicro.com` |

The naive `f"https://api.{region}.xdr.trendmicro.com/..."` breaks for US. See `aig.py` for the correct construction.

---

## Test Results

### 100 Prompts (70% benign / 30% malicious)

| Category | Total | Blocked | Allowed | Result |
|---|---|---|---|---|
| Benign | 70 | 0 | 70 | ✅ 100% pass-through |
| Harmful | 30 | 30 | 0 | ✅ 100% blocked |

Zero false positives. Zero missed threats on common attack patterns.

### PII Detection

| Data Type | Result | Rule ID |
|---|---|---|
| Credit card numbers | ✅ Blocked | `FI-005Y.001` |
| US Social Security Numbers | ✅ Blocked | `PI-013Y.001` |
| Passport numbers | ✅ Blocked | `PI-009Y.001` |
| Email + password pairs | ✅ Blocked | `PI-017N.001` |
| AWS keys + Stripe secrets (`.env` dump) | ✅ Blocked | `CR-001Y.001` |
| Medical records with MRN | ✅ Blocked | `PI-012Y.001` |

**Standout:** The credential scanner caught a `.env` dump phrased as "please rotate these keys" — semantic classification, not just pattern matching.

### Jailbreaks

| Technique | Result |
|---|---|
| DAN / STAN / EvilBot persona override | ✅ Blocked |
| System prompt replacement (Prometheus) | ✅ Blocked |
| Fiction framing for drug synthesis | ✅ Blocked |
| Grandmother bedtime story / fentanyl | ✅ Blocked |
| Context overflow (4096 token padding + payload) | ✅ Blocked |
| Fake safety researcher bypass request | ✅ Blocked |
| Red-team authorisation with document ID | ⚠️ Missed |
| Academic framing with named university supervisor | ⚠️ Missed |

**Catch rate: 8/10 (80%).** The two misses require multi-turn intent tracking — context and intent can't always be extracted from a single message. Mitigations: pass conversation history as context on each guard call, or add output-layer code scanning.

---

## Environment Setup

Need a Vision One API key with AI Security scope? Start a self-serve 30-day trial via [Trend Micro Trials](https://resources.trendmicro.com/vision-one-trial.html) or [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-u2in6sa3igl7c?sr=0-3&ref_=beagle&applicationId=AWSMPContessa). Trend Micro path: click **Claim your 30-day free trial now** and submit the form. Marketplace path: click **Try for free** and submit the form. If approved, use the activation email link to sign in (or create an account) and the 30-day trial begins.

```bash
# .env.sh
export V1_API_KEY="<Vision One API key — AI Security scope>"
export V1_REGION="sg"           # us / sg / eu / au / jp / in
export AWS_PROFILE="default"    # must have bedrock:InvokeModel in us-east-2
export TMAS_API_KEY="$V1_API_KEY"  # tmas uses a different env var name
```

```bash
pip install -r requirements.txt
# strands-agents  boto3  requests  flask
```

---

## Production Checklist

```
Pre-flight
  ☐ Vision One API key — AI Security scope provisioned
  ☐ XDR region confirmed (affects API host — see table above)
  ☐ Python 3.10+ (strands-agents hard requirement)
  ☐ Bedrock model access enabled in us-east-2 console

AI Scanner (before shipping)
  ☐ demo_app.py running before tmas scan
  ☐ TMAS_API_KEY set (separate env var from V1_API_KEY)
  ☐ config-sample.yaml endpoint matches proxy port
  ☐ Review all "Successful attacks" findings before shipping
  ☐ Run --dirty mode to see the full attack surface

AI Guard (production)
  ☐ Input guard: TMV1-Request-Type: SimpleRequestGuardrails
  ☐ Output guard: TMV1-Request-Type: OpenAIChatCompletionResponseV1
  ☐ str(agent_result) cast before JSON serialisation
  ☐ callback_handler=None on Strands Agent (prevents stdout streaming)
  ☐ Fail closed — block on any guard API error or timeout
  ☐ TMV1-Application-Name set per service (populates V1 dashboard)
  ☐ Custom PII rules added for Singapore NRIC / SingPass if applicable
```

---

## Performance

| Operation | Latency |
|---|---|
| AI Guard input check | ~150–400 ms |
| Bedrock Claude Haiku 4.5 | ~2,000–4,000 ms |
| AI Guard output check | ~150–400 ms |
| **End-to-end (allowed)** | **~2.5–5 s** |
| **End-to-end (blocked at input)** | **~200–500 ms** — Bedrock never called |

Blocking bad prompts is ~10× faster and costs nothing in Bedrock tokens.
