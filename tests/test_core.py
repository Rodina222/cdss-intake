"""Offline tests of the pipeline with a fake language model: python tests/test_core.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["SCHEMA_PATH"] = str(Path(os.environ["DATA_DIR"]) / "schema.json")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdss import config, llm, pipeline, report, samples, scoring, store  # noqa: E402
import cdss.extract as ex  # noqa: E402
from cdss.extract import parse_json, validate  # noqa: E402

FAKE = {
    "site": {"value": "knee", "evidence_quote": "ركبتي"},
    "side": {"value": "right", "evidence_quote": "اليمين"},
    "onset": {"value": "من حوالي تلات شهور", "evidence_quote": "من حوالي تلات شهور"},
    "pain_severity": {"value": "6", "evidence_quote": "حوالي ستة"},
    "swelling": {"value": "yes", "evidence_quote": "الركبة متورمة شوية"},
    "fever": {"value": "no", "evidence_quote": "مفيش سخونية"},
    "diabetes": {"value": "yes", "evidence_quote": "عندي سكر"},      # invented: quote not in transcript
    "weakness": {"value": "maybe", "evidence_quote": "ضعف"},         # invalid value
}
ex.llm.call_llm = lambda system, user: "```json\n" + json.dumps({"fields": FAKE}, ensure_ascii=False) + "\n```"

n = 0
def check(cond, msg):
    global n
    assert cond, "FAILED: " + msg
    n += 1
    print("ok  ", msg)

made = samples.seed_samples()
check(len(made) == 21, "seed adds 21 sample cases")
check((config.GOLD_DIR / "d01.json").exists() and (config.GOLD_DIR / "sample-d01.json").exists(), "gold files copied")
check(samples.seed_samples() == [], "seeding twice adds nothing")

pipeline.run_step("sample-d01", "extract")
case = store.get("sample-d01")
F = case["fields"]
check(F["site"]["value"] == "knee" and F["pain_severity"]["value"] == 6, "values filled and number converted")
check(not F["diabetes"]["filled"], "invented answer (quote not in transcript) was discarded")
check(not F["weakness"]["filled"], "invalid enum value was discarded")
check({x["field"] for x in case["flags"]} == {"diabetes", "weakness"}, "flags list both discarded values")
check(not F["night_pain"]["filled"] and F["night_pain"]["value"] is None, "unanswered field stays not answered")
check(case["busy"] is None and case["error"] is None, "busy flag cleared")

c2 = pipeline.edit_field("sample-d01", "pain_severity", "7", who="Dr A", kind="edited by doctor")
check(c2["fields"]["pain_severity"]["edited"] and c2["fields"]["pain_severity"]["ai"] == 6, "edit keeps the AI value")
check(c2["events"][-1]["who"] == "Dr A", "edit records who")
for bad, why in [(("side", "upside"), "bad enum edit rejected"), (("night_pain", "yes"), "cannot edit an unfilled field")]:
    try:
        pipeline.edit_field("sample-d01", *bad); check(False, why)
    except ValueError:
        check(True, why)
pipeline.decide("sample-d01", "site", "approve", who="Dr A")
pipeline.decide("sample-d01", "swelling", "flag", who="Dr A")
c3 = pipeline.save_review("sample-d01", "ok", "save", who="Dr A")
check(c3["reviewed"] and (config.REPORT_DIR / "sample-d01.md").exists(), "review saved and report written")
kinds = [e["kind"] for e in c3["events"]]
check({"AI filled", "edited by doctor", "approved", "flagged", "review saved"} <= set(kinds), "all event kinds recorded")
md = report.report_markdown(c3)
check(
    "- No positive red flags reported." in md
    and "Patient explicitly said no to: Fever?" in md
    and "**Not answered (ask the patient):**" in md,
    "report: red flags first, unasked ones listed"
)
ev = scoring.evaluate()
s = ev["summary"]
check(s["cases_scored"] == ["sample-d01"] and s["counts"]["invented"] == 0 and s["counts"]["missed"] > 0, "scoring counts missed fields, none invented")
row = [x for x in ev["rows"] if x["field"] == "pain_severity"][0]
check(row["status"] == "correct", "a doctor's edit does not change the AI's score")

pipeline.create_case("my case", "ركبتي بتوجعني")
check(store.exists("my-case"), "case id is sanitised")
try:
    pipeline.create_case("my case", "x"); check(False, "duplicate id rejected")
except ValueError:
    check(True, "duplicate id rejected")
store.delete("my-case")
check(not store.exists("my-case"), "delete")

def boom(system, user):
    raise llm.LLMError("model is down")
ex.llm.call_llm = boom
try:
    pipeline.run_step("sample-d02", "extract"); check(False, "model failure raises")
except RuntimeError as e:
    check(str(e) == "model is down" and store.get("sample-d02")["error"] == "model is down" and store.get("sample-d02")["busy"] is None, "model failure is stored on the case and the busy flag cleared")

cl, fl = validate({"fields": {"site": {"value": "KNEE", "evidence_quote": "ركبتى"}}}, "ركبتي اليمين")
check("site" in cl and cl["site"]["value"] == "knee", "quote matched after Arabic spelling normalisation")
check(parse_json('blah {"fields": {}} blah') == {"fields": {}}, "JSON found inside extra text")
print(f"\nAll {n} checks passed.")
