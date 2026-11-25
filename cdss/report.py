from .schema import SCHEMA, MODULE_TITLES


def _filled(c, f):
    return c["fields"][f["id"]]["filled"]


def report_markdown(c):
    F = c["fields"]
    followups = c.get("followup_answers", {})

    def answered(f):
        return _filled(c, f) or f["id"] in followups

    L = [
        f"# Pre-consultation history (case {c['id']})",
        "*Role-played dialogue. Filled by a language model for the doctor to review. Not a diagnosis.*",
        ""
    ]

    # Red flags
    rf = [f for f in SCHEMA if f["red_flag"]]
    yes, no, na = [], [], []

    for f in rf:
        fid = f["id"]

        if _filled(c, f):
            d = F[fid]
            if d["value"] == "yes":
                yes.append(
                    f'- **{f["question_en"]}** yes. "{d["quote"]}" (AI extraction)'
                )
            elif d["value"] == "no":
                no.append(f["question_en"])

        elif fid in followups:
            answer = followups[fid]
            if answer["value"] == "yes":
                yes.append(
                    f'- **{f["question_en"]}** yes. '
                    f'"{answer["answer_text"]}" (patient follow-up)'
                )
            elif answer["value"] == "no":
                no.append(f["question_en"])

        else:
            na.append(f["question_en"])

    L.append("## Red flags reported by the patient")
    L.extend(yes or ["- No positive red flags reported."])

    if no:
        L.append("- Patient explicitly said no to: " + "; ".join(no))
    if na:
        L.append("- **Not answered (ask the patient):** " + "; ".join(na))

    L.append("")

    # Original AI-extracted answers
    modules = []
    for f in SCHEMA:
        if f["module"] != "red_flags" and f["module"] not in modules:
            modules.append(f["module"])

    for m in modules:
        items = [
            f for f in SCHEMA
            if f["module"] == m and _filled(c, f)
        ]

        if not items:
            continue

        L.append(f"## {MODULE_TITLES.get(m, m)}")

        for f in items:
            d = F[f["id"]]
            mark = " (edited)" if d["edited"] else ""
            L.append(
                f'- {f["question_en"]} **{d["value"]}**{mark}. "{d["quote"]}"'
            )

        L.append("")

    # Separate patient follow-up answers
    if followups:
        L.append("## Patient Follow-up Answers")

        for f in SCHEMA:
            fid = f["id"]
            if fid not in followups:
                continue

            answer = followups[fid]
            L.append(
                f'- **{f["question_en"]}** **{answer["value"]}**. '
                f'"{answer["answer_text"]}" (Source: patient follow-up)'
            )

        L.append("")

    # Questions unanswered by both sources
    missing = [
        f["question_en"]
        for f in SCHEMA
        if f["module"] != "red_flags" and not answered(f)
    ]

    L.extend([
        "## Not answered",
        "; ".join(missing) if missing else "None."
    ])

    return "\n".join(L)
