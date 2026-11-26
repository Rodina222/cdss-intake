"""The steps: create a case, transcribe its audio, extract fields. Used by the dashboard and the scripts."""
import json
import time
import threading
import traceback
from pathlib import Path
from . import asr, config, extract as ex, store
from .schema import BY_ID
from .textutil import safe_id


def create_case(case_id, transcript="", source="text", audio_file=None):
    case_id = safe_id(case_id)
    if store.exists(case_id):
        raise ValueError(f"A case named '{case_id}' already exists.")
    return store.new_case(case_id, transcript, source, audio_file)


def set_transcript(case_id, text):
    c = store.get(case_id)
    c["transcript"] = text
    return store.save(c)


def transcribe_case(case_id):
    c = store.get(case_id)
    if not c.get("audio_file"):
        raise ValueError("This case has no audio file.")
    path = config.AUDIO_DIR / c["audio_file"]
    res = asr.transcribe(path)
    (config.TRANSCRIPT_DIR / f"{case_id}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.TRANSCRIPT_DIR / f"{case_id}.txt").write_text(res["text"], encoding="utf-8")
    c = store.get(case_id)
    c["transcript"] = res["text"]
    c["asr"] = {k: res[k] for k in ("model", "language", "duration_s", "seconds_to_transcribe")}
    return store.save(c)


def extract_case(case_id):
    c = store.get(case_id)
    transcript = (c.get("transcript") or "").strip()
    if not transcript:
        raise ValueError("This case has no transcript yet.")
    t0 = time.time()
    clean, flags, raw = ex.extract(transcript)
    took = round(time.time() - t0, 1)
    (config.CASE_DIR / f"{case_id}.llm.txt").write_text(raw or "", encoding="utf-8")
    c = store.get(case_id)
    c["fields"] = store.empty_fields()
    c["events"], c["reviewed"], c["report_seen"], c["comment"] = [], False, False, ""
    for fid, item in clean.items():
        d = c["fields"][fid]
        d.update(ai=item["value"], value=item["value"], quote=item["evidence_quote"], filled=True)
        store.event(c, "AI filled", fid, None, str(item["value"]), who="Language model")
    c["flags"] = flags
    c["extract_s"] = took
    c["model"] = {"llm": config.llm_model_name(), "backend": config.LLM_BACKEND, "prompt_version": config.PROMPT_VERSION}
    return store.save(c)


# ---- background jobs for the dashboard ----
_STEPS = {"transcribe": transcribe_case, "extract": extract_case}
_job_lock = threading.Lock()


def start_job(case_id, kind):
    if kind not in _STEPS:
        raise ValueError("unknown step")
    with _job_lock:
        c = store.get(case_id)
        if c is None:
            raise KeyError(case_id)
        if c.get("busy"):
            raise ValueError("A step is already running for this case.")
        c["busy"], c["error"] = kind, None
        store.save(c)

    def run():
        err = None
        try:
            _STEPS[kind](case_id)
        except Exception as e:                       # shown in the dashboard
            err = str(e) or e.__class__.__name__
            traceback.print_exc()
        c2 = store.get(case_id)
        c2["busy"], c2["error"] = None, err
        store.save(c2)

    threading.Thread(target=run, daemon=True).start()


# ---- edits and decisions ----
def edit_field(case_id, fid, value, who="Reviewer", kind="edited"):
    c = store.get(case_id)
    spec, d = BY_ID.get(fid), c["fields"].get(fid)
    if spec is None or d is None or not d["filled"]:
        raise ValueError("That field has no value to edit.")
    if spec["type"] == "number":
        value = float(value)
        value = int(value) if value == int(value) else value
    elif spec["type"] == "enum":
        value = str(value).lower()
        if value not in spec["options"]:
            raise ValueError("Value not allowed for this field.")
    else:
        value = str(value).strip()
        if not value:
            raise ValueError("The value cannot be empty.")
    if str(value) != str(d["value"]):
        store.event(c, kind, fid, str(d["value"]), str(value), who=who)
        d["value"] = value
        d["edited"] = str(value) != str(d["ai"])
    return store.save(c)


def decide(case_id, fid, decision, who="Doctor"):
    if decision not in ("approve", "flag"):
        raise ValueError("decision must be approve or flag")
    c = store.get(case_id)
    d = c["fields"].get(fid)
    if d is None or not d["filled"]:
        raise ValueError("That field has no value.")
    d["decision"] = decision
    store.event(c, "approved" if decision == "approve" else "flagged", fid, None, str(d["value"]), who=who)
    return store.save(c)


def run_step(case_id, kind):
    """Run one step now (blocking) while marking the case busy so other users see it. Raises on failure."""
    with _job_lock:
        c = store.get(case_id)
        if c.get("busy"):
            raise ValueError("A step is already running for this case.")
        c["busy"], c["error"] = kind, None
        store.save(c)
    err = None
    try:
        _STEPS[kind](case_id)
    except Exception as e:
        err = str(e) or e.__class__.__name__
    c = store.get(case_id)
    c["busy"], c["error"] = None, err
    store.save(c)
    if err:
        raise RuntimeError(err)


def mark_report_seen(case_id):
    c = store.get(case_id)
    c["report_seen"] = True
    return store.save(c)


def save_review(case_id, comment, kind="save", who="Doctor"):
    from . import report
    c = store.get(case_id)
    c["comment"] = comment
    if kind == "request":
        store.event(c, "more information requested", None, None, comment or "(no comment)", who=who)
    else:
        c["reviewed"] = True
        store.event(c, "review saved", None, None, comment or "(no comment)", who=who)
        (config.REPORT_DIR / f"{case_id}.md").write_text(report.report_markdown(c), encoding="utf-8")
    return store.save(c)


def save_followup_answer(case_id, fid, value, answer_text, who="Reviewer"):
    """Save an explicit patient follow-up answer separately from AI fields."""

    c = store.get(case_id)
    if c is None:
        raise ValueError("Case not found.")

    spec = BY_ID.get(fid)
    if spec is None:
        raise ValueError("Unknown field ID.")

    # Never overwrite an original AI-extracted or reviewed answer.
    field_data = c["fields"].get(fid, {})
    if field_data.get("filled", False):
        raise ValueError("This field already has an original answer.")

    # Never silently replace an earlier follow-up answer.
    if fid in c.setdefault("followup_answers", {}):
        raise ValueError("A follow-up answer already exists for this field.")

    if not isinstance(answer_text, str) or not answer_text.strip():
        raise ValueError("The patient's answer text cannot be empty.")

    field_type = spec["type"]

    if field_type == "enum":
        if value not in spec.get("options", []):
            raise ValueError("Value must be one of the allowed options.")

    elif field_type == "number":
        if isinstance(value, bool):
            raise ValueError("A valid number is required.")
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError("A valid number is required.")

    elif field_type == "text":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A non-empty text value is required.")

    else:
        raise ValueError("Unsupported field type.")

    c["followup_answers"][fid] = {
        "value": value,
        "answer_text": answer_text,
        "source": "patient_followup",
        "timestamp": store.now(),
        "who": who
    }

    store.event(
        c,
        "Follow-up answer",
        fid,
        None,
        str(value),
        who=who
    )

    return store.save(c)
