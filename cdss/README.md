# CDSS Core Package

The `cdss/` package contains the core pipeline, configuration, storage, reporting, scoring, and language-model integration for CDSS Intake. It is imported by the Streamlit dashboard and the command-line scripts in [`scripts/`](../scripts/).

## Package layout

| Module | Responsibility |
| --- | --- |
| `pipeline.py` | Creates and updates cases; runs transcription and extraction; manages review actions and background jobs. |
| `asr.py` | Transcribes audio locally with `faster-whisper` and PyAV. |
| `extract.py` | Builds model prompts, parses model output, and validates answers against transcript evidence. |
| `llm.py` | Calls an OpenAI-compatible server such as Ollama or the OpenCode CLI. |
| `config.py` | Loads environment settings and defines project data paths. |
| `store.py` | Reads and atomically writes one JSON case file per case. |
| `schema.py` | Loads and defines the intake form, field types, prompts, and allowed values. |
| `scoring.py` | Compares extracted values with optional hand-written gold answer keys. |
| `report.py` | Generates Markdown case and review reports. |
| `samples.py` | Loads the bundled role-played demonstration dialogues. |
| `textutil.py` | Provides identifiers and Arabic/Unicode text normalization helpers. |
| `__init__.py` | Marks the directory as a Python package. |

## Processing flow

```text
case or transcript
        |
        v
pipeline.create_case / set_transcript
        |
        v
pipeline.transcribe_case     (optional audio step)
        |
        v
pipeline.extract_case
  - extract.extract()
  - llm.call_llm()
  - evidence validation
        |
        v
store.save()
        |
        v
Streamlit dashboard or scripts
```

Cases are stored at `data/cases/<case-id>.json`. Audio, transcripts, reports, and large language-model working files are separated into the directories defined in `config.py`.

## Key APIs

### Create and update a case

```python
from cdss import pipeline

case = pipeline.create_case("roleplay-001", transcript="patient transcript text", source="text")
pipeline.set_transcript(case["id"], "updated transcript text")
```

Case IDs are sanitized by `textutil.safe_id()`. Creating a case with an ID that already exists raises `ValueError`.

### Transcribe audio

```python
case = pipeline.create_case("roleplay-002", source="audio", audio_file="roleplay-002.wav")
case = pipeline.transcribe_case(case["id"])
```

The package looks for uploaded recordings in `DATA_DIR/audio` and writes transcript JSON and text under `DATA_DIR/transcripts`.

### Extract fields

```python
case = pipeline.extract_case("roleplay-001")
```

Extraction is split into field modules and small chunks. Every model value is checked for:

- a known field ID;
- the field's allowed type and enum options;
- a direct quote from the transcript; and
- an appropriate preceding assistant question when `REQUIRE_QUESTION=1`.

Rejected values are included in `case["flags"]` with a machine-readable issue name.

### Review fields

```python
pipeline.edit_field("roleplay-001", "pain", 7)
pipeline.decide("roleplay-001", "pain", "approve", who="Reviewer")
pipeline.save_review("roleplay-001", "Reviewed without diagnosis", who="Reviewer")
```

Field edits preserve the original AI value and are recorded in the case audit history.

## Configuration

Settings are loaded by `cdss/config.py` from environment variables or a project-level `.env` file.

### Storage paths

- `DATA_DIR`: root data directory, default `./data`
- `AUDIO_DIR`: uploaded recordings
- `TRANSCRIPT_DIR`: transcription JSON and text
- `GOLD_DIR`: optional gold answer-key JSON files
- `CASE_DIR`: structured case JSON files
- `REPORT_DIR`: generated Markdown reports
- `SCHEMA_PATH`: intake template, default `./schema.json`

### Language-model backends

Set `LLM_BACKEND=openai` for an OpenAI-compatible server, for example Ollama:

```dotenv
LLM_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen3:14b
OPENAI_API_KEY=ollama
LLM_TIMEOUT=600
```

Or set `LLM_BACKEND=opencode`:

```dotenv
LLM_BACKEND=opencode
OPENCODE_MODEL=opencode/deepseek-v4.1-flash-free
OPENCODE_CMD=opencode run -m {model} {prompt}
```

### Whisper

```dotenv
WHISPER_MODEL=small
WHISPER_DEVICE=auto
WHISPER_COMPUTE=int8
WHISPER_LANGUAGE=ar
```

For more information, copy the repository-level [`.env.example`](../.env.example) and follow the setup instructions in the project [README](../README.md).

## Evidence and safety rules

- A filled answer must be supported by a quote in the transcript.
- Enum values must match the schema's allowed options.
- Numeric values must parse as numbers.
- Answers are checked against the question named by the model when `REQUIRE_QUESTION` is enabled.
- Unknown fields and unsupported values are discarded rather than guessed.
- Stored doctor edits do not overwrite the original AI value.

This package is intended for role-played intake workflows and decision-support review. It does not diagnose, recommend treatment, calculate a clinical score, or determine probabilities.

## Extending the package

### Add or change intake fields

Update `schema.json` and adjust `cdss/schema.py` if the form requires new modules or prompt behavior. Keep field IDs stable because they are used in case JSON, reports, reviews, and gold answer keys.

### Add a model backend

Add a backend implementation in `cdss/llm.py`, expose its settings through `cdss/config.py`, and handle it in `call_llm()`. Keep backend calls synchronous; `pipeline.py` manages concurrency and background jobs.

### Run checks

From the repository root:

```bash
python tests/test_core.py
python tests/test_app.py
```

The test suite uses fake model responses and offline sample data, so it does not require Whisper or a hosted language model.
