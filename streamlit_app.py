"""CDSS intake dashboard (Streamlit). Run: streamlit run streamlit_app.py"""
import hmac
import html
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from cdss import config, llm, pipeline, report, samples, scoring, store
from cdss.schema import BY_ID, MODULE_TITLES, SCHEMA
from cdss.textutil import safe_id

st.set_page_config(page_title="CDSS Intake", page_icon=None, layout="wide")

PAGES = ["Cases", "Intake", "Summary", "Report", "Doctor review", "History", "Evaluation"]
AUDIO_TYPES = ["m4a", "wav", "mp3", "ogg", "flac", "opus", "webm", "aac", "mp4"]

st.markdown("""
<style>
.ar{font-family:"Noto Naskh Arabic","Geeza Pro","Segoe UI",Tahoma,serif;font-size:1.1rem;direction:rtl;text-align:right;line-height:1.7}
.ar-inline{font-family:"Noto Naskh Arabic","Geeza Pro","Segoe UI",Tahoma,serif;direction:rtl;unicode-bidi:isolate}
.qar{font-family:"Noto Naskh Arabic","Geeza Pro","Segoe UI",Tahoma,serif;color:#5B6F76;font-size:.85rem;direction:rtl;text-align:left}
.tag{display:inline-block;font-size:.8rem;padding:1px 9px;border-radius:99px;background:#E4EDED;color:#44575d;white-space:nowrap}
.tag.ai{background:#D9EEEE;color:#263B43}.tag.ok{background:#DDF1E3;color:#1E7B3E}
.tag.edit{background:#FBEBD0;color:#8A5100}.tag.flag{background:#FBE4E1;color:#B3261E}
.rf{border:1px solid #B3261E;background:#FBE4E1;border-radius:10px;padding:12px 16px;margin-bottom:12px;color:#263B43}
.rf h4{color:#B3261E;margin:0 0 6px 0}
.banner{background:#FBEBD0;color:#8A5100;border-radius:8px;padding:8px 12px;font-size:.9rem;margin-bottom:12px}
.hdr{font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:#5B6F76}
s{color:#7d8d92;margin-right:8px}
.stButton button{padding:.2rem .55rem;font-size:.85rem;white-space:nowrap}
</style>
""", unsafe_allow_html=True)


def esc(x):
    return html.escape("" if x is None else str(x))


# ---------------------------------------------------------------- sign in
def _password():
    pw = os.environ.get("APP_PASSWORD")
    if pw:
        return pw
    try:
        return st.secrets.get("APP_PASSWORD")
    except Exception:
        return None


PASSWORD = _password()
if "me" not in st.session_state:
    st.session_state.me = ""
if not st.session_state.me:
    st.title("CDSS Intake")
    st.caption("Orthopedic pre-consultation. Role-played dialogues only, no real patient data.")
    with st.form("login"):
        name = st.text_input("Your name (recorded next to every change you make)")
        pw = st.text_input("Password", type="password") if PASSWORD else ""
        if st.form_submit_button("Continue"):
            if not name.strip():
                st.error("Enter your name.")
            elif PASSWORD and not hmac.compare_digest(pw.encode(), PASSWORD.encode()):
                st.error("Wrong password.")
            else:
                st.session_state.me = name.strip()
                st.rerun()
    if not PASSWORD:
        st.warning("No APP_PASSWORD is set, so anyone who can open this address can enter. Set one before sharing the link.")
    st.stop()

ME = st.session_state.me

# ---------------------------------------------------------------- state
if "_goto" in st.session_state:                      # set by buttons; applied before the radio is created
    st.session_state.page = st.session_state.pop("_goto")
st.session_state.setdefault("page", "Cases")
st.session_state.setdefault("cur", None)
st.session_state.setdefault("editing", None)
st.session_state.setdefault("eval", None)


def goto(page, cid=None):
    st.session_state["_goto"] = page
    if cid is not None:
        st.session_state["cur"] = cid
    st.session_state["editing"] = None


def case():
    cid = st.session_state.get("cur")
    c = store.get(cid) if cid else None
    if cid and c is None:
        st.session_state["cur"] = None
    return c


def filled(c):
    return [f for f in SCHEMA if c["fields"][f["id"]]["filled"]]


def status_of(s):
    if s["busy"]:
        return "Transcribing…" if s["busy"] == "transcribe" else "Extracting…"
    if s["error"]:
        return "Error"
    if s["reviewed"]:
        return "Reviewed"
    if s["report_seen"]:
        return "Report ready"
    if s["extracted"]:
        return "Extracted"
    return "Transcript ready" if s["has_transcript"] else "New"


def fmt(f, v):
    return str(v).replace("_", " ") if f["type"] == "enum" else str(v)


def value_html(f, d):
    def one(v):
        return f'<span class="ar-inline">{esc(v)}</span>' if f["type"] == "text" else esc(fmt(f, v))
    if d["edited"]:
        return f"<b><s>{one(d['ai'])}</s>{one(d['value'])}</b>"
    return f"<b>{one(d['value'])}</b>"


def badge(d):
    if d["decision"] == "flag":
        return '<span class="tag flag">Flagged</span>'
    if d["decision"] == "approve":
        return '<span class="tag ok">Approved</span>'
    if d["edited"]:
        return '<span class="tag edit">Edited</span>'
    return '<span class="tag ai">AI-filled</span>'


def model_name(c):
    return (c.get("model") or {}).get("llm") or config.llm_model_name()


def banner(c):
    st.markdown(f'<div class="banner"><b>CASE {esc(c["id"])}</b> &nbsp; Role-played dialogues only, no real patient data. '
                f'Fields are filled by {esc(model_name(c))} and checked against the transcript. '
                f'The doctor reviews every value. Not a diagnosis.</div>', unsafe_allow_html=True)


def need_case():
    st.info("Open a case first.")
    st.button("Go to cases", on_click=goto, args=("Cases",))


def need_extract(c):
    banner(c)
    st.info("This case has not been read yet.")
    st.button("Go to intake", on_click=goto, args=("Intake",))


def rf_block(c):
    F = c["fields"]
    rf = [f for f in SCHEMA if f["red_flag"]]
    yes = [f for f in rf if F[f["id"]]["filled"] and F[f["id"]]["value"] == "yes"]
    no = [f for f in rf if F[f["id"]]["filled"] and F[f["id"]]["value"] == "no"]
    na = [f for f in rf if not F[f["id"]]["filled"]]
    out = []
    if yes:
        out.append("<ul style='margin:0 0 6px 0'>" + "".join(
            f'<li><b>{esc(f["question_en"])}</b> yes. <span class="ar-inline">{esc(F[f["id"]]["quote"])}</span></li>' for f in yes) + "</ul>")
    else:
        out.append("<p style='margin:0 0 6px 0'>None reported by the patient.</p>")
    if no:
        out.append("<p style='margin:0 0 6px 0;color:#44575d'>Patient said no to: " + ", ".join(esc(f["question_en"].rstrip("?")) for f in no) + ".</p>")
    if na:
        out.append("<p style='margin:0'><b>Not answered, ask the patient:</b> " + ", ".join(esc(f["question_en"].rstrip("?")) for f in na) + ".</p>")
    cls = "rf" if yes else "banner"
    style = "" if yes else ' style="background:#EEF3F3;color:#263B43"'
    st.markdown(f'<div class="{cls}"{style}><h4 style="{"" if yes else "color:#263B43;"}">Red flags</h4>{"".join(out)}</div>', unsafe_allow_html=True)


def field_tables(c, mode):
    """mode is 'summary' (edit only) or 'review' (approve, edit, flag)."""
    F = c["fields"]
    modules = ["red_flags"] + [m for m in dict.fromkeys(f["module"] for f in SCHEMA) if m != "red_flags"]
    for m in modules:
        items = [f for f in SCHEMA if f["module"] == m and F[f["id"]]["filled"]]
        if not items:
            continue
        with st.container(border=True):
            st.markdown(f"**{'Red flag answers' if m == 'red_flags' else MODULE_TITLES.get(m, m)}**")
            h = st.columns([2.4, 1.7, 2.6, 1.3, 4.0])
            for col, t in zip(h, ["Question", "Value", "Patient's words", "Status", ""]):
                col.markdown(f'<span class="hdr">{t}</span>', unsafe_allow_html=True)
            for f in items:
                fid, d = f["id"], F[f["id"]]
                a, b, q, s, act = st.columns([2.4, 1.7, 2.6, 1.3, 4.0], vertical_alignment="center")
                a.markdown(f'{esc(f["question_en"])}<div class="qar">{esc(f["question_ar"])}</div>', unsafe_allow_html=True)
                editing = st.session_state.editing == (mode, fid)
                if editing:
                    key = f"ed-{c['id']}-{fid}"
                    if f["type"] == "enum":
                        new = b.selectbox("New value", f["options"], index=f["options"].index(str(d["value"])) if str(d["value"]) in f["options"] else 0,
                                          key=key, label_visibility="collapsed")
                    elif f["type"] == "number":
                        new = b.number_input("New value", value=float(d["value"]), key=key, label_visibility="collapsed")
                    else:
                        new = b.text_input("New value", value=str(d["value"]), key=key, label_visibility="collapsed")
                else:
                    b.markdown(value_html(f, d), unsafe_allow_html=True)
                q.markdown(f'<div class="ar">{esc(d["quote"])}</div>', unsafe_allow_html=True)
                s.markdown(badge(d), unsafe_allow_html=True)
                if editing:
                    c1, c2 = act.columns(2)
                    if c1.button("Save", key=f"sv-{mode}-{fid}", type="primary"):
                        try:
                            rev = mode == "review"
                            pipeline.edit_field(c["id"], fid, new, who=ME, kind="edited by doctor" if rev else "edited before report")
                            if rev and store.get(c["id"])["fields"][fid]["decision"] != "approve":
                                pipeline.decide(c["id"], fid, "approve", who=ME)
                            st.session_state.editing = None
                            st.rerun()
                        except (ValueError, TypeError) as e:
                            st.error(str(e))
                    if c2.button("Cancel", key=f"cn-{mode}-{fid}"):
                        st.session_state.editing = None
                        st.rerun()
                elif mode == "summary":
                    if act.button("Edit", key=f"ed-{mode}-{fid}"):
                        st.session_state.editing = (mode, fid)
                        st.rerun()
                else:
                    c1, c2, c3 = act.columns(3)
                    if c1.button("Approve", key=f"ap-{fid}", disabled=d["decision"] == "approve"):
                        pipeline.decide(c["id"], fid, "approve", who=ME)
                        st.rerun()
                    if c2.button("Edit", key=f"ed-{mode}-{fid}"):
                        st.session_state.editing = (mode, fid)
                        st.rerun()
                    if c3.button("Flag", key=f"fl-{fid}"):
                        pipeline.decide(c["id"], fid, "flag", who=ME)
                        st.rerun()


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### CDSS Intake")
    st.caption("Orthopedic pre-consultation")
    st.radio("Screen", PAGES, key="page", label_visibility="collapsed")
    cc = case()
    st.divider()
    st.caption(f"Signed in as **{ME}**")
    st.caption(f"Open case: **{cc['id']}**" if cc else "No case open")

page = st.session_state.page

# ---------------------------------------------------------------- Cases
if page == "Cases":
    st.title("Cases")
    st.caption("Each case is one intake dialogue. Add a recording or paste a transcript, read it with the model, then check and review.")
    rows = store.list_cases()
    if not rows:
        st.info("No cases yet. Add one below.")
    for r in rows:
        c1, c2, c3, c4, c5 = st.columns([2, 1.2, 2.4, 1.6, 2], vertical_alignment="center")
        c1.markdown(f"**{esc(r['id'])}**")
        c2.write(r["source"] or "")
        c3.write(r["concern"] or "Not read yet")
        c4.markdown(f'<span class="tag {"ok" if r["reviewed"] else ("flag" if r["error"] else "")}">{status_of(r)}</span>', unsafe_allow_html=True)
        b1, b2 = c5.columns(2)
        b1.button("Open", key=f"open-{r['id']}", on_click=goto, args=("Intake", r["id"]))
        if st.session_state.get("confirm_del") == r["id"]:
            if b2.button("Confirm", key=f"cd-{r['id']}", type="primary"):
                store.delete(r["id"])
                st.session_state.confirm_del = None
                if st.session_state.cur == r["id"]:
                    st.session_state.cur = None
                st.rerun()
        elif b2.button("Delete", key=f"del-{r['id']}"):
            st.session_state.confirm_del = r["id"]
            st.rerun()

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("New case")
        with st.form("newcase", clear_on_submit=False):
            nid = st.text_input("Case name (optional). Name it like the answer key, for example d01")
            up = st.file_uploader("Audio recording", type=AUDIO_TYPES)
            txt = st.text_area("Or paste a transcript instead", height=110)
            go = st.form_submit_button("Create case", type="primary")
        if go:
            try:
                if up is not None:
                    cid = safe_id(nid or Path(up.name).stem)
                    if store.exists(cid):
                        raise ValueError(f"A case named '{cid}' already exists.")
                    name = cid + Path(up.name).suffix.lower()
                    (config.AUDIO_DIR / name).write_bytes(up.getvalue())
                    pipeline.create_case(cid, "", "audio", name)
                    goto("Intake", cid)
                    with st.spinner("Transcribing the audio on this computer. This can take several minutes…"):
                        try:
                            pipeline.run_step(cid, "transcribe")
                        except RuntimeError:
                            pass                       # the error is stored on the case and shown on the Intake screen
                    st.rerun()
                elif txt.strip():
                    cid = safe_id(nid or "case-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
                    pipeline.create_case(cid, txt.strip(), "text")
                    goto("Intake", cid)
                    st.rerun()
                else:
                    st.error("Add an audio file or paste a transcript.")
            except ValueError as e:
                st.error(str(e))
    with right, st.container(border=True):
        st.subheader("This computer")
        st.markdown(f"Speech to text: faster-whisper **{config.WHISPER_MODEL}**  \n"
                    f"Language model: **{config.LLM_BACKEND} / {config.llm_model_name()}**  \n"
                    f"Template: {len(SCHEMA)} questions  \nData folder: `{config.DATA_DIR}`")
        b1, b2, b3 = st.columns(3)
        if b1.button("Test the model"):
            with st.spinner("Asking the model…"):
                try:
                    out = llm.call_llm("Reply with exactly this JSON and nothing else.", '{"ok": true}')
                    st.success("The model answered: " + out[:200])
                except Exception as e:
                    st.error(str(e))
        if b2.button("Import from data folders"):
            made = samples.import_folders()
            st.success(f"Imported {len(made)} case(s)." if made else "Nothing new in the data folders.")
            if made:
                st.rerun()
        if b3.button("Add the 31 samples"):
            made = samples.seed_samples()
            st.success(f"Added {len(made)} sample cases." if made else "The sample cases are already there.")
            if made:
                st.rerun()

# ---------------------------------------------------------------- Intake
elif page == "Intake":
    c = case()
    if not c:
        need_case(); st.stop()
    banner(c)
    st.title("Intake dialogue")
    st.caption("The patient's answers come from a recording (speech to text) or a pasted transcript. The model reads the transcript and fills the template. Nothing is filled that the patient did not say.")
    if c.get("error"):
        st.error(c["error"])
    if c.get("busy"):
        st.info("Another user or script is running this case right now. Refresh in a moment.")
        if st.button("Refresh"):
            st.rerun()
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.subheader("Transcript")
        if c.get("audio_file") and (config.AUDIO_DIR / c["audio_file"]).exists():
            st.audio(str(config.AUDIO_DIR / c["audio_file"]))
            if st.button("Transcribe again" if c["transcript"] else "Transcribe audio", disabled=bool(c.get("busy"))):
                with st.spinner("Transcribing on this computer. This can take several minutes…"):
                    try:
                        pipeline.run_step(c["id"], "transcribe")
                    except RuntimeError:
                        pass
                st.rerun()
            if c.get("asr"):
                a = c["asr"]
                st.caption(f"{a['model']} · {a['duration_s']} s of audio · {a['seconds_to_transcribe']} s to transcribe")
        tx = st.text_area("Transcript", value=c["transcript"], height=220, key=f"tx-{c['id']}-{hash(c['transcript']) % 100000}",
                          label_visibility="collapsed", disabled=bool(c.get("busy")))
        if st.button("Save transcript", disabled=bool(c.get("busy"))):
            pipeline.set_transcript(c["id"], tx)
            st.toast("Transcript saved")
            st.rerun()
        st.caption("Fix speech-to-text mistakes here before extracting.")
    with right, st.container(border=True):
        st.subheader("Fill the template")
        nf = len(filled(c))
        done = nf > 0 or bool(c.get("model"))
        if done:
            st.markdown(f'<span class="tag ok">Done</span> {nf} fields filled, {len(SCHEMA) - nf} not answered.', unsafe_allow_html=True)
            st.button("Continue to summary", type="primary", on_click=goto, args=("Summary",))
            again = st.checkbox("Replace the current values and decisions")
        else:
            again = True
        if st.button("Run extraction" if not done else "Run extraction again", disabled=bool(c.get("busy")) or not (tx or "").strip() or not again):
            if tx != c["transcript"]:
                pipeline.set_transcript(c["id"], tx)
            with st.spinner(f"Reading the transcript with {config.llm_model_name()}. This can take a minute…"):
                try:
                    pipeline.run_step(c["id"], "extract")
                except RuntimeError:
                    pass
            st.rerun()
        if any(str(x.get("issue", "")).startswith("model_error") for x in c.get("flags") or []):
            st.warning("The language model failed on part of this case, so some fields were not filled. Press Run extraction again.")
        if c.get("flags"):
            with st.expander(f"{len(c['flags'])} value(s) discarded by the checks"):
                st.dataframe(pd.DataFrame([{"field": x["field"], "why": x["issue"].replace("_", " "), "detail": x.get("quote") or x.get("value") or ""} for x in c["flags"]]),
                             hide_index=True, width="stretch")

# ---------------------------------------------------------------- Summary
elif page == "Summary":
    c = case()
    if not c:
        need_case(); st.stop()
    if not filled(c):
        need_extract(c); st.stop()
    banner(c)
    st.title("Case summary")
    st.caption("Check each AI-filled value against the patient's own words. Edit anything that is wrong, then continue. Unanswered questions stay \"not answered\".")
    rf_block(c)
    field_tables(c, "summary")
    na = [f["question_en"].rstrip("?") for f in SCHEMA if not f["red_flag"] and not c["fields"][f["id"]]["filled"]]
    with st.container(border=True):
        st.markdown("**Not answered**")
        st.caption("; ".join(na) if na else "None.")
    if st.button("Continue to report", type="primary"):
        pipeline.mark_report_seen(c["id"])
        goto("Report")
        st.rerun()

# ---------------------------------------------------------------- Report
elif page == "Report":
    c = case()
    if not c:
        need_case(); st.stop()
    if not filled(c):
        need_extract(c); st.stop()
    banner(c)
    st.title("History report")
    st.caption("One page for the doctor, built only from the filled fields. Red flags the patient reported come first.")
    md = report.report_markdown(c)
    with st.container(border=True):
        st.markdown(md)
        st.caption(f"Model: {model_name(c)}. Contains no diagnosis, treatment advice, dose, score or probability. The doctor reviews before use.")
    b1, b2 = st.columns([1, 1])
    b1.button("Continue to doctor review", type="primary", on_click=goto, args=("Doctor review",))
    b2.download_button("Download report (.md)", md, file_name=f"{c['id']}_report.md", mime="text/markdown")

# ---------------------------------------------------------------- Doctor review
elif page == "Doctor review":
    c = case()
    if not c:
        need_case(); st.stop()
    if not filled(c):
        need_extract(c); st.stop()
    banner(c)
    st.title("Doctor review")
    st.caption("Approve, edit or flag each value. Every change is saved next to the original AI value so the team can measure how often the doctor corrects the model.")
    rf_block(c)
    field_tables(c, "review")
    f = filled(c)
    decided = sum(1 for x in f if c["fields"][x["id"]]["decision"] or c["fields"][x["id"]]["edited"])
    with st.container(border=True):
        st.markdown("**Comment**")
        cm = st.text_area("Comment", value=c["comment"], key=f"cm-{c['id']}", label_visibility="collapsed")
        b1, b2, b3 = st.columns([1, 1.4, 3], vertical_alignment="center")
        if b1.button("Save review", type="primary"):
            pipeline.save_review(c["id"], cm, "save", who=ME)
            st.toast("Review saved. The report is in data/reports.")
            st.rerun()
        if b2.button("Request more information"):
            pipeline.save_review(c["id"], cm, "request", who=ME)
            st.toast("Request recorded in history")
            st.rerun()
        b3.caption(f"{decided} of {len(f)} fields decided")

# ---------------------------------------------------------------- History
elif page == "History":
    c = case()
    if not c:
        need_case(); st.stop()
    st.title("History")
    st.caption(f"What the model filled, what was changed, and by whom. Case {c['id']}.")
    fl = filled(c)
    F = c["fields"]
    ai = len(fl)
    ap = sum(1 for f in fl if F[f["id"]]["decision"] == "approve")
    ed = sum(1 for f in fl if F[f["id"]]["edited"])
    fg = sum(1 for f in fl if F[f["id"]]["decision"] == "flag")
    cols = st.columns(5)
    for col, (label, v) in zip(cols, [("Filled by AI", ai), ("Approved", ap), ("Edited", ed), ("Flagged", fg), ("Edit rate", f"{round(100 * ed / ai)}%" if ai else "n/a")]):
        col.metric(label, v)
    ev = c["events"]
    if not ev:
        st.info("No events yet for this case. Run extraction on the intake screen.")
    else:
        rows = []
        for e in reversed(ev):
            f = BY_ID.get(e["field"])
            if e["kind"] == "AI filled":
                ch = str(e["to"])
            elif e["from"] is not None:
                ch = f'{e["from"]} → {e["to"]}'
            else:
                ch = str(e["to"] or "")
            try:
                t = datetime.fromisoformat(e["t"]).astimezone().strftime("%d %b %H:%M")
            except ValueError:
                t = e["t"]
            rows.append({"Time": t, "Event": e["kind"], "Field": f["question_en"].rstrip("?") if f else "Whole case", "Change": ch, "By": e["who"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------------------------------------------------------------- Evaluation
elif page == "Evaluation":
    st.title("Evaluation")
    st.caption("Compares what the model filled with the hand-filled answer keys in data/gold. A case is scored when its name matches an answer key (case d01 uses d01.json). Results on role-played dialogues are an upper bound for real patients.")
    if st.button("Score all cases", type="primary"):
        st.session_state.eval = scoring.evaluate()
    ev = st.session_state.eval
    if ev is None:
        st.info('Press "Score all cases".')
    else:
        s = ev["summary"]
        if not s["cases_scored"]:
            st.info("No case can be scored yet. A case needs an extraction and a matching answer key."
                    + (f" No answer key for: {', '.join(s['cases_without_gold'])}." if s["cases_without_gold"] else ""))
        else:
            cn = s["counts"]
            cols = st.columns(7)
            for col, (label, v) in zip(cols, [("Cases scored", len(s["cases_scored"])),
                                              ("Field accuracy", "n/a" if s["accuracy"] is None else f"{round(s['accuracy'] * 100)}%"),
                                              ("Wrong values", cn["wrong value"]), ("Missed fields", cn["missed"]), ("Invented fields", cn["invented"]),
                                              ("Red-flag yes caught", f"{s['red_flag_yes_caught']} / {s['red_flag_yes_total']}"),
                                              ("Red flags invented", s.get("red_flag_invented", 0))]):
                col.metric(label, v)
            if s["cases_without_gold"]:
                st.caption("No answer key for: " + ", ".join(s["cases_without_gold"]))
            bad = [r for r in ev["rows"] if r["status"] != "correct"]
            st.subheader("Fields that are not correct")
            if bad:
                st.dataframe(pd.DataFrame(bad)[["case", "field", "status", "gold", "model", "red_flag"]].astype(str), hide_index=True, width="stretch")
            else:
                st.success("Every filled field matched the answer key.")