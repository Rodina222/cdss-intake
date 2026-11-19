"""Cases are stored as one JSON file each in data/cases/. All reads and writes go through here."""
import json
import threading
from datetime import datetime, timezone
from . import config
from .schema import SCHEMA

_lock = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(case_id):
    return config.CASE_DIR / f"{case_id}.json"


def empty_fields():
    return {f["id"]: {"ai": None, "quote": "", "value": None, "decision": "", "edited": False, "filled": False}
            for f in SCHEMA}


def exists(case_id):
    return _path(case_id).exists()


def get(case_id):
    with _lock:
        p = _path(case_id)
        if not p.exists():
            return None
        c = json.loads(p.read_text(encoding="utf-8"))
    for f in SCHEMA:                      # a schema that grew since the case was made
        c["fields"].setdefault(f["id"], {"ai": None, "quote": "", "value": None, "decision": "", "edited": False, "filled": False})
    return c


def save(case):
    with _lock:
        case["updated"] = now()
        tmp = _path(case["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_path(case["id"]))
    return case


def new_case(case_id, transcript="", source="text", audio_file=None):
    c = {"id": case_id, "created": now(), "updated": now(), "source": source, "audio_file": audio_file,
         "transcript": transcript, "asr": None, "busy": None, "error": None,
         "model": None, "fields": empty_fields(), "flags": [], "events": [],
         "comment": "", "reviewed": False, "report_seen": False}
    return save(c)


def delete(case_id):
    with _lock:
        for p in config.CASE_DIR.glob(f"{case_id}.*"):
            p.unlink()


def event(case, kind, field=None, frm=None, to=None, who="Reviewer"):
    case["events"].append({"t": now(), "kind": kind, "field": field, "from": frm, "to": to, "who": who})


def list_cases():
    out = []
    for p in sorted(config.CASE_DIR.glob("*.json")):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        f = c.get("fields", {})
        site = f.get("site", {}).get("value")
        side = f.get("side", {}).get("value")
        concern = " ".join(x for x in [str(side) if side else "", str(site).replace("_", " ") if site else ""] if x) or None
        out.append({"id": c["id"], "concern": concern, "source": c.get("source"), "busy": c.get("busy"),
                    "error": c.get("error"), "has_transcript": bool(c.get("transcript")),
                    "extracted": any(v.get("filled") for v in f.values()) or bool(c.get("model")),
                    "reviewed": c.get("reviewed", False), "report_seen": c.get("report_seen", False),
                    "updated": c.get("updated")})
    out.sort(key=lambda x: x["updated"] or "", reverse=True)
    return out


def clear_stale_busy():
    for p in config.CASE_DIR.glob("*.json"):
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("busy"):
            c["busy"] = None
            c["error"] = "The server restarted while this step was running. Run it again."
            p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
