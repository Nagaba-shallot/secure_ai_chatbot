from datetime import datetime, timezone

from app.stats import KINDS, build_stats

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def row(kind, detail, day):
    return {"kind": kind, "detail": detail, "created_at": f"{day}T09:30:00+00:00"}


def test_daily_series_covers_every_day_even_with_no_events():
    stats = build_stats([], 7, now=NOW)
    assert [d["date"] for d in stats["daily"]] == [f"2026-11-{n:02d}" for n in range(2, 9)]
    assert all(d[kind] == 0 for d in stats["daily"] for kind in KINDS)
    assert stats["totals"] == {kind: 0 for kind in KINDS} and stats["rules"] == []


def test_counts_group_by_day_and_kind():
    rows = [
        row("input_blocked", "override_instructions", "2026-11-08"),
        row("input_blocked", "reveal_prompt,persona_hijack", "2026-11-08"),
        row("input_masked", "pii_email", "2026-11-07"),
        row("rate_limited", "chat", "2026-11-07"),
    ]
    stats = build_stats(rows, 3, now=NOW)
    assert stats["totals"]["input_blocked"] == 2 and stats["totals"]["input_masked"] == 1
    assert stats["daily"][-1]["input_blocked"] == 2
    assert stats["daily"][-2]["input_masked"] == 1 and stats["daily"][-2]["rate_limited"] == 1


def test_top_triggers_split_comma_lists_and_rank_by_count():
    rows = [
        row("input_blocked", "override_instructions", "2026-11-08"),
        row("input_blocked", "override_instructions,reveal_prompt", "2026-11-08"),
        row("input_masked", "pii_email", "2026-11-08"),
        row("rate_limited", "chat", "2026-11-08"),  # not a rule-based kind, so not a trigger
    ]
    rules = build_stats(rows, 1, now=NOW)["rules"]
    assert rules[0] == {"kind": "input_blocked", "rule": "override_instructions", "count": 2}
    assert {r["rule"] for r in rules} == {"override_instructions", "reveal_prompt", "pii_email"}


def test_events_outside_the_window_and_unknown_kinds_are_ignored():
    rows = [
        row("input_blocked", "x", "2026-10-01"),
        row("mystery", "x", "2026-11-08"),
        row("input_blocked", "x", "2026-11-08"),
    ]
    assert build_stats(rows, 7, now=NOW)["totals"]["input_blocked"] == 1


def test_only_the_ten_most_common_triggers_are_returned():
    rows = [row("input_masked", f"rule_{i}", "2026-11-08") for i in range(15)]
    assert len(build_stats(rows, 1, now=NOW)["rules"]) == 10