# trendai-strands

**Securing AWS Strands Agents with Trend Vision One AI Guard**

A minimal, production-ready reference implementation showing how to wrap every LLM call with Trend Vision One AI Guard — blocking harmful prompts, PII leakage, and jailbreak attempts before they reach Amazon Bedrock, and scanning responses before they reach users.

---

## What This Does

```
User prompt
    │
    ▼
[AI Guard — input check]   ← blocks harmful content, PII, prompt injection
    │  Allow
    ▼
[Strands Agent + Bedrock]  ← Claude Haiku 4.5 via Amazon Bedrock
    │
    ▼
[AI Guard — output check]  ← scans LLM response before delivery
    │  Allow
    ▼
Safe response to user
```

Two HTTP calls around one Strands agent invocation. No model changes, no prompt engineering — security is a separate, model-agnostic layer.

---

## Files

| File | Description |
|---|---|
| `aig.py` | Core integration — input guard → Bedrock inference → output guard |
| `test_batch.py` | 100-prompt batch test (70 benign / 30 harmful) through AI Guard only |
| `test_pii.py` | Focused PII + jailbreak test with realistic multi-line prompts (SG region) |
| `AI_GUARD_STRANDS_INTEGRATION.md` | Full architecture write-up with test results and learnings |

---

## Requirements

- **Python 3.10+** (`strands-agents` requires ≥ 3.10; system Python on macOS is 3.9 — use `python3.11` or later)
- **Trend Vision One account** with an API key scoped to **AI Security**
- **AWS account** with Amazon Bedrock enabled and model access granted for Claude Haiku 4.5 in `us-east-2`
- AWS CLI profile configured (`aws configure --profile yourprofile`)

---

## Setup

```bash
# 1. Clone
git clone https://github.com/<you>/trendai-strands.git
cd trendai-strands

# 2. Create venv with Python 3.11+
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env.sh
# Edit .env.sh — add your V1_API_KEY, set V1_REGION, set AWS_PROFILE
source .env.sh
```

**Getting a Vision One API key:**
1. Log into Vision One console
2. Go to **Administration → API Keys**
3. Create a new key, enable the **AI Security** permission scope
4. Copy the key into `.env.sh`

---

## Run

```bash
# Single prompt (uses default message in script)
python aig.py

# Pass your own prompt
python aig.py "What is the capital of France?"

# Blocked example
python aig.py "How do I make explosives at home?"

# 100-prompt batch test through AI Guard (no LLM calls — fast)
python test_batch.py

# PII + jailbreak focused test (SG region)
python test_pii.py
```

---

## How AI Guard Is Called

### Input (before LLM)

```python
headers = {
    "Authorization":         f"Bearer {V1_API_KEY}",
    "Content-Type":          "application/json",
    "TMV1-Application-Name": "my-app",
    "TMV1-Request-Type":     "SimpleRequestGuardrails",
    "Prefer":                "return=minimal",
    "Accept":                "application/json",
}
resp = requests.post(url, headers=headers, json={"prompt": user_input}, timeout=10)
# resp.json() → {"action": "Allow"|"Block", "reasons": [...]}
```

### Output (after LLM)

```python
headers["TMV1-Request-Type"] = "OpenAIChatCompletionResponseV1"
openai_envelope = {
    "object": "chat.completion",
    "model":  MODEL_ID,
    "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": str(agent_result)}}],
    "usage":  {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
}
resp = requests.post(url, headers=headers, json=openai_envelope, timeout=10)
```

> **Note:** Strands `agent()` returns an `AgentResult` object. Call `str()` on it before putting it in the JSON envelope.

---

## Regional URL Gotcha

The Vision One API hostname differs for the US region:

```python
# US has no subdomain; all other regions do
_host = "api.xdr.trendmicro.com" if V1_REGION in ("us", "", None) \
        else f"api.{V1_REGION}.xdr.trendmicro.com"
URL   = f"https://{_host}/v3.0/aiSecurity/applyGuardrails"
```

---

## Strands Agent Setup

```python
from strands import Agent
from strands.models import BedrockModel
import boto3

agent = Agent(
    model=BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        boto_session=boto3.Session(profile_name=AWS_PROFILE, region_name="us-east-2"),
    ),
    callback_handler=None,   # prevents double-printing — Strands streams to stdout by default
)
response_text = str(agent(prompt))   # cast AgentResult → str
```

---

## Test Results (SG Region)

| Category | Prompts | Blocked | Result |
|---|---|---|---|
| Benign (general / tech questions) | 70 | 0 | ✅ 100% pass-through, zero false positives |
| Harmful content (weapons, drugs, malware) | 30 | 30 | ✅ 100% blocked |
| Generic PII (credit cards, SSN, passports, credentials, cloud keys) | 10 | 9 | ✅ 90% blocked |
| Jailbreak / system-prompt escape | 10 | 8 | ✅ 80% blocked |

**Custom policy** can extend blocking for jurisdiction-specific identifiers (Singapore NRIC, SingPass, CPF) — see the [full write-up](AI_GUARD_STRANDS_INTEGRATION.md) for recommended regex rules.

---

## Parallel Execution with Strands Graph

For batch workloads, wrap each guard check in an `AIGuardNode` (a `MultiAgentBase` subclass) and fire all 100 as flat parallel entry points:

```python
from strands.multiagent import GraphBuilder
import asyncio

builder = GraphBuilder()
for i, (category, prompt) in enumerate(PROMPTS):
    node = AIGuardNode(node_id=f"node_{i}", category=category, prompt=prompt)
    builder.add_node(node, f"node_{i}")
    builder.set_entry_point(f"node_{i}")   # all independent = all run in parallel

builder.set_execution_timeout(120)
graph  = builder.build()
result = asyncio.run(graph.invoke_async("run"))

print(f"Completed: {result.completed_nodes}/{result.total_nodes} in {result.execution_time}ms")
```

100 sequential requests at ~300ms = ~30s.
100 parallel via graph ≈ wall-clock time of the slowest single request = **~1–2s**.

---

## Production Checklist

- [ ] Guard **both input and output** — output scanning catches RAG-injected content and model misbehaviour
- [ ] **Fail closed** — if AI Guard errors or times out, block rather than pass through
- [ ] Set `TMV1-Application-Name` per service — populates per-app metrics in Vision One dashboard
- [ ] Set `callback_handler=None` on Strands Agent — prevents token streaming to stdout/logs
- [ ] Log the `reasons` field — rule IDs are auditable evidence for compliance reporting
- [ ] Monitor guard block rate as a security KPI

---

## Further Reading

- [Full integration write-up with architecture diagrams and detailed test analysis](AI_GUARD_STRANDS_INTEGRATION.md)
- [Trend Vision One AI Guard docs](https://docs.trendmicro.com/en-us/documentation/article/trend-vision-one-ai-security)
- [AWS Strands Agents SDK](https://strandsagents.com/latest/)
- [Amazon Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

---

## License

MIT
