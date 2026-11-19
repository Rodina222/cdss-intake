"""Speech to text with faster-whisper, on this computer."""
import threading
import time
from pathlib import Path
from . import config

_model = None
_lock = threading.Lock()


def _load():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper is not installed. Run: pip install -r requirements.txt")
        _model = WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE)
    return _model


def transcribe(path):
    """Return {file, model, language, duration_s, seconds_to_transcribe, text, segments}."""
    with _lock:
        model = _load()
        start = time.time()
        segs, info = model.transcribe(str(path), language=config.WHISPER_LANGUAGE, beam_size=5, vad_filter=True)
        segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
        return {
            "file": Path(path).name,
            "model": config.WHISPER_MODEL,
            "language": config.WHISPER_LANGUAGE,
            "duration_s": round(info.duration, 1),
            "seconds_to_transcribe": round(time.time() - start, 1),
            "text": " ".join(s["text"] for s in segments).strip(),
            "segments": segments,
        }
