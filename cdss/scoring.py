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


def evaluate():
    rows, cases_scored, no_gold = [], [], []
    for s in store.list_cases():
        if not s["extracted"]:
            continue
        gold = load_gold(s["id"])
        if gold is None:
            no_gold.append(s["id"])
            continue
        rows += score_case(store.get(s["id"]), gold)
        cases_scored.append(s["id"])
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("correct", "wrong value", "missed", "invented")}
    answered = counts["correct"] + counts["wrong value"] + counts["missed"]
    rf_yes = [r for r in rows if r["red_flag"] and r["gold"] == "yes"]
    summary = {
        "cases_scored": cases_scored, "cases_without_gold": no_gold, "counts": counts,
        "accuracy": round(counts["correct"] / answered, 3) if answered else None,
        "red_flag_yes_total": len(rf_yes),
        "red_flag_yes_caught": sum(1 for r in rf_yes if r["status"] == "correct"),
    }
    return {"summary": summary, "rows": rows}
