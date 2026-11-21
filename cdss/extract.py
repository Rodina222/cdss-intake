"""Ask the model, then check every answer against the transcript."""
import json
import re
from .schema import BY_ID, SCHEMA, SYSTEM_PROMPT, build_user_prompt
from .textutil import normalize_arabic
from . import llm


def parse_json(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, flags=re.S)
    return json.loads(m.group(0) if m else raw)


_YES = {"نعم", "ايوه", "أيوه", "آه", "اه", "أيوة", "ايوة", "true", "y"}
_NO = {"لا", "لأ", "لاء", "false", "n"}


def _enum_alias(val, options):
    """Accept Arabic yes/no and an unambiguous part of an option name (foot -> ankle_foot). Never guesses between two options."""
    if val in options:
        return val
    if "yes" in options and "no" in options:
        if val in _YES:
            return "yes"
        if val in _NO:
            return "no"
    hits = [o for o in options if val and (val in o.split("_") or o.replace("_", " ") == val.replace("_", " "))]
    return hits[0] if len(hits) == 1 else val



def validate(parsed, transcript):
    """Return (clean, flags). clean = {field_id: {value, evidence_quote}}; flags list what was discarded and why."""
    t_norm = normalize_arabic(transcript)
    clean, flags = {}, []
    for fid, item in (parsed.get("fields") or {}).items():
        spec = BY_ID.get(fid)
        if spec is None:
            flags.append({"field": fid, "issue": "unknown_field"}); continue
        if not isinstance(item, dict) or "value" not in item:
            flags.append({"field": fid, "issue": "bad_shape"}); continue
        val, quote = item["value"], str(item.get("evidence_quote", "")).strip()
        if spec["type"] == "enum":
            val = _enum_alias(str(val).strip().lower(), spec["options"])
            if val not in spec["options"]:
                flags.append({"field": fid, "issue": "value_not_allowed", "value": val}); continue
        elif spec["type"] == "number":
            try:
                val = float(val)
                val = int(val) if val == int(val) else val
            except (TypeError, ValueError):
                flags.append({"field": fid, "issue": "not_a_number", "value": str(val)}); continue
        else:
            val = str(val).strip()
            if not val:
                flags.append({"field": fid, "issue": "empty_value"}); continue
        if not quote:
            flags.append({"field": fid, "issue": "no_evidence_quote"}); continue
        if normalize_arabic(quote) not in t_norm:
            flags.append({"field": fid, "issue": "quote_not_in_transcript", "quote": quote}); continue
        clean[fid] = {"value": val, "evidence_quote": quote}
    return clean, flags


CHUNK = 14  # fields per model call: small models lose fields on long lists
REGION_FOR_SITE = {"neck": ["neck"], "shoulder": ["shoulder"], "elbow": ["elbow"], "wrist_hand": ["wrist_hand"],
                   "back": ["back"], "hip": ["hip", "back"], "knee": ["knee"], "ankle_foot": ["ankle_foot"]}


def _fields(module):
    return [f for f in SCHEMA if f["module"] == module]


def _split(fields):
    return [fields[i:i + CHUNK] for i in range(0, len(fields), CHUNK)]


def _run_chunk(transcript, fields):
    """One model call for a part of the form. Returns (clean, flags, raw)."""
    user = build_user_prompt(transcript, fields)
    raw = llm.call_llm(SYSTEM_PROMPT, user)
    try:
        parsed = parse_json(raw)
    except Exception:
        raw = llm.call_llm(SYSTEM_PROMPT, user + "\n\nYour last reply was not valid JSON. Reply with only the JSON object.")
        try:
            parsed = parse_json(raw)
        except Exception as e:
            return {}, [{"field": "*", "issue": f"unparseable_json: {e}"}], raw
    allowed = {f["id"] for f in fields}
    parsed = {"fields": {k: v for k, v in (parsed.get("fields") or {}).items() if k in allowed}}
    clean, flags = validate(parsed, transcript)
    return clean, flags, raw


def extract(transcript):
    """Fill the form in parts: site, core, red flags, then the injury and region modules the patient's answers call for.
    Return (clean, flags, raw_text)."""
    clean, flags, raws = {}, [], []

    calls = {"n": 0, "failed": 0, "last": None}

    def go(fields):
        calls["n"] += 1
        try:
            c, f, r = _run_chunk(transcript, fields)
        except llm.LLMError as e:  # one slow or failed call must not lose the whole case
            calls["failed"] += 1; calls["last"] = e
            flags.append({"field": fields[0]["module"], "issue": f"model_error: {e}"})
            return
        clean.update(c); flags.extend(f); raws.append(r)

    go(_fields("site"))
    for part in _split(_fields("core")):
        go(part)
    go(_fields("red_flags"))
    if clean.get("injury", {}).get("value") == "yes":
        go(_fields("trauma"))
    mods = list(REGION_FOR_SITE.get(clean.get("site", {}).get("value"), []))
    if clean.get("also_neck_back", {}).get("value") == "yes" and "back" not in mods:
        mods.append("back")
    for m in mods:
        for part in _split(_fields(m)):
            go(part)
    if calls["failed"] == calls["n"]:
        raise calls["last"]
    return clean, flags, "\n---\n".join(raws)
