# CDSS Intake
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![faster-whisper](https://img.shields.io/badge/transcription-faster--whisper-green.svg)](https://github.com/SYSTRAN/faster-whisper)
[![LLM backends](https://img.shields.io/badge/LLM-Ollama%20%7C%20OpenCode-purple.svg)](https://ollama.com/)
[![Offline tests](https://img.shields.io/badge/tests-offline-lightgrey.svg)](#tests)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A doctor-in-the-loop orthopedic pre-consultation dashboard. CDSS Intake turns role-played intake recordings or transcripts into structured case data, evidence-linked answers, reviewable reports, and evaluation results.

> **Clinical safety:** CDSS Intake is a decision-support prototype, not a diagnostic or treatment system. Use role-played dialogues rather than real patient data unless your deployment has been approved for that use. A clinician must review every extracted value before use.

## What it does

- Accepts audio recordings or pasted Egyptian/English Arabic transcripts.
- Transcribes audio locally with `faster-whisper`.
- Extracts transcript-supported answers with a configurable language model.
- Provides summary, doctor review, reporting, editing, and audit history in a Streamlit dashboard.
- Evaluates extracted cases against optional hand-written answer keys.

## Requirements

- Python 3.10 or newer and `pip`
- Optional: Ollama or OpenCode with access to a compatible language model
- Optional: a capable CPU or GPU for local Whisper transcription

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS or Linux
source .venv/bin/activate
```

Install the dashboard and pipeline dependencies:

```bash
python -m pip install -r requirements.txt
```

Only on the computer that will transcribe audio, install the optional transcription dependencies:

```bash
python -m pip install -r requirements-whisper.txt
```

Create local configuration from the example file:

```bash
# Windows
copy .env.example .env

# macOS or Linux
cp .env.example .env
```

Configure a language-model backend in `.env` as described below. Never commit `.env`, credentials, real recordings, patient data, or generated private case files.

## Configure a language model

Choose one backend in `.env`.

### Ollama (local processing)

Install Ollama, download a model, and configure its OpenAI-compatible API:

```bash
ollama pull qwen3:14b
```

```dotenv
LLM_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen3:14b
OPENAI_API_KEY=ollama
```

### OpenCode Zen

Install and sign in to OpenCode, then configure:

```dotenv
LLM_BACKEND=opencode
OPENCODE_MODEL=opencode/deepseek-v4.1-flash-free
OPENCODE_CMD=opencode run -m {model} {prompt}
```

Hosted models may retain or process submitted text. Use role-played dialogues only unless your organization has approved the provider and its privacy terms.

To check the configured model, run:

```bash
python scripts/check_llm.py
```

## Run the dashboard

Start the dashboard from the repository root:

```bash
python scripts/serve.py
```

Or invoke Streamlit directly:

```bash
streamlit run streamlit_app.py
```

Open <http://localhost:8501> on the computer running the app.

### Access from another device or an external URL

The Streamlit server is configured to listen on all IPv4 interfaces (`0.0.0.0`), so it can accept connections addressed to the host computer. After starting the app, Streamlit prints the available Local, Network, and, where provided by the hosting environment, External URLs. Open the Network or External URL from the other device. Use the actual URL shown by your environment.

If the URL does not load, check that:

1. The dashboard process is still running and listening on port `8501`.
2. The host firewall, cloud security group, and network routing/NAT permit inbound TCP traffic to port `8501`.
3. You are using the host's reachable address. A private `10.x.x.x` Network URL is generally only reachable from the same private network; public access requires a managed tunnel or reverse proxy.

Before sharing the dashboard, set a strong password using one of these methods.

In `.streamlit/secrets.toml`:

```toml
APP_PASSWORD = "choose-a-long-unique-password"
```

Or set `APP_PASSWORD` in the environment. Keep secrets out of the repository. Do not expose this app to the public internet without authentication and appropriate HTTPS, network access controls, and privacy/security review.

## Dashboard workflow

1. Sign in and create or open a case.
2. Upload an audio recording or paste a transcript.
3. Transcribe the audio or save the transcript.
4. Run extraction and check the values against the patient's words.
5. Generate and download the report.
6. Approve, edit, or flag fields in Doctor review, then save a comment.
7. Optionally evaluate the case against a matching answer key.

The dashboard can also import cases from data folders or seed role-played sample cases.

## Adaptive Intake Follow-up Agent

The Adaptive Intake Follow-up Agent improves the clinical intake process by identifying missing information and asking relevant follow-up questions based on the patient's initial responses.

### Key Features

- Generates follow-up questions based on missing or incomplete clinical information.
- Avoids asking questions that have already been answered.
- Filters out irrelevant follow-up questions.
- Prioritizes clinically important information and red flags.
- Validates follow-up answers before incorporating them into the case.
- Stores follow-up answers separately from the original AI-extracted answers.
- Integrates relevant follow-up information into the clinical report while preserving the original responses.

### Workflow

1. Reviews the initial patient intake data.
2. Identifies unanswered or incomplete relevant fields.
3. Generates targeted follow-up questions.
4. Collects and validates the patient's responses.
5. Updates the case with the additional information.
6. Makes the collected information available for doctor review and reporting.

### Testing

The feature was tested with dedicated follow-up test cases, alongside the existing core and dashboard test suites.

- Follow-up tests: Passed.
- Core tests: 24/24 passed.
- Dashboard tests: 21/21 passed.

## Command-line pipeline

```bash
# Transcribe recordings in data/audio
python scripts/01_transcribe.py

# Extract cases with transcripts
python scripts/02_extract.py

# Evaluate cases with matching keys in data/gold
python scripts/03_evaluate.py

# Add demonstration cases
python scripts/seed_samples.py
```

The scripts and dashboard use the same case files and can be used independently.

## Evaluation metrics

Run `python scripts/03_evaluate.py` after adding extracted cases and matching files in `data/gold/<case-id>.json`. The script evaluates model output against the gold answer keys and saves field-level results to `data/scores.csv`.

Scoring uses the model's original AI values, not later doctor edits. It compares every schema field that is present in the prediction or gold answer key.

| Metric | Meaning |
| --- | --- |
| Correct | The prediction and gold value match. |
| Wrong value | Both fields are present, but the values differ. |
| Missed | The gold answer exists, but the model did not fill it. |
| Invented | The model filled a field that is absent from the gold answer. |
| Field accuracy / recall | `correct / (correct + wrong value + missed)` |
| Precision | `correct / (correct + wrong value + invented)` |
| Recall | `correct / (correct + wrong value + missed)` |
| F1 | Harmonic mean of precision and recall |
| Coverage | `(correct + wrong value) / (correct + wrong value + missed)` |

Red flags, doctor-review actions, value validation, transcription, and performance are also reported:

| Metric | Meaning |
| --- | --- |
| Red-flag `yes` caught | Gold `yes` red flags whose extracted value is also correct. |
| Red-flag recall | `red_flag_yes_caught / red_flag_yes_total` |
| Red-flag `yes` missed or wrong | Gold `yes` red flags that were missed or incorrectly extracted. |
| Red-flag answers invented | The model filled a red flag, but it is absent from the gold answer. |
| Discarded values | Values removed by schema, evidence, enum, number, or question checks. |
| Discard rate | `discarded / (discarded + filled)` |
| Doctor approved | Number of retained fields marked approved by a doctor. |
| Doctor edited | Number of retained fields edited by a doctor. |
| Doctor flagged | Number of retained fields marked as flagged. |
| Edit rate | `doctor_edited / filled` |
| Mean extraction time | Mean extraction time per scored case, in seconds. |

### Metric breakdowns

The evaluation report additionally provides:

- Precision, recall, F1, and four status counts by intake module.
- Precision, recall, F1, and status counts for each scored case.
- Per-field incorrect rows containing case ID, field ID, status, gold value, and model value.
- A list of extracted cases with no matching gold answer key.
- ASR word error rate (WER) and character error rate (CER) for audio cases that have both Whisper transcription and a matching scripted transcript.
- Rejected-value reasons reported by the extraction checks.

WER and CER are calculated using an edit distance after Arabic text normalization:

- **WER:** word-level edit distance divided by words in the reference transcript.
- **CER:** character-level edit distance divided by characters in the reference transcript.

The field-level comparison also tracks the module and whether a field is a red flag in `data/scores.csv`. Evaluation currently uses only extracted cases with a matching gold file; cases without extraction or gold answers are not included in the aggregate field metrics.

## Speech-to-text configuration

Whisper settings are controlled in `.env`:

```dotenv
WHISPER_MODEL=small
WHISPER_DEVICE=auto
WHISPER_COMPUTE=int8
```

For a CUDA-enabled server, for example:

```dotenv
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE=float16
```

The first transcription downloads the selected model. Keep real clinical audio off hosted deployments unless the service has been approved for that data.

## Customize the template

`schema.json` defines the intake questions and allowed values. Fields include a stable ID, module, bilingual question text, type, optional allowed values, and whether they are red flags. Change the template only with approval from the responsible clinical owner and rerun the tests after modifications.

## Data, privacy, and project structure

The app stores uploaded audio, transcripts, case JSON, and reports under `data/`. Treat these files as potentially sensitive. Do not commit real patient information, identifiable recordings, credentials, or private case files. Ollama processes locally; a hosted model backend may send transcript content to an external provider.

```text
streamlit_app.py            Streamlit dashboard entry point
cdss/                       Core pipeline, configuration, storage, and reporting
scripts/                    Transcription, extraction, evaluation, and server helpers
data/audio/                 Uploaded recordings
data/transcripts/           Saved transcripts
data/cases/                 Structured case JSON files
data/gold/                  Optional hand-written answer keys
data/reports/               Generated Markdown reports
data/scores.csv             Evaluation results
samples/                    Role-played sample dialogues
schema.json                 Intake question template
tests/                      Core and dashboard tests
.env.example                Environment variable template
requirements.txt            Dashboard and pipeline dependencies
requirements-whisper.txt    Optional local transcription dependencies
```

The application requires transcript evidence for filled answers, rejects unsupported values, and leaves unanswered fields explicitly unanswered. A red flag is reported absent only when the patient explicitly says no. Reports contain no diagnosis, treatment, dose, score, or probability, and doctor edits preserve the original model value for evaluation.

## Tests

Run the offline test suites:

```bash
python tests/test_core.py
python tests/test_app.py
```

The tests use a fake model and do not require a Whisper download or hosted model account.

## Limits

The application is built and tested around role-played dialogues. Whisper and model calls depend on tools and services outside this repository. Evaluation is meaningful only when answer keys match case IDs and the approved template. Accuracy, safety, bilingual performance, and clinical suitability require local validation before any real-world use.

## License

This project is licensed under the [MIT License](LICENSE).
