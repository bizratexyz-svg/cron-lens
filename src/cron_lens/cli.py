"""CLI and pure-stdlib 5-field cron expression parser, explainer, and simulator."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from . import __version__

MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

MONTH_LABELS = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

DOW_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}

DOW_LABELS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]

PRESETS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


class CronSyntaxError(ValueError):
    """Raised when a cron expression is invalid."""


@dataclass(frozen=True)
class CronSchedule:
    """Parsed 5-field cron schedule."""

    raw: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    dom_wildcard: bool
    dow_wildcard: bool

    def matches(self, dt: datetime) -> bool:
        """Return True if *dt* matches this cron schedule."""
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False

        # Python weekday(): Monday=0..Sunday=6 -> Cron: Sunday=0..Saturday=6
        cron_dow = (dt.weekday() + 1) % 7
        dom_match = dt.day in self.days_of_month
        dow_match = cron_dow in self.days_of_week

        # Standard Vixie cron semantics: if both DOM and DOW are restricted,
        # match when EITHER matches; otherwise both must match.
        if not self.dom_wildcard and not self.dow_wildcard:
            return dom_match or dow_match
        return dom_match and dow_match

    def next_runs(self, count: int = 10, start: datetime | None = None) -> list[datetime]:
        """Simulate the next *count* execution timestamps strictly after *start*."""
        if count <= 0:
            return []

        now = start or datetime.now()
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = candidate + timedelta(days=366 * 8)
        results: list[datetime] = []

        while len(results) < count and candidate <= limit:
            if candidate.month not in self.months:
                # Jump to the first day of the next month
                if candidate.month == 12:
                    candidate = candidate.replace(
                        year=candidate.year + 1, month=1, day=1, hour=0, minute=0
                    )
                else:
                    candidate = candidate.replace(
                        month=candidate.month + 1, day=1, hour=0, minute=0
                    )
                continue

            cron_dow = (candidate.weekday() + 1) % 7
            dom_match = candidate.day in self.days_of_month
            dow_match = cron_dow in self.days_of_week
            day_ok = (
                (dom_match or dow_match)
                if (not self.dom_wildcard and not self.dow_wildcard)
                else (dom_match and dow_match)
            )
            if not day_ok:
                candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
                continue

            if candidate.hour not in self.hours:
                candidate = (candidate + timedelta(hours=1)).replace(minute=0)
                continue

            if candidate.minute in self.minutes:
                results.append(candidate)

            candidate += timedelta(minutes=1)

        return results


def _replace_names(token: str, mapping: dict[str, int]) -> str:
    upper = token.upper()
    for name, value in mapping.items():
        upper = upper.replace(name, str(value))
    return upper


def _parse_int(value: str, field_name: str, min_val: int, max_val: int, allow_7_as_0: bool = False) -> int:
    try:
        num = int(value)
    except ValueError as exc:
        raise CronSyntaxError(
            f"Invalid integer '{value}' in {field_name} field (expected {min_val}-{max_val})."
        ) from exc

    if allow_7_as_0 and num == 7:
        return 0
    if num < min_val or num > max_val:
        raise CronSyntaxError(
            f"Value {num} out of range in {field_name} field (allowed: {min_val}-{max_val})."
        )
    return num


def _parse_field(
    expr: str,
    field_name: str,
    min_val: int,
    max_val: int,
    names: dict[str, int] | None = None,
    allow_7_as_0: bool = False,
) -> tuple[frozenset[int], bool]:
    if not expr:
        raise CronSyntaxError(f"Empty {field_name} field.")

    is_wildcard = expr == "*"
    normalized = _replace_names(expr, names) if names else expr
    values: set[int] = set()

    for part in normalized.split(","):
        if not part:
            raise CronSyntaxError(f"Empty list item in {field_name} field: '{expr}'.")

        step = 1
        if "/" in part:
            pieces = part.split("/")
            if len(pieces) != 2 or not pieces[1]:
                raise CronSyntaxError(f"Invalid step syntax '{part}' in {field_name} field.")
            base, step_str = pieces
            try:
                step = int(step_str)
            except ValueError as exc:
                raise CronSyntaxError(
                    f"Invalid step '{step_str}' in {field_name} field (must be a positive integer)."
                ) from exc
            if step <= 0:
                raise CronSyntaxError(
                    f"Step must be >= 1 in {field_name} field, got {step}."
                )
        else:
            base = part

        if base == "*":
            start, end = min_val, max_val
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2 or not bounds[0] or not bounds[1]:
                raise CronSyntaxError(f"Invalid range '{base}' in {field_name} field.")
            start = _parse_int(bounds[0], field_name, min_val, max_val, allow_7_as_0)
            end = _parse_int(bounds[1], field_name, min_val, max_val, allow_7_as_0)
            if allow_7_as_0 and bounds[1] == "7" and start > 0:
                # Allow ranges like 5-7 (Fri-Sun) -> 5, 6, 0
                values.update(v % 7 for v in range(start, 8, step))
                continue
            if start > end:
                raise CronSyntaxError(
                    f"Range start ({start}) exceeds end ({end}) in {field_name} field: '{part}'."
                )
        else:
            start = _parse_int(base, field_name, min_val, max_val, allow_7_as_0)
            end = max_val if "/" in part else start

        values.update(range(start, end + 1, step))

    if not values:
        raise CronSyntaxError(f"No valid values parsed for {field_name} field: '{expr}'.")

    return frozenset(values), is_wildcard


def parse_cron(expression: str) -> CronSchedule:
    """Parse and validate a standard 5-field cron expression (or @preset)."""
    cleaned = expression.strip()
    if not cleaned:
        raise CronSyntaxError("Cron expression cannot be empty.")

    if cleaned.lower() in PRESETS:
        cleaned = PRESETS[cleaned.lower()]

    fields = cleaned.split()
    if len(fields) != 5:
        raise CronSyntaxError(
            f"Expected 5 space-separated fields (minute hour day-of-month month day-of-week), "
            f"got {len(fields)}: '{expression}'."
        )

    min_f, hour_f, dom_f, mon_f, dow_f = fields
    minutes, _ = _parse_field(min_f, "minute", 0, 59)
    hours, _ = _parse_field(hour_f, "hour", 0, 23)
    doms, dom_wild = _parse_field(dom_f, "day-of-month", 1, 31)
    months, _ = _parse_field(mon_f, "month", 1, 12, names=MONTH_NAMES)
    dows, dow_wild = _parse_field(dow_f, "day-of-week", 0, 6, names=DOW_NAMES, allow_7_as_0=True)

    return CronSchedule(
        raw=cleaned,
        minutes=minutes,
        hours=hours,
        days_of_month=doms,
        months=months,
        days_of_week=dows,
        dom_wildcard=dom_wild,
        dow_wildcard=dow_wild,
    )


def _format_list(items: Iterable[str]) -> str:
    seq = list(items)
    if not seq:
        return ""
    if len(seq) == 1:
        return seq[0]
    if len(seq) == 2:
        return f"{seq[0]} and {seq[1]}"
    return ", ".join(seq[:-1]) + f", and {seq[-1]}"


def _describe_time(min_f: str, hour_f: str, minutes: frozenset[int], hours: frozenset[int]) -> str:
    if min_f == "*" and hour_f == "*":
        return "Every minute"
    if min_f.startswith("*/") and hour_f == "*":
        return f"Every {min_f[2:]} minutes"
    if len(minutes) == 1 and len(hours) == 1:
        m = next(iter(minutes))
        h = next(iter(hours))
        return f"At {h:02d}:{m:02d}"

    parts: list[str] = []
    if min_f == "*":
        parts.append("Every minute")
    elif min_f.startswith("*/"):
        parts.append(f"Every {min_f[2:]} minutes")
    else:
        sorted_m = sorted(minutes)
        parts.append(f"At minute {_format_list(str(m) for m in sorted_m)}")

    if hour_f != "*":
        if hour_f.startswith("*/"):
            parts.append(f"every {hour_f[2:]} hours")
        elif "-" in hour_f and "," not in hour_f and "/" not in hour_f:
            start_h, end_h = hour_f.split("-")
            parts.append(f"from {int(start_h):02d}:00 through {int(end_h):02d}:59")
        else:
            sorted_h = sorted(hours)
            parts.append(f"past hour {_format_list(f'{h:02d}' for h in sorted_h)}")

    return ", ".join(parts)


def explain_cron(schedule: CronSchedule) -> str:
    """Return a concise human-readable explanation of *schedule*."""
    min_f, hour_f, dom_f, mon_f, dow_f = schedule.raw.split()
    segments = [_describe_time(min_f, hour_f, schedule.minutes, schedule.hours)]

    if not schedule.dom_wildcard:
        if dom_f.startswith("*/"):
            segments.append(f"every {dom_f[2:]} days")
        else:
            sorted_d = sorted(schedule.days_of_month)
            segments.append(f"on day {_format_list(str(d) for d in sorted_d)} of the month")

    if not schedule.dow_wildcard:
        sorted_dow = sorted(schedule.days_of_week)
        if sorted_dow == [1, 2, 3, 4, 5]:
            segments.append("Monday through Friday")
        elif sorted_dow == [0, 6]:
            segments.append("on weekends (Saturday and Sunday)")
        else:
            segments.append(f"on {_format_list(DOW_LABELS[d] for d in sorted_dow)}")

    if mon_f != "*":
        sorted_mon = sorted(schedule.months)
        segments.append(f"in {_format_list(MONTH_LABELS[m] for m in sorted_mon)}")

    return ", ".join(segments) + "."


def format_countdown(delta: timedelta) -> str:
    """Format a positive timedelta as a compact relative countdown like 'in 2h 10m'."""
    total_seconds = max(0, int(delta.total_seconds()))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return "in " + " ".join(parts[:3])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cron-lens",
        description="Inspect, validate, explain, and simulate 5-field cron expressions.",
        epilog="Examples:\n  cron-lens '*/15 9-18 * * 1-5'\n  cron-lens '0 0 1 * *' --next 5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "expression",
        help="5-field cron expression (e.g. '*/15 9-18 * * 1-5') or preset (e.g. '@daily').",
    )
    parser.add_argument(
        "-n",
        "--next",
        type=int,
        default=10,
        metavar="N",
        help="Number of upcoming execution timestamps to simulate (default: 10).",
    )
    parser.add_argument(
        "--from",
        dest="start_from",
        metavar="ISO_DATETIME",
        help="Optional reference start timestamp (ISO 8601, e.g. '2026-01-01T08:00:00').",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        schedule = parse_cron(args.expression)
    except CronSyntaxError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    if args.next < 0:
        print("Error: --next must be >= 0.", file=sys.stderr)
        return 2

    now = datetime.now()
    if args.start_from:
        try:
            now = datetime.fromisoformat(args.start_from)
        except ValueError as err:
            print(f"Error: invalid --from timestamp '{args.start_from}': {err}", file=sys.stderr)
            return 2

    print(f"Expression : {schedule.raw}")
    print(f"Meaning    : {explain_cron(schedule)}")

    if args.next > 0:
        runs = schedule.next_runs(count=args.next, start=now)
        print(f"\nNext {len(runs)} runs (from {now.strftime('%Y-%m-%d %H:%M:%S')}):")
        for idx, run in enumerate(runs, start=1):
            countdown = format_countdown(run - now)
            print(f"  {idx:>2}. {run.strftime('%Y-%m-%d %H:%M (%a)')}  ({countdown})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
