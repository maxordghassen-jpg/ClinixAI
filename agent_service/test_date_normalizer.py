"""
Tests for DateNormalizer.

Covers all four parsing tiers:
  Tier 1 — hardcoded relative keywords (en/fr/ar)
  Tier 2 — already-ISO passthrough
  Tier 3 — European DD/MM/YYYY
  Tier 4 — dateparser fallback (weekday names, relative phrases)

Run:  pytest agent_service/test_date_normalizer.py -v
"""

import re
import sys
import os

# Allow running from repo root or from agent_service/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import pytest
from datetime import datetime, timedelta
from graphs.shared.normalizers.date_normalizer import DateNormalizer

TODAY_ISO = datetime.now().strftime("%Y-%m-%d")
TOMORROW_ISO = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
DAY_AFTER_ISO = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_iso(value: str) -> bool:
    return bool(_ISO_RE.match(value))


def days_from_now(iso: str) -> int:
    d = datetime.strptime(iso, "%Y-%m-%d")
    return (d - datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).days


# ── Tier 1: hardcoded relative keywords ──────────────────────────────────────

class TestRelativeKeywords:

    def test_today_english(self):
        assert DateNormalizer.normalize("today") == TODAY_ISO

    def test_today_case_insensitive(self):
        assert DateNormalizer.normalize("Today") == TODAY_ISO
        assert DateNormalizer.normalize("TODAY") == TODAY_ISO

    def test_tomorrow_english(self):
        assert DateNormalizer.normalize("tomorrow") == TOMORROW_ISO

    def test_tomorrow_with_whitespace(self):
        assert DateNormalizer.normalize("  tomorrow  ") == TOMORROW_ISO

    def test_day_after_tomorrow_english(self):
        assert DateNormalizer.normalize("the day after tomorrow") == DAY_AFTER_ISO

    def test_today_french(self):
        assert DateNormalizer.normalize("aujourd'hui") == TODAY_ISO

    def test_tomorrow_french(self):
        assert DateNormalizer.normalize("demain") == TOMORROW_ISO

    def test_day_after_tomorrow_french(self):
        assert DateNormalizer.normalize("après-demain") == DAY_AFTER_ISO

    def test_day_after_tomorrow_french_no_accent(self):
        assert DateNormalizer.normalize("apres-demain") == DAY_AFTER_ISO

    def test_today_arabic(self):
        assert DateNormalizer.normalize("اليوم") == TODAY_ISO

    def test_tomorrow_arabic(self):
        assert DateNormalizer.normalize("غدا") == TOMORROW_ISO

    def test_tomorrow_arabic_with_alef_maqsura(self):
        assert DateNormalizer.normalize("غداً") == TOMORROW_ISO

    def test_day_after_tomorrow_arabic(self):
        assert DateNormalizer.normalize("بعد غد") == DAY_AFTER_ISO

    def test_day_after_tomorrow_arabic_variant(self):
        assert DateNormalizer.normalize("بعد غداً") == DAY_AFTER_ISO


# ── Tier 2: already-ISO passthrough ──────────────────────────────────────────

class TestISOPassthrough:

    def test_iso_passthrough(self):
        assert DateNormalizer.normalize("2026-12-25") == "2026-12-25"

    def test_iso_passthrough_past_date(self):
        # Past ISO dates pass through unchanged (caller may validate separately)
        assert DateNormalizer.normalize("2020-01-01") == "2020-01-01"

    def test_iso_passthrough_leading_zeros(self):
        assert DateNormalizer.normalize("2026-01-05") == "2026-01-05"


# ── Tier 3: European DD/MM/YYYY ───────────────────────────────────────────────

class TestEuropeanFormat:

    def test_eu_slash_format(self):
        assert DateNormalizer.normalize("25/12/2026") == "2026-12-25"

    def test_eu_dash_format(self):
        assert DateNormalizer.normalize("25-12-2026") == "2026-12-25"

    def test_eu_single_digit_day_month(self):
        assert DateNormalizer.normalize("5/1/2026") == "2026-01-05"

    def test_eu_mixed_single_double_digit(self):
        assert DateNormalizer.normalize("9/11/2026") == "2026-11-09"


# ── Tier 4: dateparser fallback ───────────────────────────────────────────────

class TestDateparserFallback:

    def test_next_monday_english(self):
        result = DateNormalizer.normalize("next monday")
        assert is_iso(result)
        delta = days_from_now(result)
        assert 1 <= delta <= 7, f"Expected within 7 days, got delta={delta}"

    def test_friday_english(self):
        result = DateNormalizer.normalize("friday")
        assert is_iso(result)
        delta = days_from_now(result)
        # dateparser with PREFER_DATES_FROM=future gives the next Friday
        assert 0 <= delta <= 7, f"Expected next Friday (0-7 days), got delta={delta}"

    def test_vendredi_prochain_french(self):
        result = DateNormalizer.normalize("vendredi prochain")
        assert is_iso(result)
        delta = days_from_now(result)
        assert 1 <= delta <= 7, f"Expected within 7 days, got delta={delta}"

    def test_vendredi_french(self):
        result = DateNormalizer.normalize("vendredi")
        assert is_iso(result)
        delta = days_from_now(result)
        assert 0 <= delta <= 7

    def test_arabic_friday(self):
        result = DateNormalizer.normalize("الجمعة")
        assert is_iso(result)
        delta = days_from_now(result)
        assert 0 <= delta <= 7, f"Expected next Friday, got delta={delta}"

    def test_next_week_english(self):
        result = DateNormalizer.normalize("next week")
        assert is_iso(result)
        delta = days_from_now(result)
        assert 1 <= delta <= 14


# ── Invalid input ─────────────────────────────────────────────────────────────

class TestInvalidInput:

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            DateNormalizer.normalize("")

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            DateNormalizer.normalize("xyzzy not a date")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            DateNormalizer.normalize("   ")
