# cron-lens

[English](README.md) | **日本語**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

標準的な5フィールドの cron 式を検査・検証・解説・シミュレーションする、外部依存ゼロの Python CLI ツールです。

## 主な機能

- **Python 標準ライブラリのみ** — サードパーティ製の依存パッケージ不要。
- **分かりやすい解説** — cron 構文を人間が読みやすい英語の説明文に変換。
- **親切な構文バリデーション** — 範囲外の値、不正なステップ指定、フォーマット誤りなどを的確に指摘。
- **実行シミュレーション** — 次回以降 `N` 回分の実行日時を相対カウントダウン（例: `in 14m`, `in 2h 10m`）付きで一覧表示。
- **標準構文に幅広く対応** — ワイルドカード（`*`）、ステップ（`*/15`）、範囲（`9-18`）、リスト（`1,15`）、月・曜日名（`JAN`, `MON-FRI`）、プリセット（`@daily`, `@hourly` など）をサポート。

## インストール

[`uv`](https://docs.astral.sh/uv/) を使用する場合:

```bash
uv tool install .
```

インストールせずに直接実行する場合:

```bash
uv run cron-lens "*/15 9-18 * * 1-5"
```

## 使い方

```bash
# cron 式の解説と次回以降 10 回分（デフォルト）の実行をシミュレーション
cron-lens "*/15 9-18 * * 1-5"

# 次回以降 5 回分の実行をシミュレーション
cron-lens "0 9 * * MON-FRI" --next 5

# 指定した基準日時からシミュレーション
cron-lens "@monthly" --next 3 --from 2026-01-15T10:00:00
```

## 出力例

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

## ライセンス

MIT
