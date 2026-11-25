"""Score extracted cases against data/gold/<case id>.json and save data/scores.csv."""
import _path  # noqa: F401
import csv
from cdss import config, scoring, store

res = scoring.evaluate()
s, rows = res["summary"], res["rows"]
if not s["cases_scored"]:
    raise SystemExit("No cases to score. A case needs an extraction and a matching file in data/gold/.")
print("Cases scored:", ", ".join(s["cases_scored"]))
if s["cases_without_gold"]:
    print("No answer key for:", ", ".join(s["cases_without_gold"]))
print("Counts:", s["counts"])
pc = lambda v: "n/a" if v is None else f"{round(v * 100)}%"
print(f"Field accuracy (recall): {pc(s['accuracy'])}   precision: {pc(s['precision'])}   F1: {pc(s['f1'])}   coverage: {pc(s['coverage'])}")
print(f"Red-flag 'yes' answers caught: {s['red_flag_yes_caught']} of {s['red_flag_yes_total']}")
print(f"Red-flag recall: {pc(s['red_flag_recall'])}   red-flag yes missed or wrong: {s['red_flag_yes_missed']}")
print(f"Red-flag answers invented (filled, but not in the answer key): {s['red_flag_invented']}")
print(f"Discarded by the checks: {s['discarded']} ({pc(s['discard_rate'])} of what the model returned)  {s['discard_reasons']}")
print(f"Doctor review: approved {s['doctor_approved']}, edited {s['doctor_edited']}, flagged {s['doctor_flagged']}, edit rate {pc(s['edit_rate'])}")
if s["mean_extract_s"] is not None:
    print(f"Mean extraction time per case: {s['mean_extract_s']} s")
print("By module:")
for m in res["modules"]:
    print(f"  {m['module']:12} precision {pc(m['precision']):>4}  recall {pc(m['recall']):>4}  F1 {pc(m['f1']):>4}  (correct {m['correct']}, wrong {m['wrong']}, missed {m['missed']}, invented {m['invented']})")
asr = scoring.evaluate_asr()
if asr["rows"]:
    print(f"Speech recognition on {len(asr['rows'])} recordings: word error rate {pc(asr['mean_wer'])}, character error rate {pc(asr['mean_cer'])}")
bad = [r for r in rows if r["status"] != "correct"]
for r in bad:
    print(f"  {r['case']:12} {r['field']:22} {r['status']:12} gold={r['gold']!r} model={r['model']!r}")
with open(config.DATA_DIR / "scores.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print("Saved", config.DATA_DIR / "scores.csv")
