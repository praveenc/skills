---
name: clean-skill
description: >
  Convert a CSV file of exchange rates into a normalized JSON rates table.
  Use when the user asks to "normalize exchange rates", "convert the rates CSV",
  "build a rates table from CSV", or hands over a currency-rate CSV and wants
  JSON out. Do NOT use for generic CSV-to-JSON conversion, for parsing
  non-currency data, or for live rate fetching from an API — those are out of scope.
compatibility: >
  Requires bash and python3. Read-only against the input CSV; writes one JSON
  file to the path the user specifies.
---

# Clean Skill (fixture: well-formed)

Normalize a currency-rate CSV into a canonical JSON rates table.

## Workflow

1. Run the converter, which validates columns and emits JSON to stdout:

   ```bash
   python3 <skill-dir>/scripts/normalize.py <input.csv>
   ```

2. Review the JSON summary line printed to stderr (row count, currencies seen).
3. If the script exits non-zero, read the stderr message and fix the input — do
   not hand-edit the JSON.

## Output

The script prints a JSON object: `{"base": "USD", "rates": {"EUR": 0.92, ...}}`.

## Gotchas

- The converter rejects CSVs whose header is not exactly `currency,rate` — this
  is intentional; a mismatched header usually means the wrong file was passed.
- Rates are parsed as floats; scientific notation (`1e-3`) is accepted but a
  trailing `%` is rejected, because rate columns are ratios, not percentages.
- Duplicate currency rows fail fast rather than silently taking the last value.
