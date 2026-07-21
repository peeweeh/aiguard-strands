#!/usr/bin/env python3
import logging
import os
import sys

import boto3
import requests
from strands import Agent
from strands.models import BedrockModel

logger = logging.getLogger("aiguard-strands")

_TIMEOUT_SECONDS = 10

# =========================
# Config – EDIT THIS
# =========================

# 1) Your one-off message variable
message = "Explain the concept of machine learning in simple terms."

# Allow override via CLI: python main.py "your text here"
if len(sys.argv) > 1:
    message = " ".join(sys.argv[1:])

# 2) Trend Vision One AI Guard
V1_API_KEY = os.environ.get("V1_API_KEY")  # export V1_API_KEY=...
V1_REGION = os.environ.get("V1_REGION", "us")  # xdr region (not AWS region)

# 3) AWS / Bedrock / Strands
AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")  # your existing profile
AWS_REGION = "us-east-2"  # Bedrock region
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # Claude Haiku 4.5 in us-east-2

# Trend Vision One AI Guard endpoint from docs
# US region: api.xdr.trendmicro.com (no subdomain)
# All other regions: api.<region>.xdr.trendmicro.com
_v1_host = (
    "api.xdr.trendmicro.com"
    if V1_REGION in ("us", "", None)
    else f"api.{V1_REGION}.xdr.trendmicro.com"
)
APPLY_GUARDRAILS_URL = f"https://{_v1_host}/v3.0/aiSecurity/applyGuardrails"


def _headers(request_type: str) -> dict:
    return {
        "Authorization": f"Bearer {V1_API_KEY}",
        "Content-Type": "application/json",
        "TMV1-Application-Name": os.environ.get("V1_APP_NAME", "aiguard-strands"),
        "TMV1-Request-Type": request_type,
        "Prefer": "return=minimal",
        "Accept": "application/json",
    }


def ai_guard_check_prompt(prompt: str) -> dict:
    """
    SimpleRequestGuardrails – same pattern as Vision One example.

    Fails closed: a missing key, network error, timeout, or non-200 response
    all return a Block dict rather than raising — one bad network blip
    shouldn't crash a live demo (or a batch test run) mid-prompt.
    """
    if not V1_API_KEY:
        return {"action": "Block", "reasons": ["V1_API_KEY not set — AI Guard disabled"]}
    try:
        resp = requests.post(
            APPLY_GUARDRAILS_URL,
            headers=_headers("SimpleRequestGuardrails"),
            json={"prompt": prompt},
            timeout=_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            logger.warning("AI Guard input check HTTP %s: %s", resp.status_code, resp.text[:200])
            return {"action": "Block", "reasons": [f"AI Guard HTTP {resp.status_code} — failing closed"]}
        return resp.json()
    except requests.RequestException as e:
        logger.warning("AI Guard input check failed: %s", e)
        return {"action": "Block", "reasons": ["AI Guard unreachable — failing closed"]}


def ai_guard_check_response(openai_like: dict) -> dict:
    """
    OpenAIChatCompletionResponseV1 – pass the whole LLM response.
    Fails closed — see ai_guard_check_prompt.
    """
    if not V1_API_KEY:
        return {"action": "Block", "reasons": ["V1_API_KEY not set — AI Guard disabled"]}
    try:
        resp = requests.post(
            APPLY_GUARDRAILS_URL,
            headers=_headers("OpenAIChatCompletionResponseV1"),
            json=openai_like,
            timeout=_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            logger.warning("AI Guard output check HTTP %s: %s", resp.status_code, resp.text[:200])
            return {"action": "Block", "reasons": [f"AI Guard HTTP {resp.status_code} — failing closed"]}
        return resp.json()
    except requests.RequestException as e:
        logger.warning("AI Guard output check failed: %s", e)
        return {"action": "Block", "reasons": ["AI Guard unreachable — failing closed"]}


def build_strands_agent(system_prompt: str = None) -> Agent:
    """
    Minimal Strands Agent wired to Bedrock Claude Haiku 4.5.
    Pass system_prompt to inject a custom persona / tool context.
    """
    boto_session = boto3.Session(
        profile_name=AWS_PROFILE,
        region_name=AWS_REGION,
    )

    bedrock_model = BedrockModel(
        model_id=MODEL_ID,
        boto_session=boto_session,
    )

    agent = Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        # suppress default streaming to stdout
        callback_handler=None,
    )
    return agent


def run_one_shot(message: str) -> None:
    print(f"Message:\n{message}\n")

    # 1) Guardrails on input
    prompt_guard = ai_guard_check_prompt(message)
    if prompt_guard.get("action") == "Block":
        print("[AI Guard] Prompt blocked.")
        print("Reasons:", prompt_guard.get("reasons", []))
        return

    print("[AI Guard] Prompt allowed. Calling Strands/Bedrock...\n")

    # 2) Call Strands agent once
    agent = build_strands_agent()
    # Agent(...) returns an AgentResult; convert to plain string
    response_text = str(agent(message))

    # 3) Wrap into OpenAI-style object for AI Guard
    openai_like = {
        "id": "bedrock-" + MODEL_ID,
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

    # 4) Guardrails on output
    resp_guard = ai_guard_check_response(openai_like)
    if resp_guard.get("action") == "Block":
        print("[AI Guard] LLM response blocked.")
        print("Reasons:", resp_guard.get("reasons", []))
        return

    # 5) Safe → print answer
    print("\n[AI Guard] Response allowed.\n")
    print("AI answer:\n")
    print(response_text)


if __name__ == "__main__":
    run_one_shot(message)
