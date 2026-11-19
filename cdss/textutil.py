import re

_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def normalize_arabic(text):
    t = _DIAC.sub("", str(text))
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    t = t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def safe_id(name):
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", str(name)).strip("-")
    return s[:60] or "case"
