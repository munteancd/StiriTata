from datetime import datetime

from generator.text_utils import (
    format_date_ro,
    year_to_words_ro,
    normalize_title_for_dedup,
)


def test_format_date_ro_weekend():
    # 2026-04-19 is a Sunday
    assert format_date_ro(datetime(2026, 4, 19)) == "duminică, 19 aprilie"


def test_format_date_ro_weekday():
    # 2026-04-20 is a Monday
    assert format_date_ro(datetime(2026, 4, 20)) == "luni, 20 aprilie"


def test_year_to_words_ro_2026():
    assert year_to_words_ro(2026) == "două mii douăzeci și șase"


def test_year_to_words_ro_2000():
    assert year_to_words_ro(2000) == "două mii"


def test_year_to_words_ro_2010():
    assert year_to_words_ro(2010) == "două mii zece"


def test_normalize_title_strips_punctuation_and_lowercases():
    assert normalize_title_for_dedup("  Guvernul, adoptă Măsuri! ") == "guvernul adopta masuri"


def test_normalize_title_dedups_despite_diacritic_difference():
    a = normalize_title_for_dedup("Președintele Iohannis a declarat")
    b = normalize_title_for_dedup("Presedintele Iohannis a declarat")
    assert a == b
