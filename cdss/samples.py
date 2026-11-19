"""Helpers to add sample dialogues and to import files that scripts or you placed in the data folders."""
import json
import shutil
from . import config, pipeline, store
from .textutil import safe_id

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".webm", ".mp4"}


def seed_samples():
    """Copy the sample answer keys to data/gold (as d01.json and sample-d01.json) and add typed sample cases."""
    made = []
    for g in (config.SAMPLES_DIR / "gold").glob("*.json"):
        shutil.copy(g, config.GOLD_DIR / g.name)
        shutil.copy(g, config.GOLD_DIR / f"sample-{g.name}")
    for t in sorted((config.SAMPLES_DIR / "transcripts").glob("*.txt")):
        cid = f"sample-{t.stem}"
        if not store.exists(cid):
            pipeline.create_case(cid, t.read_text(encoding="utf-8"), "sample")
            made.append(cid)
    return made


def import_folders():
    """Create cases from files in data/audio and data/transcripts that have no case yet."""
    made = []
    for p in sorted(config.AUDIO_DIR.iterdir()):
        cid = safe_id(p.stem)
        if p.suffix.lower() in AUDIO_EXT and not store.exists(cid):
            c = pipeline.create_case(cid, "", "audio", p.name)
            tj, tt = config.TRANSCRIPT_DIR / f"{cid}.json", config.TRANSCRIPT_DIR / f"{cid}.txt"
            if tj.exists():
                c["transcript"] = json.loads(tj.read_text(encoding="utf-8")).get("text", "")
            elif tt.exists():
                c["transcript"] = tt.read_text(encoding="utf-8")
            store.save(c)
            made.append(cid)
    for p in sorted(config.TRANSCRIPT_DIR.iterdir()):
        cid = safe_id(p.stem)
        if p.suffix in (".json", ".txt") and not store.exists(cid):
            text = json.loads(p.read_text(encoding="utf-8")).get("text", "") if p.suffix == ".json" else p.read_text(encoding="utf-8")
            pipeline.create_case(cid, text, "text")
            made.append(cid)
    return made
