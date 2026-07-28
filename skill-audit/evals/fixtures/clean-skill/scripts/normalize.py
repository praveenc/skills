#!/usr/bin/env python3
"""normalize.py - Convert a currency-rate CSV into a canonical JSON rates table.

Usage:
  normalize.py <input.csv>

Reads a CSV with an exact header `currency,rate` and prints a JSON object
{"base": "USD", "rates": {...}} to stdout. Diagnostics go to stderr.

Exit codes:
  0  Success - JSON printed to stdout
  1  Input error (missing file, bad header, duplicate rows, unparseable rate)
  2  Usage / argument error
"""

import csv
import json
import sys


def err(msg: str) -> None:
    print(msg, file=sys.stderr)


def print_help() -> None:
    print(__doc__)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a not in ("-h", "--help")]
    if len(argv) > 1 and argv[1] in ("-h", "--help"):
        print_help()
        return 0
    if len(args) != 1:
        err("error: exactly one <input.csv> argument is required")
        err("usage: normalize.py <input.csv>")
        return 2

    path = args[0]
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header != ["currency", "rate"]:
                err(f"error: expected header 'currency,rate', got: {header}")
                return 1
            rates: dict[str, float] = {}
            for line_no, row in enumerate(reader, start=2):
                if len(row) != 2:
                    err(f"error: line {line_no}: expected 2 columns, got {len(row)}")
                    return 1
                cur, raw = row[0].strip().upper(), row[1].strip()
                if cur in rates:
                    err(f"error: line {line_no}: duplicate currency {cur}")
                    return 1
                if raw.endswith("%"):
                    err(f"error: line {line_no}: rate must be a ratio, not a percentage: {raw}")
                    return 1
                try:
                    rates[cur] = float(raw)
                except ValueError:
                    err(f"error: line {line_no}: unparseable rate: {raw}")
                    return 1
    except FileNotFoundError:
        err(f"error: no such file: {path}")
        return 1

    print(json.dumps({"base": "USD", "rates": rates}))
    err(f"summary: {len(rates)} rows, currencies={sorted(rates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
