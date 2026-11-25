
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["SCHEMA_PATH"] = str(
    Path(os.environ["DATA_DIR"]) / "schema.json"
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdss import samples, store
from cdss.followup import get_follow_up_questions

# Prepare sample cases
samples.seed_samples()
case = store.get("sample-d01")
# Simulate previously answered fields
case["fields"]["fever"].update(
    value="no",
    ai="no",
    quote="لا مفيش سخونية",
    filled=True
)

case["fields"]["night_pain"].update(
    value="no",
    ai="no",
    quote="لا يوجد ألم ليلي",
    filled=True
)
# Test 1: Relevant questions only
questions = get_follow_up_questions(case, language="ar")
question_ids = {q["id"] for q in questions}

assert "overhead_activity" not in question_ids
assert "foot_site" not in question_ids

# Test 2: Already answered questions are excluded
assert "fever" not in question_ids
assert "night_pain" not in question_ids

# Test 3: Trauma questions are excluded when injury is unanswered
assert "trauma_mechanism" not in question_ids

# Test 4: Red flags appear first
red_flag_positions = [
    i for i, q in enumerate(questions) if q["red_flag"]
]
normal_positions = [
    i for i, q in enumerate(questions) if not q["red_flag"]
]

if red_flag_positions and normal_positions:
    assert max(red_flag_positions) < min(normal_positions)

# Test 5: English questions are supported
english_questions = get_follow_up_questions(case, language="en")
assert all(q["question"] for q in english_questions)

# Test 6: Invalid language is rejected
try:
    get_follow_up_questions(case, language="fr")
    raise AssertionError("Invalid language should raise ValueError")
except ValueError:
    pass

print("All follow-up tests passed!")
