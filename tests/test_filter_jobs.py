"""Tests for filter_jobs. No network — every posting here is a fixture."""

from datetime import datetime, timedelta, timezone

import pytest

import main
from main import filter_jobs


def hours_ago(hours):
    """A SmartRecruiters-style timestamp N hours in the past."""
    ts = datetime.now(timezone.utc) - timedelta(hours=hours)
    return ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def posting(name="Praktikum Software", level="internship", hours=1, **extra):
    job = {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "experienceLevel": {"id": level, "label": level.title()},
        "releasedDate": hours_ago(hours),
    }
    job.update(extra)
    return job


def titles(jobs):
    return [j["name"] for j in jobs]


# ── 72h window ──────────────────────────────────────────────────────
def test_posting_inside_window_is_kept():
    assert titles(filter_jobs([posting(hours=71)])) == ["Praktikum Software"]


def test_posting_outside_window_is_dropped():
    assert filter_jobs([posting(hours=73)]) == []


def test_cutoff_boundary_splits_the_batch():
    """The window is the only thing separating these two — same level, same title."""
    jobs = filter_jobs([posting(name="Just inside", hours=71),
                        posting(name="Just outside", hours=73)])
    assert titles(jobs) == ["Just inside"]


def test_window_follows_config():
    """Shrinking hours_window drops a posting that a 72h window would have kept."""
    job = posting(hours=48)
    assert filter_jobs([job]) != []

    original = main.CONFIG["hours_window"]
    main.CONFIG["hours_window"] = 24
    try:
        assert filter_jobs([job]) == []
    finally:
        main.CONFIG["hours_window"] = original


# ── Experience level ────────────────────────────────────────────────
@pytest.mark.parametrize("level", main.CONFIG["experience_levels"])
def test_allowed_levels_are_kept(level):
    assert filter_jobs([posting(level=level)]) != []


@pytest.mark.parametrize("level", ["director", "executive", "mid_senior_level", ""])
def test_senior_levels_are_dropped(level):
    assert filter_jobs([posting(level=level)]) == []


def test_missing_experience_level_is_dropped():
    job = posting()
    del job["experienceLevel"]
    assert filter_jobs([job]) == []


# ── Keywords ────────────────────────────────────────────────────────
def test_empty_keywords_passes_everything_through():
    """Default config: no keywords means no title filtering at all."""
    assert main.CONFIG["keywords"] == []
    jobs = [posting(name="Praktikum Verpackungsentwicklung"),
            posting(name="Werkstudent Supply Chain")]
    assert len(filter_jobs(jobs)) == 2


def test_configured_keywords_match_titles_case_insensitively():
    original = main.CONFIG["keywords"]
    main.CONFIG["keywords"] = ["Software", "embedded"]
    try:
        jobs = filter_jobs([
            posting(name="Praktikum SOFTWARE Engineering"),   # case-insensitive
            posting(name="Embedded Systems Werkstudent"),     # partial match
            posting(name="Praktikum Supply Chain"),           # no keyword
        ])
        assert titles(jobs) == ["Praktikum SOFTWARE Engineering",
                                "Embedded Systems Werkstudent"]
    finally:
        main.CONFIG["keywords"] = original


# ── Bad dates ───────────────────────────────────────────────────────
def test_missing_released_date_is_dropped():
    job = posting()
    del job["releasedDate"]
    assert filter_jobs([job]) == []


def test_empty_released_date_is_dropped():
    assert filter_jobs([posting(releasedDate="")]) == []


@pytest.mark.parametrize("bad", ["not-a-date", "2026-13-45T00:00:00Z", "29/03/2026"])
def test_malformed_released_date_is_skipped_without_killing_the_run(bad):
    """One bad posting must not cost the whole digest."""
    jobs = filter_jobs([posting(name="Broken", releasedDate=bad),
                        posting(name="Fine", hours=2)])
    assert titles(jobs) == ["Fine"]


# ── Ordering ────────────────────────────────────────────────────────
def test_results_are_newest_first():
    jobs = filter_jobs([posting(name="Older", hours=48),
                        posting(name="Newest", hours=1),
                        posting(name="Middle", hours=12)])
    assert titles(jobs) == ["Newest", "Middle", "Older"]


def test_empty_input_returns_empty_list():
    assert filter_jobs([]) == []
