from .schema import SCHEMA, MODULE_TITLES


def _filled(c, f):
    return c["fields"][f["id"]]["filled"]


def report_markdown(c):
    F = c["fields"]
    L = [f"# Pre-consultation history (case {c['id']})",
         "*Role-played dialogue. Filled by a language model for the doctor to review. Not a diagnosis.*", ""]
    rf = [f for f in SCHEMA if f["red_flag"]]
    yes = [f for f in rf if _filled(c, f) and F[f["id"]]["value"] == "yes"]
    no = [f for f in rf if _filled(c, f) and F[f["id"]]["value"] == "no"]
    na = [f for f in rf if not _filled(c, f)]
    L.append("## Red flags reported by the patient")
    L += [f"- **{f['question_en']}** yes. \"{F[f['id']]['quote']}\"" for f in yes] or ["- None reported."]
    if no:
        L.append("- Patient said no to: " + "; ".join(f["question_en"] for f in no))
    if na:
        L.append("- **Not answered (ask the patient):** " + "; ".join(f["question_en"] for f in na))
    L.append("")
    modules = []
    for f in SCHEMA:
        if f["module"] != "red_flags" and f["module"] not in modules:
            modules.append(f["module"])
    for m in modules:
        items = [f for f in SCHEMA if f["module"] == m and _filled(c, f)]
        if not items:
            continue
        L.append(f"## {MODULE_TITLES.get(m, m)}")
        for f in items:
            d = F[f["id"]]
            mark = " (edited)" if d["edited"] else ""
            L.append(f"- {f['question_en']} **{d['value']}**{mark}. \"{d['quote']}\"")
        L.append("")
    missing = [f["question_en"] for f in SCHEMA if f["module"] != "red_flags" and not _filled(c, f)]
    L += ["## Not answered", "; ".join(missing) if missing else "None."]
    return "\n".join(L)
