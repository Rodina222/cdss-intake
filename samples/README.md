# Sample dialogues

This directory contains bundled role-played dialogues used to demonstrate and evaluate CDSS Intake. The samples are synthetic or role-played intake material; they are not real patient records.

## Directory layout

| Path | Contents |
| --- | --- |
| [`transcripts/`](./transcripts/) | Egyptian Arabic intake transcripts in plain-text `.txt` files. |
| [`gold/`](./gold/) | Hand-written answer-key JSON files paired with the transcripts by case ID. |

Each transcript and gold answer key use the same base filename, such as `d01.txt` and `d01.json`. The `d10`–`d21` files include the larger cases currently added beyond the first nine short examples.

## Use the samples

Seed all bundled cases and copy their answer keys into the local data directories:

```bash
python scripts/seed_samples.py
```

This creates cases named `sample-d01`, `sample-d02`, and so on for every transcript found in `samples/transcripts/`. It also copies each `samples/gold/*.json` answer key to `data/gold/` under both its original name and a `sample-` prefixed name.

The dashboard's **Add the 31 samples** and **Import from data folders** actions call the same project helpers. The button label refers to the project's intended sample set; at present, the files supplied in this repository determine how many cases are seeded.

## Gold answer-key format

A gold file contains field IDs and expected values:

```json
{
  "site": "knee",
  "side": "right",
  "onset": "من حوالي تلات شهور",
  "onset_type": "gradual",
  "injury": "no",
  "pain_severity": 6,
  "worse_with": "لما أنزل السلم",
  "swelling": "yes",
  "night_pain": "yes",
  "fever": "no"
}
```

Answer keys must use field IDs and value formats from [`schema.json`](../schema.json). They are optional for normal dashboard use, but are required when evaluating extraction results with `python scripts/03_evaluate.py`.

## Evaluation

After seeding or importing the samples, run:

```bash
python scripts/03_evaluate.py
```

Cases are evaluated against answer keys with matching case IDs. A gold file named `d01.json` can also match your own recording or transcript if it is named `d01.m4a`, `d01.wav`, or `d01.txt`.

## Safety and data handling

- Keep these dialogues role-played and de-identify all examples.
- Do not replace the bundled files with real patient information, recordings, or clinical records.
- Review transcripts and answer keys before publishing or distributing a fork.
- These samples support demonstration and offline testing only; CDSS Intake is not a diagnostic or treatment system.
