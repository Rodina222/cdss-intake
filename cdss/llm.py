"""Language model backends. One function: call_llm(system, user) -> text."""
import re
import shlex
import subprocess
import requests
from . import config

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class LLMError(RuntimeError):
    pass


def _opencode(system, user):
    prompt = system + "\n\n" + user
    parts = shlex.split(config.OPENCODE_CMD, posix=True)
    cmd = [p.replace("{model}", config.OPENCODE_MODEL).replace("{prompt}", prompt) for p in parts]
    try:
        r = subprocess.run(cmd, cwd=str(config.LLM_WORK_DIR), capture_output=True, text=True,
                           encoding="utf-8", timeout=config.LLM_TIMEOUT)
    except FileNotFoundError:
        raise LLMError(f"Could not start '{cmd[0]}'. Install OpenCode and make sure the command is on your PATH, "
                       "or set OPENCODE_CMD in .env.")
    except subprocess.TimeoutExpired:
        raise LLMError(f"OpenCode did not answer within {config.LLM_TIMEOUT} seconds.")
    out = _ANSI.sub("", r.stdout or "").strip()
    if r.returncode != 0 and not out:
        raise LLMError("OpenCode failed: " + _ANSI.sub("", (r.stderr or "")).strip()[:400])
    return out


_THINK = re.compile(r"<think>.*?</think>", re.S)


def _ollama_native(system, user):
    """Ollama's own chat API. Used for Qwen3 because it accepts think:false (no slow reasoning), which the OpenAI-style endpoint may ignore."""
    base = config.OPENAI_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    body = {"model": config.OPENAI_MODEL, "stream": False, "think": False, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        r = requests.post(base + "/api/chat", json=body, timeout=config.LLM_TIMEOUT)
    except requests.ConnectionError:
        raise LLMError(f"Could not connect to {base}. Is Ollama running?")
    except requests.Timeout:
        raise LLMError(f"The model server did not answer within {config.LLM_TIMEOUT} seconds.")
    if r.status_code != 200:
        raise LLMError(f"Model server returned {r.status_code}: {r.text[:300]}")
    return _THINK.sub("", (r.json().get("message") or {}).get("content") or "").strip()


def _openai(system, user):
    if config.OPENAI_MODEL.lower().startswith("qwen3") and config.OPENAI_BASE_URL.rstrip("/").endswith(("/v1", ":11434")):
        return _ollama_native(system, user)
    if config.OPENAI_MODEL.lower().startswith("qwen3"):
        user = user + "\n/no_think"  # Qwen3 soft switch: answer directly, no long reasoning (faster, no timeouts)
    url = config.OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
    body = {"model": config.OPENAI_MODEL, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if config.OPENAI_MODEL.lower().startswith(("qwen3", "gpt-oss")):
        body["reasoning_effort"] = "none" if config.OPENAI_MODEL.lower().startswith("qwen3") else "low"
    try:
        r = requests.post(url, json=body, timeout=config.LLM_TIMEOUT,
                          headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"})
    except requests.ConnectionError:
        raise LLMError(f"Could not connect to {config.OPENAI_BASE_URL}. Is Ollama (or your server) running?")
    except requests.Timeout:
        raise LLMError(f"The model server did not answer within {config.LLM_TIMEOUT} seconds.")
    if r.status_code != 200:
        raise LLMError(f"Model server returned {r.status_code}: {r.text[:300]}")
    return _THINK.sub("", r.json()["choices"][0]["message"]["content"] or "").strip()


def call_llm(system, user):
    if config.LLM_BACKEND == "opencode":
        return _opencode(system, user)
    if config.LLM_BACKEND == "openai":
        return _openai(system, user)
    raise LLMError("LLM_BACKEND must be 'opencode' or 'openai'")
