"""Compare what the model filled with the hand-filled answers in data/gold/<case id>.json."""
import json
from . import config, store
from .schema import SCHEMA, BY_ID
from .textutil import normalize_arabic


def _same(spec, a, b):
    if spec["type"] == "number":
        try:
            return float(a) == float(b)
        except (TypeError, ValueError):
            return False
    if spec["type"] == "enum":
        return str(a).lower() == str(b).lower()
    na, nb = normalize_arabic(a), normalize_arabic(b)
    return bool(na) and bool(nb) and (na in nb or nb in na)


def load_gold(case_id):
    p = config.GOLD_DIR / f"{case_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def score_case(case, gold):
    """Rows for every field either side filled. Uses the model's own value (the AI value), not the doctor's edit."""
    rows = []
    for f in SCHEMA:
        d = case["fields"][f["id"]]
        has_pred, has_gold = d["filled"], f["id"] in gold
        if has_gold and has_pred:
            status = "correct" if _same(f, d["ai"], gold[f["id"]]) else "wrong value"
        elif has_gold:
            status = "missed"
        elif has_pred:
            status = "invented"
        else:
            continue
        rows.append({"case": case["id"], "field": f["id"], "module": f["module"], "red_flag": f["red_flag"],
                     "gold": gold.get(f["id"]), "model": d["ai"] if has_pred else None, "status": status})
    return rows


def _edit_distance(a, b):
    """Levenshtein distance between two sequences (words or characters)."""
    try:
        from rapidfuzz.distance import Levenshtein
        return Levenshtein.distance(a, b)
    except ImportError:
        pass
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def error_rates(reference, hypothesis):
    """(word error rate, character error rate) of a hypothesis against a reference text, after Arabic normalisation."""
    r, h = normalize_arabic(reference), normalize_arabic(hypothesis)
    rw, hw = r.split(), h.split()
    wer = _edit_distance(rw, hw) / len(rw) if rw else None
    cer = _edit_distance(r, h) / len(r) if r else None
    return wer, cer


def reference_text(case_id):
    """The scripted transcript for a recorded case (d17 uses samples/transcripts/d17.txt), or None."""
    p = config.SAMPLES_DIR / "transcripts" / f"{case_id}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else None


def evaluate_asr():
    """Word and character error rate of every transcribed (audio) case that has a scripted reference."""
    rows = []
    for s in store.list_cases():
        c = store.get(s["id"])
        if not c.get("asr") or not c.get("transcript"):
            continue
        ref = reference_text(c["id"])
        if ref is None:
            continue
        wer, cer = error_rates(ref, c["transcript"])
        rows.append({"case": c["id"], "wer": None if wer is None else round(wer, 3), "cer": None if cer is None else round(cer, 3),
                     "audio_s": c["asr"].get("duration_s"), "transcribe_s": c["asr"].get("seconds_to_transcribe")})
    ok = [r for r in rows if r["wer"] is not None]
    return {"rows": rows, "mean_wer": round(sum(r["wer"] for r in ok) / len(ok), 3) if ok else None,
            "mean_cer": round(sum(r["cer"] for r in ok) / len(ok), 3) if ok else None}


def _rate(n, d):
    return round(n / d, 3) if d else None


def _prf(rows):
    k = {s: sum(1 for r in rows if r["status"] == s) for s in ("correct", "wrong value", "missed", "invented")}
    precision = _rate(k["correct"], k["correct"] + k["wrong value"] + k["invented"])
    recall = _rate(k["correct"], k["correct"] + k["wrong value"] + k["missed"])
    f1 = round(2 * precision * recall / (precision + recall), 3) if precision and recall else None
    return k, precision, recall, f1


def evaluate():
    rows, cases_scored, no_gold, cases = [], [], [], []
    for s in store.list_cases():
        if not s["extracted"]:
            continue
        gold = load_gold(s["id"])
        if gold is None:
            no_gold.append(s["id"])
            continue
        c = store.get(s["id"])
        rows += score_case(c, gold)
        cases_scored.append(s["id"])
        cases.append(c)
    counts, precision, recall, f1 = _prf(rows)
    answered = counts["correct"] + counts["wrong value"] + counts["missed"]
    rf_yes = [r for r in rows if r["red_flag"] and r["gold"] == "yes"]
    caught = sum(1 for r in rf_yes if r["status"] == "correct")
    modules = []
    for m in dict.fromkeys(f["module"] for f in SCHEMA):
        k, p_, r_, f_ = _prf([r for r in rows if r["module"] == m])
        if sum(k.values()):
            modules.append({"module": m, **{"correct": k["correct"], "wrong": k["wrong value"], "missed": k["missed"], "invented": k["invented"]},
                            "precision": p_, "recall": r_, "f1": f_})
    per_case = []
    for cid in cases_scored:
        k, p_, r_, f_ = _prf([r for r in rows if r["case"] == cid])
        per_case.append({"case": cid, "correct": k["correct"], "wrong": k["wrong value"], "missed": k["missed"], "invented": k["invented"],
                         "precision": p_, "recall": r_, "f1": f_})
    # what the checks threw away, and what the doctor did with what was kept
    reasons, filled = {}, 0
    ap = ed = fg = 0
    for c in cases:
        for fl in c.get("flags", []):
            key = str(fl.get("issue", "")).split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
        fl_ = [d for d in c["fields"].values() if d["filled"]]
        filled += len(fl_)
        ap += sum(1 for d in fl_ if d["decision"] == "approve")
        ed += sum(1 for d in fl_ if d["edited"])
        fg += sum(1 for d in fl_ if d["decision"] == "flag")
    discarded = sum(reasons.values())
    ex_t = [c["extract_s"] for c in cases if c.get("extract_s") is not None]
    summary = {
        "cases_scored": cases_scored, "cases_without_gold": no_gold, "counts": counts,
        "accuracy": round(counts["correct"] / answered, 3) if answered else None,
        "precision": precision, "recall": recall, "f1": f1,
        "coverage": _rate(counts["correct"] + counts["wrong value"], answered),
        "red_flag_yes_total": len(rf_yes),
        "red_flag_yes_caught": caught,
        "red_flag_recall": _rate(caught, len(rf_yes)),
        "red_flag_yes_missed": len(rf_yes) - caught,
        # a red flag the model filled although the answer key has no answer: the most dangerous kind of error
        "red_flag_invented": sum(1 for r in rows if r["red_flag"] and r["status"] == "invented"),
        "discarded": discarded, "discard_rate": _rate(discarded, discarded + filled), "discard_reasons": reasons,
        "doctor_approved": ap, "doctor_edited": ed, "doctor_flagged": fg, "edit_rate": _rate(ed, filled),
        "mean_extract_s": round(sum(ex_t) / len(ex_t), 1) if ex_t else None,
    }
    return {"summary": summary, "rows": rows, "modules": modules, "per_case": per_case}
