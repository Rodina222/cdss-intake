"""Check that the language model backend answers. Run this before the first extraction."""
import _path  # noqa: F401
from cdss import config, llm

print(f"Backend: {config.LLM_BACKEND}   Model: {config.llm_model_name()}")
if config.LLM_BACKEND == "opencode":
    print("Command template:", config.OPENCODE_CMD)
try:
    out = llm.call_llm("Reply with exactly this JSON and nothing else.", '{"ok": true}')
except Exception as e:
    raise SystemExit(f"FAILED: {e}")
print("Raw reply:\n", out)
