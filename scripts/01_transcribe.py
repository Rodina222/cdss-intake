"""Transcribe every audio file in data/audio with Whisper (on this computer).

Writes data/transcripts/<name>.json and .txt and makes a dashboard case named after the file
(d01.m4a becomes case d01, which also picks up data/gold/d01.json for scoring).
Usage: python scripts/01_transcribe.py [--redo] [files...]
"""
import _path  # noqa: F401
import argparse
from pathlib import Path
from cdss import config, pipeline, store
from cdss.textutil import safe_id

EXT = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".webm", ".mp4"}

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="*", help="audio files; default is everything in data/audio")
ap.add_argument("--redo", action="store_true", help="transcribe again even if a transcript exists")
a = ap.parse_args()

if a.files:
    files = []
    for f in a.files:
        p = Path(f)
        dest = config.AUDIO_DIR / p.name
        if p.resolve() != dest.resolve():
            dest.write_bytes(p.read_bytes())
        files.append(dest)
else:
    files = sorted(p for p in config.AUDIO_DIR.iterdir() if p.suffix.lower() in EXT)
if not files:
    raise SystemExit(f"No audio found. Put recordings in {config.AUDIO_DIR}")

print(f"Whisper model: {config.WHISPER_MODEL} ({config.WHISPER_DEVICE}, {config.WHISPER_COMPUTE})")
for p in files:
    cid = safe_id(p.stem)
    if not store.exists(cid):
        pipeline.create_case(cid, "", "audio", p.name)
    c = store.get(cid)
    if c["transcript"] and not a.redo:
        print(f"{p.name}: already transcribed (use --redo to repeat)")
        continue
    c = pipeline.transcribe_case(cid)
    print(f"{p.name}: {c['asr']['duration_s']} s audio, {c['asr']['seconds_to_transcribe']} s to transcribe")
    print("   ", c["transcript"][:200])
