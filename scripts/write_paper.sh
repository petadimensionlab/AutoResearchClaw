#!/bin/bash
# Build a paper from a markdown analysis report and export it as Word (.docx).
# Runs ONLY the paper-construction stages (16-23) sequentially.
#
# Usage:
#   ./scripts/write_paper.sh <analysis_report.md> [options]
#
# Script options:
#   --dry-run     Print the exact command that would run, then exit (no LLM calls).
#   -h, --help    Show this help.
#
# Options forwarded to `researchclaw paper`:
#   -o, --output DIR         Output run directory (default: artifacts/paper-<ts>-<hash>)
#   -c, --config FILE        Config file (default: auto-detect config.arc.yaml / config.yaml)
#   -t, --topic TEXT         Research topic override
#       --authors TEXT       Author string
#       --output-format FMT  docx (default) | latex | both
#       --charts DIR         Charts directory to copy into the run
#       --references BIB     BibTeX file to seed references.bib
#       --run-id ID          Run id
#
# Examples:
#   ./scripts/write_paper.sh analysis_report.md
#   ./scripts/write_paper.sh analysis_report.md --authors "A. Author" -o artifacts/my-paper
#   ./scripts/write_paper.sh analysis_report.md --dry-run
#
# See docs/IMPROVEMENTS.md (paper-only mode) for details.

set -euo pipefail

usage() {
    cat <<'EOF'
Build a paper from a markdown analysis report and export it as Word (.docx).
Runs ONLY the paper-construction stages (16-23) sequentially.

Usage:
  ./scripts/write_paper.sh <analysis_report.md> [options]

Script options:
  --dry-run     Print the exact command that would run, then exit (no LLM calls).
  -h, --help    Show this help.

Forwarded to `researchclaw paper`:
  -o, --output DIR         Output run directory
  -c, --config FILE        Config file (default: auto-detect)
  -t, --topic TEXT         Research topic override
      --authors TEXT       Author string
      --output-format FMT  docx (default) | latex | both
      --charts DIR         Charts directory
      --references BIB     BibTeX file
      --run-id ID          Run id

Examples:
  ./scripts/write_paper.sh analysis_report.md
  ./scripts/write_paper.sh analysis_report.md --authors "A. Author" -o artifacts/my-paper
  ./scripts/write_paper.sh analysis_report.md --dry-run
EOF
}

has_flag() {
    local needle="$1"
    shift
    local arg
    for arg in "$@"; do
        case "$arg" in
            "$needle"|"$needle"=*) return 0 ;;
        esac
    done
    return 1
}

flag_value() {
    local needle="$1"
    shift
    local prev="" arg
    for arg in "$@"; do
        case "$arg" in
            "$needle"=*) printf '%s' "${arg#*=}"; return 0 ;;
        esac
        if [ "$prev" = "$needle" ]; then
            printf '%s' "$arg"
            return 0
        fi
        prev="$arg"
    done
    return 1
}

if [ "$#" -eq 0 ]; then
    usage
    exit 2
fi

case "$1" in
    -h|--help)
        usage
        exit 0
        ;;
esac

REPORT="$1"
shift

DRY_RUN=0
forward=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) forward+=("$arg") ;;
    esac
done

if [ ! -e "$REPORT" ]; then
    echo "ERROR: analysis report not found: $REPORT" >&2
    exit 1
fi
if [ -d "$REPORT" ]; then
    echo "ERROR: expected a markdown file but got a directory: $REPORT" >&2
    exit 1
fi
case "$REPORT" in
    *.md|*.markdown) ;;
    *) echo "WARNING: '$REPORT' does not end in .md; continuing anyway." >&2 ;;
esac

REPORT_DIR="$(cd "$(dirname "$REPORT")" && pwd)"
REPORT_ABS="$REPORT_DIR/$(basename "$REPORT")"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ -n "${PYTHON_BIN:-}" ]; then
    PY="$PYTHON_BIN"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    echo "ERROR: no Python interpreter found (set PYTHON_BIN)." >&2
    exit 1
fi

if ! "$PY" -c "import researchclaw" >/dev/null 2>&1; then
    echo "ERROR: 'researchclaw' is not importable with '$PY'." >&2
    echo "Install it first: $PY -m pip install -e ." >&2
    exit 1
fi

if ! has_flag -c ${forward[@]+"${forward[@]}"} && ! has_flag --config ${forward[@]+"${forward[@]}"}; then
    if [ ! -f config.arc.yaml ] && [ ! -f config.yaml ]; then
        echo "ERROR: no config file found (config.arc.yaml / config.yaml)." >&2
        echo "Create one first: $PY -m researchclaw init" >&2
        exit 1
    fi
fi

if has_flag --output-format ${forward[@]+"${forward[@]}"}; then
    fmt="$(flag_value --output-format ${forward[@]+"${forward[@]}"})"
else
    fmt="docx"
fi

cmd=("$PY" -m researchclaw paper --report "$REPORT_ABS")
if [ "$fmt" = "docx" ] && ! has_flag --output-format ${forward[@]+"${forward[@]}"}; then
    cmd+=(--output-format docx)
fi
cmd+=(${forward[@]+"${forward[@]}"})

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Would run (stages 16-23 sequential, format=$fmt):"
    printf '  %q' "${cmd[0]}"
    printf ' %q' "${cmd[@]:1}"
    echo
    exit 0
fi

if { [ "$fmt" = "docx" ] || [ "$fmt" = "both" ]; } && ! command -v pandoc >/dev/null 2>&1; then
    echo "WARNING: pandoc not found on PATH; docx export will be skipped (a warning is logged)." >&2
fi

echo "=== Paper-only build (stages 16-23, sequential) ==="
echo "Report: $REPORT_ABS"
echo "Format: $fmt"
echo

"${cmd[@]}"
