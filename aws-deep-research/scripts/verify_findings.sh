#!/usr/bin/env bash
# verify_findings.sh - silent-failure detector for a research work dir.
#
# Subagents occasionally report success while writing an empty or stub findings
# file (script crash mid-write, missing API key, blocked domain). This script
# classifies every findings file in a work dir by SIZE ONLY so the parent agent
# can surface degraded sources without reading any findings content into its
# own context.
#
# It never prints file contents - only names, sizes, and a status.
#
# Usage:
#   verify_findings.sh <work-dir> [--expect <name.md>]... [--min-bytes N] [--json]
#
#   <work-dir>       $WORK_DIR/<slug>/ - the session work directory
#   --expect NAME    a findings file the parent dispatched a subagent for.
#                    Repeatable. An expected file that is absent reports MISSING.
#                    With no --expect, whatever *.md is present is classified.
#   --min-bytes N    WEAK threshold (default 500)
#   --json           emit a JSON object instead of KEY=STATUS lines
#
# Statuses:
#   OK          >= min-bytes, readable
#   WEAK        < min-bytes - treat the subagent as having failed silently
#   MISSING     declared via --expect but not present on disk
#   UNREADABLE  present but cannot be read (permissions, dangling symlink)
#
# Non-findings files are skipped: research-contract.md, *-report.md,
# *.eval.md, *.log, and anything under downloads/.
#
# Exit codes:
#   0  at least one OK findings file - safe to dispatch the synthesizer
#   1  zero OK findings files - nothing worth synthesizing, tell the user
#   2  usage error (no work dir, or work dir does not exist)
#
# The caller MUST pass every WEAK/MISSING entry into the synthesizer brief so
# they land in the report's Gaps & Limitations section instead of vanishing.
set -uo pipefail

err() { printf '%s\n' "$*" >&2; }

print_help() { sed -n '2,42p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'; }

WORK_DIR=""
MIN_BYTES=500
JSON=0
EXPECTED=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) print_help; exit 0 ;;
    --expect)
      [ $# -ge 2 ] || { err "verify_findings.sh: --expect needs a filename"; exit 2; }
      EXPECTED+=("$2"); shift 2 ;;
    --min-bytes)
      [ $# -ge 2 ] || { err "verify_findings.sh: --min-bytes needs a number"; exit 2; }
      case "$2" in ''|*[!0-9]*) err "verify_findings.sh: --min-bytes must be an integer"; exit 2 ;; esac
      MIN_BYTES="$2"; shift 2 ;;
    --json) JSON=1; shift ;;
    -*) err "verify_findings.sh: unknown flag: $1"; exit 2 ;;
    *)
      [ -z "$WORK_DIR" ] || { err "verify_findings.sh: unexpected argument: $1"; exit 2; }
      WORK_DIR="$1"; shift ;;
  esac
done

[ -n "$WORK_DIR" ] || { err "verify_findings.sh: missing <work-dir>"; print_help >&2; exit 2; }
[ -d "$WORK_DIR" ] || { err "verify_findings.sh: not a directory: $WORK_DIR"; exit 2; }

# is_findings <basename> - false for contracts, prior reports, logs.
is_findings() {
  case "$1" in
    research-contract.md|*-report.md|*-report.old.md|*.eval.md|*.log) return 1 ;;
    *.md) return 0 ;;
    *) return 1 ;;
  esac
}

# classify <path> -> prints "STATUS BYTES"
classify() {
  local f="$1" sz
  [ -e "$f" ] || { printf 'MISSING 0'; return; }
  if [ ! -r "$f" ] || ! sz=$(wc -c < "$f" 2>/dev/null); then
    printf 'UNREADABLE 0'; return
  fi
  sz=${sz//[[:space:]]/}
  if [ "$sz" -lt "$MIN_BYTES" ]; then printf 'WEAK %s' "$sz"; else printf 'OK %s' "$sz"; fi
}

names=()
if [ "${#EXPECTED[@]}" -gt 0 ]; then
  names=("${EXPECTED[@]}")
fi
# Always include findings files actually on disk, even if not declared. An
# undeclared file is real evidence the synthesizer should see.
for f in "$WORK_DIR"/*.md; do
  [ -e "$f" ] || continue
  b="$(basename "$f")"
  is_findings "$b" || continue
  for n in ${names[@]+"${names[@]}"}; do [ "$n" = "$b" ] && continue 2; done
  names+=("$b")
done

if [ "${#names[@]}" -eq 0 ]; then
  err "verify_findings.sh: no findings files in $WORK_DIR"
  [ "$JSON" = "1" ] && printf '{"work_dir":"%s","min_bytes":%s,"files":{},"ok":0}\n' "$WORK_DIR" "$MIN_BYTES"
  exit 1
fi

ok_count=0
json_entries=""
for n in "${names[@]}"; do
  read -r status bytes <<<"$(classify "$WORK_DIR/$n")"
  [ "$status" = "OK" ] && ok_count=$((ok_count + 1))
  if [ "$JSON" = "1" ]; then
    [ -n "$json_entries" ] && json_entries="$json_entries,"
    json_entries="$json_entries\"$n\":{\"status\":\"$status\",\"bytes\":$bytes}"
  else
    printf '%s=%s (%s bytes)\n' "$n" "$status" "$bytes"
  fi
done

if [ "$JSON" = "1" ]; then
  printf '{"work_dir":"%s","min_bytes":%s,"files":{%s},"ok":%s}\n' \
    "$WORK_DIR" "$MIN_BYTES" "$json_entries" "$ok_count"
fi

[ "$ok_count" -gt 0 ] || { err "verify_findings.sh: no OK findings file - do not synthesize"; exit 1; }
exit 0
