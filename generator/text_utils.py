import re
import unicodedata
from datetime import datetime

WEEKDAYS_RO = [
    "luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică",
]
MONTHS_RO = [
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]
UNITS_RO = [
    "", "unu", "doi", "trei", "patru", "cinci", "șase", "șapte", "opt", "nouă",
    "zece", "unsprezece", "doisprezece", "treisprezece", "paisprezece",
    "cincisprezece", "șaisprezece", "șaptesprezece", "optsprezece", "nouăsprezece",
]
TENS_RO = [
    "", "", "douăzeci", "treizeci", "patruzeci", "cincizeci",
    "șaizeci", "șaptezeci", "optzeci", "nouăzeci",
]


def format_date_ro(dt: datetime) -> str:
    return f"{WEEKDAYS_RO[dt.weekday()]}, {dt.day} {MONTHS_RO[dt.month - 1]}"


def _two_digits_to_words_ro(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return UNITS_RO[n]
    tens, unit = divmod(n, 10)
    if unit == 0:
        return TENS_RO[tens]
    return f"{TENS_RO[tens]} și {UNITS_RO[unit]}"


def year_to_words_ro(year: int) -> str:
    if year < 2000 or year >= 3000:
        raise ValueError(f"Only years 2000-2999 supported, got {year}")
    remainder = year - 2000
    if remainder == 0:
        return "două mii"
    rest = _two_digits_to_words_ro(remainder)
    return f"două mii {rest}"


def normalize_title_for_dedup(title: str) -> str:
    # Strip diacritics, lowercase, remove punctuation, collapse whitespace.
    nfkd = unicodedata.normalize("NFKD", title)
    no_diacritics = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_diacritics.lower()
    no_punct = re.sub(r"[^\w\s]", " ", lowered)
    collapsed = re.sub(r"\s+", " ", no_punct).strip()
    return collapsed
