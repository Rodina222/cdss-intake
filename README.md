# CDSS Intake: local pipeline and dashboard

Audio or transcript → speech to text → language model fills the orthopedic question template → check → report → doctor review.
Everything runs on this computer except the language model call when you choose an OpenCode Zen model.

```
recording ──► scripts/01_transcribe.py ──► data/transcripts
                                              │
                    scripts/02_extract.py ◄───┘  (model fills the template, every value needs the patient's own words)
                          │
                          ▼
                    data/cases/<id>.json  ◄──►  dashboard (Streamlit)  ──► data/reports/<id>.md
                          │
          scripts/03_evaluate.py  (compares with data/gold/<id>.json)
```
The scripts and the dashboard use the same case files, so you can mix them: transcribe with the script, review in the dashboard, or do everything in the dashboard.

## 1. Install (once)

Python 3.10 or newer.

```
python -m venv .venv
.venv\Scripts\activate          # Windows.  On Mac or Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-whisper.txt     # only on the computer that transcribes audio
copy .env.example .env          # Mac or Linux: cp .env.example .env
```

## 2. Choose the language model (edit `.env`)

**A. OpenCode with a free model (default).** Install OpenCode from opencode.ai and sign in to OpenCode Zen as its docs describe. The default model is `opencode/glm-5.3-flash-free`. The scripts call the `opencode` command, because OpenCode's docs say its free models work only through the OpenCode client. Free models change often: check the current list at opencode.ai/docs/zen and set `OPENCODE_MODEL`. Qwen is not in the free list at the time of writing.

**B. Qwen on your own computer (Ollama).** Nothing leaves the machine, so this is the safest choice for anything sensitive. Install Ollama, run `ollama pull qwen2.5:7b-instruct`, then in `.env` set `LLM_BACKEND=openai` (the other lines for this option are already in `.env.example`). A 7B model may be weak on Egyptian Arabic. Use a larger Qwen if your computer can run it, and judge it with the evaluation step.

Then check it works:

```
python scripts/check_llm.py
```
If it fails with the OpenCode option, the flags may differ in your OpenCode version. Run `opencode run --help`, then change `OPENCODE_CMD` in `.env` (`{model}` and `{prompt}` are filled in).

**Privacy.** Use role-played dialogues only. Never send real patient data to a hosted free model: some of them keep or train on what you send (see opencode.ai/docs/zen for each model's policy). `glm-5.3-flash-free` and `deepseek-v4.1-flash-free` are listed there as zero retention, no training.

## 3. Run

Dashboard (Streamlit):

```
python scripts/serve.py            # or: streamlit run streamlit_app.py
```
It opens at http://localhost:8501. Sign in with your name (recorded next to every change you make). Add a recording or paste a transcript, press **Run extraction**, then work through Summary, Report, Doctor review and History. The **Evaluation** screen scores cases against answer keys.

Scripts:

```
python scripts/01_transcribe.py        # every file in data/audio  (name them d01.m4a, d02.m4a ...)
python scripts/02_extract.py           # every case with a transcript
python scripts/03_evaluate.py          # accuracy, wrong/missed/invented fields, red-flag "yes" caught
```
To try everything before you have recordings, run `python scripts/seed_samples.py` (or press **Add the 21 samples** in the dashboard). It adds typed sample cases and copies the 21 answer keys to `data/gold`, so recordings named d01 to d21 are scored automatically. d01 to d09 are short starter dialogues; d10 to d21 follow the full General Orthopedic Intake Template (121 fields in `schema.json`: site screen, core, trauma, red flags, and every region module). Cases made by the scripts appear in the dashboard (press **Import from data folders** for files you copied in by hand).

## 4. Share it with the team

Set a password first. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `APP_PASSWORD` (or put `APP_PASSWORD=...` in `.env`). Without a password anyone who can open the address can use the app, and the sidebar says so.

**A. Same Wi-Fi or network.** On the computer that has Whisper and the model: `python scripts/serve.py --share`. Others open `http://<that computer's IP address>:8501`. Allow the port through the firewall if asked. The computer must stay on. All case data stays on it.

**B. Over the internet from that computer.** Run the app as in A, then expose port 8501 with a tunnel tool such as Cloudflare Tunnel or ngrok. Anyone with the link can reach the sign-in page, so use a long password. The link changes each time unless you set up a named tunnel. Data stays on your computer. This is not tested here.

**C. Streamlit Community Cloud.** Gives a stable link and can limit viewers to invited emails. It has real limits for this project: the OpenCode command and Ollama do not exist there, so the language model must be a hosted OpenAI-compatible API with a key (OpenCode's free models cannot be used outside OpenCode); speech to text is impractical there, so use pasted or script-made transcripts; and its disk is temporary, so cases and reviews can disappear when the app restarts or sleeps. Put the settings from `.streamlit/secrets.toml.example` in the app's Secrets box. Use it only for demos with sample data, not as the place where reviews are kept.

For the 20 November demo, A or B from one team computer is the simplest and keeps the data in one place.

## Speech to text

`faster-whisper` runs on this computer. The first run downloads the model (about 500 MB for `small`). On a laptop without a GPU keep `WHISPER_MODEL=small`. `large-v3` is more accurate but needs a GPU. Always read the transcript and fix mistakes in the dashboard before extracting.

## Rules the code enforces

- Every filled value needs an evidence quote that really occurs in the transcript. Otherwise the value is discarded and listed under "discarded by the checks".
- Values must be allowed options or numbers. Unknown fields are dropped.
- Unanswered fields stay "not answered". The report says a red flag is absent only if the patient said no, and lists unasked red flags as "ask the patient".
- No diagnosis, treatment, dose, score or probability appears anywhere.
- Scores use the model's own value, so a doctor's correction does not hide a model mistake.

## Template

`schema.json` is the question template (24 starter fields). It is created on first run. Replace it with the doctor-approved template in the same format (`id`, `module`, `question_en`, `question_ar`, `type` = enum/number/text, `options`, `red_flag`). The dashboard picks up new fields without code changes.

## Tests

```
python tests/test_core.py      # pipeline, checks and scoring
python tests/test_app.py       # drives the Streamlit app, including sign-in
```
Both run offline with a fake model.

## Not verified

The Whisper step and the real model calls (OpenCode or Ollama) were not run when this was written, because the build environment had no model downloads or accounts. The code around them was tested with stand-ins: a fake `opencode` program and a fake model. Sharing options A to C were not tried. Run `scripts/check_llm.py` and one recording first, and send the team any error text.
