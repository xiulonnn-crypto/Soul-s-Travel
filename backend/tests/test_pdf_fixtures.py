"""End-to-end 100%-match acceptance tests for historical travel PDFs.

Each fixture in backend/tests/fixtures/pdf_ground_truth/*.json declares the
ground-truth values extracted by hand from the corresponding PDF. This test
module loads the real PDF, runs it through the production extract→parse
pipeline, and asserts:

- trip header fields (title substring, dates, day_count) strict match
- per-leg {city, country, day_count} set match (order-insensitive)
- expense total CNY / count / per-day CNY strict numeric match (±0.01 tol)
- required_attractions: every keyword MUST appear in any day.activities entry
- required_accommodations: every keyword MUST appear in any day.accommodation
  OR any expense.description

Known drifts (`known_drifts`) are documented in the fixture and NOT asserted
— they represent gaps acknowledged to require ai_parser.py changes (out of
this iteration's extract-layer-only scope).

If the source PDF is not on disk, the test skips — keeps CI portable.
"""
import json
import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.ai_parser import parse_text
from services.file_extractor import extract_text_from_pdf

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdf_ground_truth"
PDF_SEARCH_DIRS = [
    Path(os.path.expanduser("~/Downloads")),
]

FIXTURES = sorted(FIXTURE_DIR.glob("*.json"))


def _locate_pdf(filename):
    for d in PDF_SEARCH_DIRS:
        p = d / filename
        if p.exists():
            return p
    return None


def _load_fixture(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _parse_pdf(pdf_path):
    with open(pdf_path, "rb") as f:
        text = extract_text_from_pdf(f.read())
    return parse_text(text)


def _collect_activities(result):
    out = []
    for leg in result.get("legs", []):
        for d in leg.get("days", []):
            out.extend(d.get("activities") or [])
    return out


def _collect_accommodation_strings(result):
    out = []
    for leg in result.get("legs", []):
        for d in leg.get("days", []):
            acc = d.get("accommodation")
            if acc:
                out.append(acc)
    for exp in result.get("expenses", []):
        desc = exp.get("description")
        if desc:
            out.append(desc)
    return out


def _approx_eq(a, b, tol=0.01):
    return a is not None and b is not None and math.isclose(a, b, abs_tol=tol)


@pytest.fixture(scope="module", params=FIXTURES, ids=lambda p: p.stem)
def fixture(request):
    return _load_fixture(request.param)


@pytest.fixture(scope="module")
def parsed(fixture):
    pdf = _locate_pdf(fixture["pdf_filename"])
    if pdf is None:
        pytest.skip(f"PDF {fixture['pdf_filename']} not found in search dirs")
    return _parse_pdf(pdf)


class TestTripHeader:
    def test_title_contains(self, fixture, parsed):
        keyword = fixture["trip"]["title_contains"]
        title = parsed["trip"]["title"] or ""
        assert keyword in title, f"title={title!r} missing keyword {keyword!r}"

    def test_start_date(self, fixture, parsed):
        assert parsed["trip"]["start_date"] == fixture["trip"]["start_date"]

    def test_end_date(self, fixture, parsed):
        assert parsed["trip"]["end_date"] == fixture["trip"]["end_date"]

    def test_day_count(self, fixture, parsed):
        all_days = [d for leg in parsed["legs"] for d in leg["days"]]
        expected = fixture["trip"]["day_count"]
        assert len(all_days) == expected, (
            f"期望 {expected} 天，实际 {len(all_days)}；dates="
            f"{[d['date'] for d in all_days]}"
        )


class TestLegs:
    def test_leg_cities_present(self, fixture, parsed):
        expected_cities = {L["city"] for L in fixture["legs"]}
        actual_cities = {L["city"] for L in parsed["legs"]}
        missing = expected_cities - actual_cities
        assert not missing, f"缺少 legs: {missing}；实际 legs={actual_cities}"

    def test_leg_country_mapping(self, fixture, parsed):
        expected = {L["city"]: L["country"] for L in fixture["legs"]}
        actual = {L["city"]: L["country"] for L in parsed["legs"]}
        for city, country in expected.items():
            if city in actual:
                assert actual[city] == country, (
                    f"{city} 国家映射错：期望 {country}，实际 {actual[city]}"
                )

    def test_leg_day_counts(self, fixture, parsed):
        expected = {L["city"]: L["day_count"] for L in fixture["legs"]}
        actual = {L["city"]: len(L["days"]) for L in parsed["legs"]}
        for city, n in expected.items():
            if city in actual:
                assert actual[city] == n, (
                    f"{city} leg day_count 期望 {n}，实际 {actual[city]}"
                )


class TestExpenses:
    def test_total_cny(self, fixture, parsed):
        total = sum(e["amount"] for e in parsed["expenses"] if e["currency"] == "CNY")
        expected = fixture["expenses"]["total_cny"]
        assert _approx_eq(total, expected), (
            f"CNY 总额 期望 {expected}，实际 {round(total,2)}"
        )

    def test_count(self, fixture, parsed):
        assert len(parsed["expenses"]) == fixture["expenses"]["count"]

    def test_per_day_cny(self, fixture, parsed):
        per_day_actual = {}
        for e in parsed["expenses"]:
            if e["currency"] != "CNY":
                continue
            per_day_actual.setdefault(e["date"], 0.0)
            per_day_actual[e["date"]] += e["amount"]
        for date, expected in fixture["expenses"]["per_day_cny"].items():
            actual = per_day_actual.get(date)
            assert actual is not None and _approx_eq(actual, expected), (
                f"{date} CNY 合计 期望 {expected}，实际 {actual}"
            )


class TestAttractions:
    def test_required_attractions_present(self, fixture, parsed):
        required = fixture.get("required_attractions") or []
        if not required:
            pytest.skip("no required_attractions declared")
        actual = _collect_activities(parsed)
        missing = []
        for kw in required:
            if not any(kw in a for a in actual):
                missing.append(kw)
        assert not missing, (
            f"缺失景点关键词: {missing}\n实际景点列表: {actual}"
        )


class TestAccommodations:
    def test_required_accommodations_present(self, fixture, parsed):
        required = fixture.get("required_accommodations") or []
        if not required:
            pytest.skip("no required_accommodations declared")
        actual = _collect_accommodation_strings(parsed)
        missing = []
        for kw in required:
            if not any(kw in a for a in actual):
                missing.append(kw)
        assert not missing, (
            f"缺失住宿关键词: {missing}\n实际住宿/费用描述列表: {actual}"
        )
