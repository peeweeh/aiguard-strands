#!/usr/bin/env python3
import os
import json
import sys
import requests
import boto3

from strands import Agent
from strands.models import BedrockModel

# =========================
# Config – EDIT THIS
# =========================

# 1) Your one-off message variable
message = "Explain the concept of machine learning in simple terms."

# Allow override via CLI: python main.py "your text here"
if len(sys.argv) > 1:
    message = " ".join(sys.argv[1:])

# 2) Trend Vision One AI Guard
V1_API_KEY = os.environ.get("V1_API_KEY")       # export V1_API_KEY=...
V1_REGION = os.environ.get("V1_REGION", "us-east-1")  # xdr region (not AWS region)

# 3) AWS / Bedrock / Strands
AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")  # your existing profile
AWS_REGION = "us-east-2"  # Bedrock region
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # Haiku 4.5 in us-east-2

# Trend Vision One AI Guard endpoint from docs
# US region uses api.xdr.trendmicro.com (no subdomain); others use api.<region>.xdr.trendmicro.com
_v1_host = "api.xdr.trendmicro.com" if V1_REGION in ("us", "", None) else f"api.{V1_REGION}.xdr.trendmicro.com"
APPLY_GUARDRAILS_URL = f"https://{_v1_host}/v3.0/aiSecurity/applyGuardrails"


def ai_guard_check_prompt(prompt: str) -> dict:
    """
    SimpleRequestGuardrails – same pattern as Vision One example.
    """
    if not V1_API_KEY:
        raise ValueError("Missing V1_API_KEY environment variable")

    headers = {
        "Authorization": f"Bearer {V1_API_KEY}",
        "Content-Type": "application/json",
        "TMV1-Application-Name": "trendai-strands-oneoff",
        "TMV1-Request-Type": "SimpleRequestGuardrails",
        "Prefer": "return=minimal",
        "Accept": "application/json",
    }
    payload = {"prompt": prompt}

    resp = requests.post(
        APPLY_GUARDRAILS_URL,
        headers=headers,
        json=payload,
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"AI Guard error on prompt: {resp.status_code} {resp.text}"
        )

    return resp.json()


def ai_guard_check_response(openai_like: dict) -> dict:
    """
    OpenAIChatCompletionResponseV1 – pass the whole LLM response,
    per Vision One example. [web:11]
    """
    headers = {
        "Authorization": f"Bearer {V1_API_KEY}",
        "Content-Type": "application/json",
        "TMV1-Application-Name": "trendai-strands-oneoff",
        "TMV1-Request-Type": "OpenAIChatCompletionResponseV1",
        "Prefer": "return=minimal",
        "Accept": "application/json",
    }

    resp = requests.post(
        APPLY_GUARDRAILS_URL,
        headers=headers,
        json=openai_like,
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"AI Guard error on response: {resp.status_code} {resp.text}"
        )

    return resp.json()


def build_strands_agent() -> Agent:
    """
    Minimal Strands Agent wired to Bedrock Claude 4.5 Haiku. [web:31][web:32]
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
