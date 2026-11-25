"""Fill the question template for every case that has a transcript.

Usage: python scripts/02_extract.py [--redo] [case ids...]
"""
import _path  # noqa: F401
import argparse
from cdss import config, pipeline, store

ap = argparse.ArgumentParser()
ap.add_argument("ids", nargs="*", help="case ids; default is every case with a transcript and no extraction yet")
ap.add_argument("--redo", action="store_true", help="extract again, replacing values and decisions")
a = ap.parse_args()

todo = a.ids or [s["id"] for s in store.list_cases() if s["has_transcript"] and (a.redo or not s["extracted"])]
if not todo:
    raise SystemExit("Nothing to do. Run scripts/01_transcribe.py first, or add a case in the dashboard.")
print(f"Language model: {config.LLM_BACKEND} / {config.llm_model_name()}")
for cid in todo:
    try:
        c = pipeline.extract_case(cid)
    except Exception as e:
        print(f"{cid}: FAILED ({e}). Continuing with the next case.")
        continue
    n = sum(1 for d in c["fields"].values() if d["filled"])
    print(f"{cid}: {n} fields filled, {len(c['flags'])} discarded by the checks")
    for fl in c["flags"]:
        print("    discarded:", fl)
    failed = [fl for fl in c["flags"] if str(fl.get("issue", "")).startswith("model_error")]
    if failed:
        print(f"    WARNING: {len(failed)} model call(s) failed, so part of this case was not filled. Run it again.")
