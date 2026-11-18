"""Unit tests for cron-lens CLI and cron parsing/simulation logic."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from cron_lens.cli import (
    CronSyntaxError,
    explain_cron,
    format_countdown,
    main,
    parse_cron,
)


class TestParseCron:
    def test_wildcards_and_steps(self) -> None:
        sched = parse_cron("*/15 9-18 * * 1-5")
        assert sched.minutes == frozenset({0, 15, 30, 45})
        assert sched.hours == frozenset(range(9, 19))
        assert sched.days_of_month == frozenset(range(1, 32))
        assert sched.months == frozenset(range(1, 13))
        assert sched.days_of_week == frozenset({1, 2, 3, 4, 5})
        assert sched.dom_wildcard is True
        assert sched.dow_wildcard is False

    def test_lists_and_named_months_and_weekdays(self) -> None:
        sched = parse_cron("0,30 8,20 1,15 JAN,JUN,DEC MON-FRI")
        assert sched.minutes == frozenset({0, 30})
        assert sched.hours == frozenset({8, 20})
        assert sched.days_of_month == frozenset({1, 15})
        assert sched.months == frozenset({1, 6, 12})
        assert sched.days_of_week == frozenset({1, 2, 3, 4, 5})

    def test_sunday_as_seven_and_wraparound_range(self) -> None:
        assert parse_cron("0 0 * * 7").days_of_week == frozenset({0})
        assert parse_cron("0 0 * * 5-7").days_of_week == frozenset({5, 6, 0})

    @pytest.mark.parametrize(
        ("preset", "expected_raw"),
        [
            ("@yearly", "0 0 1 1 *"),
            ("@annually", "0 0 1 1 *"),
            ("@monthly", "0 0 1 * *"),
            ("@weekly", "0 0 * * 0"),
            ("@daily", "0 0 * * *"),
            ("@midnight", "0 0 * * *"),
            ("@hourly", "0 * * * *"),
        ],
    )
    def test_presets(self, preset: str, expected_raw: str) -> None:
        sched = parse_cron(preset)
        assert sched.raw == expected_raw


class TestValidationErrors:
    @pytest.mark.parametrize(
        "bad_expr",
        [
            "",
            "   ",
            "* * * *",
            "* * * * * *",
            "60 * * * *",
            "* 24 * * *",
            "* * 0 * *",
            "* * 32 * *",
            "* * * 13 *",
            "* * * * 8",
            "*/0 * * * *",
            "*/-5 * * * *",
            "*/abc * * * *",
            "10-5 * * * *",
            "1,,2 * * * *",
            "foo * * * *",
        ],
    )
    def test_invalid_expressions_raise_syntax_error(self, bad_expr: str) -> None:
        with pytest.raises(CronSyntaxError):
            parse_cron(bad_expr)


class TestSimulationAndMatching:
    def test_next_runs_business_hours(self) -> None:
        sched = parse_cron("*/15 9-18 * * 1-5")
        start = datetime(2026, 1, 15, 9, 1, 0)  # Thursday
        runs = sched.next_runs(count=5, start=start)
        assert runs == [
            datetime(2026, 1, 15, 9, 15),
            datetime(2026, 1, 15, 9, 30),
            datetime(2026, 1, 15, 9, 45),
            datetime(2026, 1, 15, 10, 0),
            datetime(2026, 1, 15, 10, 15),
        ]

    def test_next_runs_skips_weekend_and_rolls_month(self) -> None:
        sched = parse_cron("@monthly")
        start = datetime(2026, 1, 15, 10, 0, 0)
        runs = sched.next_runs(count=3, start=start)
        assert runs == [
            datetime(2026, 2, 1, 0, 0),
            datetime(2026, 3, 1, 0, 0),
            datetime(2026, 4, 1, 0, 0),
        ]

    def test_next_runs_zero_count(self) -> None:
        sched = parse_cron("* * * * *")
        assert sched.next_runs(count=0, start=datetime(2026, 1, 1, 0, 0)) == []

    def test_vixie_or_semantics_when_both_dom_and_dow_restricted(self) -> None:
        # 15th of the month OR Mondays at 09:00
        sched = parse_cron("0 9 15 * 1")
        assert sched.matches(datetime(2026, 1, 15, 9, 0)) is True  # Thu 15th (DOM)
        assert sched.matches(datetime(2026, 1, 12, 9, 0)) is True  # Mon 12th (DOW)
        assert sched.matches(datetime(2026, 1, 13, 9, 0)) is False  # Tue 13th


class TestFormattingAndCLI:
    def test_explain_cron(self) -> None:
        sched = parse_cron("*/15 9-18 * * 1-5")
        assert (
            explain_cron(sched)
            == "Every 15 minutes, from 09:00 through 18:59, Monday through Friday."
        )

    def test_format_countdown(self) -> None:
        assert format_countdown(timedelta(seconds=45)) == "in 45s"
        assert format_countdown(timedelta(minutes=14)) == "in 14m"
        assert format_countdown(timedelta(hours=2, minutes=10)) == "in 2h 10m"
        assert format_countdown(timedelta(days=1, hours=3, minutes=5)) == "in 1d 3h 5m"

    def test_cli_main_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["0 9 * * MON-FRI", "--next", "2", "--from", "2026-01-15T08:00:00"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Expression : 0 9 * * MON-FRI" in out
        assert "2026-01-15 09:00 (Thu)" in out
        assert "2026-01-16 09:00 (Fri)" in out

    def test_cli_main_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["invalid cron"]) == 2
        assert "Error:" in capsys.readouterr().err

        assert main(["@daily", "--next", "-1"]) == 2
        assert "--next must be >= 0" in capsys.readouterr().err

        assert main(["@daily", "--from", "not-a-date"]) == 2
        assert "invalid --from timestamp" in capsys.readouterr().err
