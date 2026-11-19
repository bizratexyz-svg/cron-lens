# cron-lens

**English** | [日本語](README.ja.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A zero-dependency Python CLI tool to inspect, validate, explain, and simulate standard 5-field cron expressions.

## Features

- **Pure Python stdlib** — no third-party dependencies.
- **Human-readable explanations** — translates cron syntax into plain English.
- **Helpful syntax validation** — pinpoints out-of-range values, bad steps, and malformed fields.
- **Execution simulation** — lists the next `N` run timestamps with relative countdowns (e.g. `in 14m`, `in 2h 10m`).
- **Supports standard syntax** — wildcards (`*`), steps (`*/15`), ranges (`9-18`), lists (`1,15`), month/weekday names (`JAN`, `MON-FRI`), and presets (`@daily`, `@hourly`, etc.).

## Installation

Using [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install .
```

Or run directly without installing:

```bash
uv run cron-lens "*/15 9-18 * * 1-5"
```

## Usage

```bash
# Explain and simulate the next 10 runs (default)
cron-lens "*/15 9-18 * * 1-5"

# Simulate the next 5 runs
cron-lens "0 9 * * MON-FRI" --next 5

# Simulate from a specific reference timestamp
cron-lens "@monthly" --next 3 --from 2026-01-15T10:00:00
```

## Example Output

```text
Expression : */15 9-18 * * 1-5
Meaning    : Every 15 minutes, from 09:00 through 18:59, Monday through Friday.

Next 5 runs (from 2026-01-15 09:01:00):
   1. 2026-01-15 09:15 (Thu)  (in 14m)
   2. 2026-01-15 09:30 (Thu)  (in 29m)
   3. 2026-01-15 09:45 (Thu)  (in 44m)
   4. 2026-01-15 10:00 (Thu)  (in 59m)
   5. 2026-01-15 10:15 (Thu)  (in 1h 14m)
```

## License

MIT
