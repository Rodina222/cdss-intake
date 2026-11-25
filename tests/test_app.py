"""Drives the Streamlit app headlessly with a fake model: python tests/test_app.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["SCHEMA_PATH"] = str(Path(os.environ["DATA_DIR"]) / "schema.json")
os.environ["APP_PASSWORD"] = "secret-pw"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cdss.extract as ex  # noqa: E402
from cdss import store  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

def fake(system, user):
    f = {"site": {"value": "back", "evidence_quote": "ضهري"},
         "weight_loss": {"value": "yes", "evidence_quote": "وزني نزل حوالي ٨ كيلو من غير ما أعمل ريجيم"},
         "onset": {"value": "من شهرين", "evidence_quote": "من شهرين"}}
    return json.dumps({"fields": f}, ensure_ascii=False)
ex.llm.call_llm = fake

n = 0
def check(cond, msg):
    global n
    assert cond, "FAILED: " + msg
    n += 1
    print("ok  ", msg)

def noexc(at, where):
    check(not at.exception, f"no exception: {where}" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))

at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
check(any("Password" in t.label for t in at.text_input), "login asks for a password when APP_PASSWORD is set")
at.text_input[0].set_value("Dr Test"); at.text_input[1].set_value("wrong"); at.button[0].click(); at.run()
check(any("Wrong password" in e.value for e in at.error), "wrong password refused")
at.text_input[1].set_value("secret-pw"); at.button[0].click(); at.run()
noexc(at, "after login")
check(at.session_state.me == "Dr Test", "signed in with a name")

# add the 21 samples from the Cases page
[b for b in at.button if b.label == "Add the 21 samples"][0].click(); at.run()
noexc(at, "seed samples")
check(len(store.list_cases()) == 21, "21 sample cases created")

# create a new case from pasted text
at.text_area[0].set_value("أهلا، ضهري بيوجعني. من شهرين. وزني نزل حوالي ٨ كيلو من غير ما أعمل ريجيم.")
at.text_input[0].set_value("mine")
[b for b in at.button if b.label == "Create case"][0].click(); at.run()
noexc(at, "create case")
check(at.session_state.cur == "mine" and at.session_state.page == "Intake", "new case opened on the Intake screen")

[b for b in at.button if b.label == "Run extraction"][0].click(); at.run()
noexc(at, "run extraction")
c = store.get("mine")
check(c["fields"]["weight_loss"]["value"] == "yes" and c["busy"] is None, "extraction through the app fills the template")

[r for r in at.radio if r.label == "Screen"][0].set_value("Summary").run()
noexc(at, "summary page")
check(any("Unexplained weight loss" in m.value for m in at.markdown), "red flag shown on the summary")
[b for b in at.button if b.label == "Edit"][-1].click(); at.run()
noexc(at, "edit mode")
at.text_input[-1].set_value("من ٣ شهور")
[b for b in at.button if b.label == "Save"][0].click(); at.run()
c = store.get("mine")
check(c["fields"]["onset"]["edited"] and c["fields"]["onset"]["value"] == "من ٣ شهور", "edit saved")
check(c["events"][-1]["who"] == "Dr Test", "edit attributed to the signed-in user")

[b for b in at.button if b.label == "Continue to report"][0].click(); at.run()
noexc(at, "report page")
check(at.session_state.page == "Report" and store.get("mine")["report_seen"], "report page reached")

at.radio[0].set_value("Doctor review").run()
noexc(at, "review page")
[b for b in at.button if b.label == "Flag"][0].click(); at.run()
at.text_area[-1].set_value("send for X-ray")
[b for b in at.button if b.label == "Save review"][0].click(); at.run()
c = store.get("mine")
check(c["reviewed"] and c["comment"] == "send for X-ray" and any(e["kind"] == "flagged" for e in c["events"]), "flag and review saved")

at.radio[0].set_value("History").run(); noexc(at, "history page")
at.radio[0].set_value("Evaluation").run()
[b for b in at.button if b.label == "Score all cases"][0].click(); at.run()
noexc(at, "evaluation page")
print(f"\nAll {n} checks passed.")
