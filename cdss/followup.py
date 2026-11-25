
"""Detect relevant unanswered intake questions for follow-up."""

from .schema import SCHEMA
from .extract import REGION_FOR_SITE


def get_relevant_fields(case):
    """Return only fields relevant to the patient's reported complaint."""

    fields = case.get("fields", {})

    site = fields.get("site", {}).get("value")
    injury = fields.get("injury", {}).get("value")
    also_neck_back = fields.get("also_neck_back", {}).get("value")

    relevant_modules = {"site", "core", "red_flags"}

    # Ask trauma questions only when an injury was reported.
    if injury == "yes":
        relevant_modules.add("trauma")

    # Include the body-region questions matching the reported site.
    for module in REGION_FOR_SITE.get(site, []):
        relevant_modules.add(module)

    if also_neck_back == "yes":
        relevant_modules.add("back")

    result = []

    for spec in SCHEMA:
        if spec["module"] not in relevant_modules:
            continue

        field_data = fields.get(spec["id"], {})
        followup_answers = case.get("followup_answers", {})

        # Skip fields answered by the original extraction or follow-up.
        if field_data.get("filled", False):
            continue

        if spec["id"] in followup_answers:
            continue

        result.append({
            "id": spec["id"],
            "module": spec["module"],
            "question_ar": spec["question_ar"],
            "question_en": spec["question_en"],
            "type": spec["type"],
            "red_flag": spec.get("red_flag", False),
            "options": spec.get("options", [])
        })

    # Red flags first, while preserving the original schema order.
    result.sort(key=lambda item: not item["red_flag"])

    return result


def get_follow_up_questions(case, language="ar"):
    """Return unanswered questions in the requested language."""

    if language not in ("ar", "en"):
        raise ValueError("language must be 'ar' or 'en'")

    questions = get_relevant_fields(case)

    question_key = "question_ar" if language == "ar" else "question_en"

    for question in questions:
        question["question"] = question[question_key]

    return questions
