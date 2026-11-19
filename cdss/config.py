"""Settings. Values come from environment variables or a .env file in the project folder."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #")[0]
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def env(key, default=""):
    return os.environ.get(key, default)


DATA_DIR = Path(env("DATA_DIR", str(ROOT / "data")))
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
GOLD_DIR = DATA_DIR / "gold"
CASE_DIR = DATA_DIR / "cases"
REPORT_DIR = DATA_DIR / "reports"
LLM_WORK_DIR = DATA_DIR / "_llm_workdir"   # empty folder the OpenCode agent runs in, so it never sees project files
SCHEMA_PATH = Path(env("SCHEMA_PATH", str(ROOT / "schema.json")))
SAMPLES_DIR = ROOT / "samples"

for _d in (AUDIO_DIR, TRANSCRIPT_DIR, GOLD_DIR, CASE_DIR, REPORT_DIR, LLM_WORK_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# speech to text (faster-whisper, runs on this computer)
WHISPER_MODEL = env("WHISPER_MODEL", "small")        # small for CPU; large-v3 needs a GPU or a lot of patience
WHISPER_DEVICE = env("WHISPER_DEVICE", "auto")       # auto, cpu or cuda
WHISPER_COMPUTE = env("WHISPER_COMPUTE", "int8")     # int8 on CPU, float16 on GPU
WHISPER_LANGUAGE = env("WHISPER_LANGUAGE", "ar")

# language model backend: "opencode" or "openai" (any OpenAI-compatible server, for example Ollama with Qwen)
LLM_BACKEND = env("LLM_BACKEND", "opencode")
OPENCODE_CMD = env("OPENCODE_CMD", "opencode run -m {model} {prompt}")
OPENCODE_MODEL = env("OPENCODE_MODEL", "opencode/glm-5.3-flash-free")
LLM_TIMEOUT = int(env("LLM_TIMEOUT", "240"))
OPENAI_BASE_URL = env("OPENAI_BASE_URL", "http://localhost:11434/v1")
OPENAI_MODEL = env("OPENAI_MODEL", "qwen2.5:7b-instruct")
OPENAI_API_KEY = env("OPENAI_API_KEY", "ollama")

PROMPT_VERSION = env("PROMPT_VERSION", "v1")
HOST = env("HOST", "127.0.0.1")
PORT = int(env("PORT", "8000"))


def llm_model_name():
    return OPENCODE_MODEL if LLM_BACKEND == "opencode" else OPENAI_MODEL
