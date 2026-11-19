"""Score extracted cases against data/gold/<case id>.json and save data/scores.csv."""
import _path  # noqa: F401
import csv
from cdss import config, scoring

res = scoring.evaluate()
s, rows = res["summary"], res["rows"]
if not s["cases_scored"]:
    raise SystemExit("No cases to score. A case needs an extraction and a matching file in data/gold/.")
print("Cases scored:", ", ".join(s["cases_scored"]))
if s["cases_without_gold"]:
    print("No answer key for:", ", ".join(s["cases_without_gold"]))
print("Counts:", s["counts"])
print("Field accuracy:", s["accuracy"])
print(f"Red-flag 'yes' answers caught: {s['red_flag_yes_caught']} of {s['red_flag_yes_total']}")
bad = [r for r in rows if r["status"] != "correct"]
for r in bad:
    print(f"  {r['case']:12} {r['field']:22} {r['status']:12} gold={r['gold']!r} model={r['model']!r}")
with open(config.DATA_DIR / "scores.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print("Saved", config.DATA_DIR / "scores.csv")
