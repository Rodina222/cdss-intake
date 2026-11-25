# CDSS Intake

A local, doctor-in-the-loop orthopedic pre-consultation dashboard. It turns a role-played intake recording or transcript into structured case data, evidence-linked answers, a reviewable report, and an evaluation against a gold answer key.

> **Clinical safety:** CDSS Intake is a decision-support prototype, not a diagnostic or treatment system. It must use role-played dialogues rather than real patient data unless the deployment has been approved for that use. A clinician should review every extracted value before use.

## What it does

- Accepts an audio recording or pasted Egyptian/English Arabic transcript.
- Transcribes audio locally with `faster-whisper`.
- Extracts answers from the transcript with a configurable language model.
- Keeps only values supported by direct evidence from the patient's words.
- Presents answers in a Streamlit dashboard for summary, review, reporting, editing, and history.
- Saves doctor approvals, edits, flags, comments, and audit events.
- Generates a Markdown history report containing no diagnosis, treatment, dose, score, or probability.
- Evaluates extracted cases against optional hand-written answer keys.

```text
Audio recording
      |
      v
scripts/01_transcribe.py --> data/transcripts
      |
      v
scripts/02_extract.py --> data/cases/<case-id>.json
                             |                    |
                             v                    v
                       Streamlit dashboard --> data/reports/<case-id>.md
                             |
                             v
scripts/03_evaluate.py <--> data/gold/<case-id>.json
```

The scripts and dashboard use the same case files, so either interface can be used independently.

## Features

- **Audio and text intake:** upload m4a, wav, mp3, ogg, flac, opus, webm, aac, or mp4 files, or paste a transcript.
- **Evidence checks:** every filled value must appear in the transcript and use a permitted enum or number.
- **Red flags:** reported `yes` answers are highlighted; `no` answers are recorded only when stated; unanswered red flags are marked for follow-up.
- **Doctor review:** approve, edit, or flag each extracted field, with the original AI value retained.
- **Audit history:** changes and review actions record the signed-in reviewer and timestamp.
- **Password protection:** optional shared-dashboard sign-in through `APP_PASSWORD` or Streamlit secrets.
- **Evaluation:** compare field accuracy, wrong, missed, and invented values, and red-flag detection against answer keys.
- **Seed cases:** load 31 role-played sample cases for demonstrations and offline testing.

## Project structure

```text
streamlit_app.py            Streamlit dashboard entry point
cdss/                       Core pipeline, configuration, storage, reporting, and scoring
scripts/                    Transcription, extraction, evaluation, seeding, and server helpers
data/
  audio/                    Uploaded recordings
data/cases/                 Structured case JSON files
data/gold/                  Optional hand-written answer keys
data/reports/               Generated Markdown reports
data/transcripts/           Saved transcripts
samples/                    Bundled role-played sample dialogues
schema.json                 Intake question template
tests/                      Core and dashboard tests
.env.example                Environment variable template
requirements.txt            Dashboard and pipeline dependencies
requirements-whisper.txt    Optional local transcription dependencies
```

## Requirements

- Python 3.10 or newer
- `pip`
- Optional: a local [Ollama](https://ollama.com/) installation
- Optional: OpenCode and access to an OpenCode Zen model
- Optional: a GPU or CPU capable of running Whisper for transcription

## Installation

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows
.venv\Scripts\activate

# macOS or Linux
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt

# Only on the computer that transcribes audio
python -m pip install -r requirements-whisper.txt
```

Create your local configuration:

```bash
# Windows
copy .env.example .env

# macOS or Linux
cp .env.example .env
```

Never commit `.env`, patient data, real recordings, or generated private case files.

## Configure a language model

The extraction backend is configured in `.env`. Use one backend at a time.

### Option A: Ollama (recommended for local processing)

Install Ollama, then download a model:

```bash
ollama pull qwen3:14b
```

The default settings in `.env.example` use Ollama through its OpenAI-compatible API:

```dotenv
LLM_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen3:14b
OPENAI_API_KEY=ollama
```

For a faster, weaker model:

```bash
ollama pull qwen2.5:7b-instruct
```

Then set `OPENAI_MODEL=qwen2.5:7b-instruct`.

### Option B: OpenCode Zen

Install and sign in to OpenCode, then configure:

```dotenv
LLM_BACKEND=opencode
OPENCODE_MODEL=opencode/deepseek-v4.1-flash-free
OPENCODE_CMD=opencode run -m {model} {prompt}
```

Hosted models may retain or process submitted text. Use role-played dialogues only unless your organization has approved the provider and privacy terms.

### Check the model

```bash
python scripts/check_llm.py
```

If an OpenCode command fails because your installed CLI uses different flags, run:

```bash
opencode run --help
```

Then update `OPENCODE_CMD` while retaining the `{model}` and `{prompt}` placeholders.

## Run the dashboard

```bash
python scripts/serve.py
```

Or run Streamlit directly:

```bash
streamlit run streamlit_app.py
```

Open <http://localhost:8501>.

Before the dashboard is shared, create `.streamlit/secrets.toml`:

```toml
APP_PASSWORD = "choose-a-long-password"
```

Alternatively, set `APP_PASSWORD` in `.env`. Set a real password before exposing the app beyond a trusted local machine.

## Run the command-line pipeline

```bash
# Transcribe every recording in data/audio
python scripts/01_transcribe.py

# Extract every case that has a transcript
python scripts/02_extract.py

# Evaluate cases that have matching answer keys in data/gold
python scripts/03_evaluate.py
```

Add demonstration cases:

```bash
python scripts/seed_samples.py
```

The dashboard also provides **Add the 31 samples** and **Import from data folders** actions.

## Speech-to-text configuration

The default `small` model is suitable for a laptop. Whisper settings are controlled in `.env`:

```dotenv
WHISPER_MODEL=small
WHISPER_DEVICE=auto
WHISPER_COMPUTE=int8
```

For a CUDA-enabled server:

```dotenv
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE=float16
```

The first transcription downloads the selected model. Keep real clinical audio off hosted deployments unless the service has been approved for that data.

## Dashboard workflow

1. Sign in and create or open a case.
2. Upload an audio recording or paste a transcript.
3. Transcribe or save the transcript.
4. Run extraction.
5. Review the field values and evidence in the Summary screen.
6. Generate and download the report.
7. Approve, edit, or flag each field in Doctor review.
8. Save a doctor comment and review the audit history.
9. Optionally score the case against a matching gold answer key.

## Customize the template

`schema.json` defines the intake questions and allowed values. It is created or loaded on application startup as needed.

Fields can define:

- a stable `id`;
- a module and bilingual question text;
- a type such as `enum`, `number`, or `text`; 
- allowed options; and
- whether the field is a red flag.

Change the template only with approval from the responsible clinical owner, and rerun the tests after any modification.

## Data and privacy behavior

- Extraction only runs remotely if a hosted backend such as OpenCode is selected.
- Ollama keeps processing on the local machine.
- Every answer requires a matching quote from the transcript.
- Unknown enum values and unsupported numbers are discarded.
- Unanswered fields remain explicitly unanswered.
- A red flag is reported absent only when the patient explicitly says `no`.
- Reports and UI labels state that this is not a diagnosis.
- A doctor correction does not alter the original model value used for evaluation.

## Tests

Run the offline test suites:

```bash
python tests/test_core.py
python tests/test_app.py
```

The tests use a fake model and do not require a Whisper download or a hosted model account.

## Sharing on a local network

From the computer running Whisper and the selected model:

```bash
python scripts/serve.py --share
```

Other devices on the same network can open:

```text
http://<host-computer-ip>:8501
```

Allow the Streamlit port through the computer's firewall. For internet exposure, use a managed tunnel or reverse proxy and protect it with authentication. Avoid using shared hosting that does not provide the required local Whisper and model runtime.

## Limits and status

- The application is built and tested around role-played dialogues.
- Whisper and real hosted/local model calls depend on models and tools outside the repository.
- Evaluation is meaningful only when gold answer keys match the case IDs and approved template.
- Accuracy, safety, bilingual performance, and clinical suitability require local validation before any real-world use.

## License

No license file is currently included. The repository owner should add an appropriate license before redistributing or deploying the project. 
