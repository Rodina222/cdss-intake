"""Ask the model, then check every answer against the transcript."""
import json
import re
from .schema import BY_ID, SYSTEM_PROMPT, build_user_prompt
from .textutil import normalize_arabic
from . import llm


def parse_json(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, flags=re.S)
    return json.loads(m.group(0) if m else raw)


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
            val = str(val).lower()
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


def extract(transcript):
    """Return (clean, flags, raw_text). Retries once if the reply is not JSON."""
    user = build_user_prompt(transcript)
    raw = llm.call_llm(SYSTEM_PROMPT, user)
    try:
        parsed = parse_json(raw)
    except Exception:
        raw = llm.call_llm(SYSTEM_PROMPT, user + "\n\nYour last reply was not valid JSON. Reply with only the JSON object.")
        try:
            parsed = parse_json(raw)
        except Exception as e:
            return {}, [{"field": "*", "issue": f"unparseable_json: {e}"}], raw
    clean, flags = validate(parsed, transcript)
    return clean, flags, raw
