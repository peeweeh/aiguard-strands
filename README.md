<div align="center">

# 🛡️ aiguard-strands

**Secure your Bedrock LLM in under a day**

*AI Scanner + AI Guard · AWS Strands Agents · Amazon Bedrock · Trend Vision One*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/bedrock/)
[![Strands](https://img.shields.io/badge/Strands-Agents-232F3E?logo=amazonaws&logoColor=white)](https://github.com/strands-agents/sdk-python)
[![Trend Vision One](https://img.shields.io/badge/Trend-Vision%20One-D71920?logo=trendmicro&logoColor=white)](https://www.trendmicro.com/en_us/business/products/one-platform.html)
[![TMAS](https://img.shields.io/badge/TMAS-v2.203-D71920?logo=trendmicro&logoColor=white)](https://docs.trendmicro.com/en-us/documentation/article/trend-micro-cloud-one-container-security-tmas-about)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## ⚡ TL;DR

| Step | What | How |
|:---:|---|---|
| 1️⃣ | **Scan** — attack your own LLM before you ship | `python demo_app.py --dirty` → `tmas aiscan llm --config scanner/config-sample.yaml` |
| 2️⃣ | **Guard** — block threats in production | Two HTTP calls in `aig.py` wrapping every prompt in and every response out |
| 3️⃣ | **Demo** — see it live | `python demo.py` — pick a category, watch Allow/Block in real time |

> **Prerequisites:** Vision One API key (self-serve 30-day trial via [Trend Micro Trials](https://www.trendmicro.com/en_gb/business/products/trials.html?utm_source=aws+summit+london&utm_medium=referral&utm_campaign=ent_aws_dg_e_uk_int_aws+summit+london+_2026) or [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-u2in6sa3igl7c?sr=0-3&ref_=beagle&applicationId=AWSMPContessa)) · AWS Bedrock access (`us-east-2`) · Python 3.10+
> **Quick trial steps:** Trend Micro site -> click **Claim your 30-day free trial now** and submit the form. AWS Marketplace -> click **Try for free** and submit the form. If approved, use the activation email link to sign in (or create an account) and your 30-day trial starts.

---

## 📁 What's in This Repo

| File | What it does |
|---|---|
| [`aig.py`](aig.py) | **The library.** Core AI Guard helpers — input + output guardrails. Everything else imports from here; never re-implement the HTTP call elsewhere. |
| [`demo_app.py`](demo_app.py) | ⚠️ Deliberately vulnerable. Simulated enterprise AI app (FinSight) — Flask + Bedrock with an exploitable system prompt; TMAS scan target only, not a usage example |
| [`demo.py`](demo.py) | Interactive CLI: pick a category, watch the full pipeline in real time |
| [`evals/batch_eval.py`](evals/batch_eval.py) | Live eval, not a unit test — 100 prompts (70% benign / 30% malicious) through the full pipeline. Makes real, billed API calls. |
| [`evals/pii_eval.py`](evals/pii_eval.py) | Live eval, not a unit test — 40-prompt PII + jailbreak corpus (SG region). Makes real, billed API calls. |
| [`scanner/config-sample.yaml`](scanner/config-sample.yaml) | Ready-to-use TMAS AI Scanner config for this stack |

---

## 🚀 Quick Start

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

## 🔍 Part 1 — AI Scanner

> Attack your own LLM before attackers do. TMAS fires **59 automated probes** — every OWASP LLM Top 10 category — and shows you exactly what slipped through.

[![AI Scanner results](images/scanner.png)](docs/ai-scanner.md)

📖 **[Full guide: install TMAS, run the scan, read the results →](docs/ai-scanner.md)**

---

## 🔒 Part 2 — AI Guard

> Two HTTP calls. Every prompt in, every response out — inspected before it reaches the model or the user.

[![AI Guard pipeline](images/aiguard.png)](docs/ai-guard.md)

📖 **[Full guide: architecture, code, test results, performance →](docs/ai-guard.md)**

---

## 📊 Results at a Glance

<div align="center">

| | AI Scanner | AI Guard |
|:---:|:---:|:---:|
| **Attacks fired** | 59 / 59 | — |
| **Harmful content blocked** | — | ⚠️ 96.7% (29/30) |
| **PII detected** | — | ✅ 90.0% (18/20) |
| **Jailbreaks stopped** | — | ✅ 90.0% (9/10) |
| **False positives** | — | ⚠️ 2.5% (2/80) |
| **Blocked prompt latency** | — | ⚡ p50 147ms · p90 181ms · max 235ms |

</div>

> AI Guard numbers above are a live re-run against the exact corpora in
> `evals/batch_eval.py` (100 prompts) + `evals/pii_eval.py` (40 prompts),
> input-guard only — not the full Bedrock round trip. Verified 2026-07-21.
> The two false positives were both benign: *"Tell me a short joke."*
> (blocked for "Harassment") and *"Explain asymmetric encryption."*
> (blocked as "Prompt attack detected"). Re-run either eval script yourself
> to reproduce or refresh these numbers — detection thresholds on the
> Vision One side can shift over time.

---

<div align="center">

*AWS Strands Agents SDK · Amazon Bedrock Claude Haiku 4.5 · Trend Vision One AI Guard · TMAS v2.203.0*

</div>

