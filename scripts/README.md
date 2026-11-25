# Scripts

These command-line helpers operate the CDSS Intake pipeline. Run each script from the repository root; `_path.py` makes the local `cdss` package available to the scripts.

## Pipeline

### 1. Transcribe recordings

```bash
python scripts/01_transcribe.py
```

Transcribes every supported audio file in `data/audio` with Whisper. Transcripts are written to `data/transcripts/`, and each recording creates a dashboard case using the file name without its extension.

Supported extensions include `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.opus`, `.webm`, and `.mp4`.

```bash
# Transcribe selected files
python scripts/01_transcribe.py path/to/recording.m4a

# Transcribe again, replacing existing transcripts
python scripts/01_transcribe.py --redo
```

### 2. Extract structured case data

```bash
python scripts/02_extract.py
```

Uses the configured language-model backend to fill the intake template for cases that have transcripts and have not yet been extracted.

```bash
# Extract selected case IDs
python scripts/02_extract.py d01 d02

# Re-extract and replace existing values
python scripts/02_extract.py --redo d01
```

Run `scripts/check_llm.py` before the first extraction if the language-model connection may need verification.

### 3. Evaluate against answer keys

```bash
python scripts/03_evaluate.py
```

Scores extracted cases against matching JSON files in `data/gold/` and writes `data/scores.csv`. It also reports field, red-flag, doctor-review, and speech-recognition metrics when matching data is available.

## Supporting scripts

- `check_llm.py` — verifies that the configured language-model backend responds.
- `seed_samples.py` — adds the bundled 31 sample dialogues as cases and copies their answer keys into `data/gold/`.
- `serve.py` — starts the Streamlit dashboard.
- `_path.py` — shared repository-root path setup imported by the command-line scripts.

```bash
# Check the language-model backend
python scripts/check_llm.py

# Add bundled demonstration cases
python scripts/seed_samples.py

# Start the dashboard locally
python scripts/serve.py

# Make the dashboard reachable on the local network
python scripts/serve.py --share
```

## Typical workflow

```bash
python scripts/check_llm.py
python scripts/seed_samples.py
python scripts/01_transcribe.py
python scripts/02_extract.py
python scripts/03_evaluate.py
python scripts/serve.py
```

All scripts share the same `data/cases/` case files and can be used with the dashboard. Keep real recordings and case data out of version control unless approved for storage and sharing.
