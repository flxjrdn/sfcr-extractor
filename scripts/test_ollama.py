from __future__ import annotations

import json
from textwrap import shorten

import requests

# Ollama defaults
OLLAMA_HOST = "http://localhost:11434"
MODEL = "mistral"  # change to "llama3.1:8b-instruct" or another pulled model

PROMPT = """You are a helpful assistant.
Answer the following question clearly and concisely.

Question: What is the capital of France?
"""


def request_ollama(
    *,
    ollama_host: str = OLLAMA_HOST,
    model: str = MODEL,
    prompt: str = PROMPT,
):
    return requests.post(
        f"{ollama_host}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            # optional settings
            "options": {"temperature": 0.2, "num_predict": 128},
            "stream": False,  # easier to parse
        },
        timeout=180,
    )


def main() -> int:
    print(f"🔍 Testing Ollama model '{MODEL}' at {OLLAMA_HOST} ...")

    try:
        resp = request_ollama()
    except requests.RequestException as exc:
        print("❌ Could not reach Ollama API:", exc)
        return 1

    if resp.status_code != 200:
        print(f"❌ Ollama returned HTTP {resp.status_code}: {resp.text[:500]}")
        return 1

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print("❌ Response was not valid JSON.")
        print(resp.text[:500])
        return 1

    # Basic inspection
    answer = data.get("response", "").strip()
    tokens = data.get("eval_count", "N/A")
    duration = data.get("total_duration", "N/A")

    print("\n✅ Ollama responded successfully!")
    print(f"Model: {MODEL}")
    print(f"Response time: {duration} ns  |  Tokens evaluated: {tokens}")
    print(f"Answer preview: {shorten(answer, width=200)}\n")

    if "paris" in answer.lower():
        print("🎉 Looks good — the model seems to respond properly.")
    else:
        print(
            "⚠️ Model responded, but the output looks unexpected. Check the text above."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
