"""The question template and the extraction prompt."""
import json
from . import config

YN = ["yes", "no"]


def _starter():
    def f(i, m, en, ar, t, o=None, rf=False):
        d = dict(id=i, module=m, question_en=en, question_ar=ar, type=t, red_flag=rf)
        if o:
            d["options"] = o
        return d
    return [
        f("site", "site", "Where is the problem?", "فين المشكلة؟", "enum", ["neck", "shoulder", "elbow", "wrist_hand", "back", "hip", "knee", "ankle_foot"]),
        f("side", "site", "Which side?", "الناحية الشمال ولا اليمين؟", "enum", ["right", "left", "both"]),
        f("onset", "core", "When did it start?", "بدأت من إمتى؟", "text"),
        f("onset_type", "core", "Sudden or gradual?", "فجأة ولا واحدة واحدة؟", "enum", ["sudden", "gradual"]),
        f("injury", "core", "Was there an injury?", "كان فيه إصابة أو وقعة؟", "enum", YN),
        f("pain_severity", "core", "Pain from 0 to 10?", "الوجع كام من صفر لعشرة؟", "number"),
        f("character", "core", "What does the pain feel like?", "الوجع شكله إيه؟", "text"),
        f("radiation", "core", "Does the pain spread elsewhere?", "الوجع بيروح مكان تاني؟", "enum", YN),
        f("worse_with", "core", "What makes it worse?", "إيه اللي بيزوّده؟", "text"),
        f("better_with", "core", "What makes it better?", "إيه اللي بيخففه؟", "text"),
        f("night_pain", "core", "Does pain wake you at night?", "الوجع بيصحيك بالليل؟", "enum", YN),
        f("morning_stiffness_min", "core", "Morning stiffness, in minutes?", "الصبح بتتيبّس كام دقيقة؟", "number"),
        f("swelling", "core", "Any swelling?", "فيه ورم؟", "enum", YN),
        f("numbness", "core", "Numbness or tingling?", "فيه تنميل؟", "enum", YN),
        f("weakness", "core", "Any weakness?", "فيه ضعف؟", "enum", YN),
        f("prior_treatment", "core", "Treatment tried so far?", "جربت أي علاج لحد دلوقتي؟", "text"),
        f("diabetes", "core", "Diabetes?", "عندك سكر؟", "enum", YN),
        f("trauma_mechanism", "trauma", "How did the injury happen?", "الإصابة حصلت إزاي؟", "text"),
        f("can_bear_weight", "trauma", "Could you put weight on it right after?", "قدرت تقف عليها بعد الإصابة؟", "enum", YN),
        f("fever", "red_flags", "Fever?", "فيه سخونية؟", "enum", YN, True),
        f("weight_loss", "red_flags", "Unexplained weight loss?", "وزنك نزل من غير سبب؟", "enum", YN, True),
        f("cancer_history", "red_flags", "History of cancer?", "عندك تاريخ مرضي بالسرطان؟", "enum", YN, True),
        f("bladder_bowel", "red_flags", "Bladder or bowel change?", "فيه تغيير في التبول أو الإخراج؟", "enum", YN, True),
        f("giving_way", "knee", "Does the knee give way?", "الركبة بتخونك وانت ماشي؟", "enum", YN),
    ]


def load_schema():
    if config.SCHEMA_PATH.exists():
        s = json.loads(config.SCHEMA_PATH.read_text(encoding="utf-8"))
    else:
        s = _starter()
        config.SCHEMA_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    for x in s:
        x.setdefault("red_flag", False)
    return s


SCHEMA = load_schema()
BY_ID = {f["id"]: f for f in SCHEMA}
RED_FLAG_IDS = [f["id"] for f in SCHEMA if f["red_flag"]]
MODULE_TITLES = {"site": "Site", "core": "History of the problem", "trauma": "Injury", "knee": "Knee",
                 "neck": "Neck", "shoulder": "Shoulder", "elbow": "Elbow", "wrist_hand": "Wrist and hand",
                 "back": "Back", "hip": "Hip", "ankle_foot": "Ankle and foot"}

SYSTEM_PROMPT = """You fill a structured pre-consultation history form for an orthopedic clinic from the transcript of a conversation between an intake assistant and an Egyptian Arabic-speaking patient.

Rules:
1. The transcript has no speaker labels. The assistant's questions and the patient's answers are mixed together. Use only what the PATIENT states. A question in the transcript is not an answer.
2. Fill a field only if the patient clearly answered it. If it was not asked, or the answer is unclear, leave the field out. Never guess and never infer.
3. For every field you fill, give evidence_quote: the patient's own words, copied exactly from the transcript (a short span, in the original Arabic). Do not translate or correct the quote.
4. For enum fields use exactly one of the allowed values, written in English as listed (for yes/no fields write yes or no, never نعم or لا). If the patient's answer does not clearly match an allowed value, leave the field out. For number fields give a number. For text fields give a short phrase in the patient's own Arabic words, copied from the transcript.
5. Do not give any diagnosis, treatment advice, dose, score or probability.
6. Do not use any tools, do not read or write files, and do not add commentary. Reply with only the JSON object, in this shape:
{"fields": {"<field_id>": {"value": <value>, "evidence_quote": "<exact words from the transcript>"}}}"""

EXAMPLE = """Example transcript: كتفي الشمال بيوجعني من أسبوعين. فيه سخونية؟ لأ، مفيش سخونية. بتاخد حاجة للوجع؟ آه بتاخد مسكن.
Example output: {"fields": {"site": {"value": "shoulder", "evidence_quote": "كتفي"}, "side": {"value": "left", "evidence_quote": "الشمال"}, "onset": {"value": "من أسبوعين", "evidence_quote": "من أسبوعين"}, "fever": {"value": "no", "evidence_quote": "مفيش سخونية"}, "prior_treatment": {"value": "بتاخد مسكن", "evidence_quote": "بتاخد مسكن"}}}
Note that the example leaves out every field the patient did not address (pain score, swelling, and so on)."""


def schema_for_prompt(fields=None):
    out = []
    for f in (SCHEMA if fields is None else fields):
        opt = f" allowed: {f['options']}" if f["type"] == "enum" else ""
        rf = " [red flag]" if f["red_flag"] else ""
        out.append(f"- {f['id']} ({f['type']}){opt}{rf}: {f['question_en']}")
    return "\n".join(out)


def build_user_prompt(transcript, fields=None):
    note = ("This list is only one part of the form. The conversation may not cover some or all of these fields. "
            "Fill a field only if the assistant asked about it and the patient answered. "
            "For a red-flag field write no only if the patient's own words deny it. If nothing here was discussed, return {\"fields\": {}}.")
    return f"Form fields:\n{schema_for_prompt(fields)}\n\n{note}\n\n{EXAMPLE}\n\nTranscript:\n{transcript}\n\nReturn the JSON now."
