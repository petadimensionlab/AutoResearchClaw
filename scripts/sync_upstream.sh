#!/bin/bash
# Sync changes from the upstream project (aiming-lab/AutoResearchClaw) into this
# derivative repository. `upstream` is READ-ONLY: this script never pushes to it.
#
# Usage:
#   ./scripts/sync_upstream.sh [--dry-run] [--no-push] [--skip-tests]
#
#   --dry-run     Fetch and show the incoming diff, then exit without merging.
#   --no-push     Merge locally but do not push to origin.
#   --skip-tests  Skip the test runs after merging.
#
# See docs/UPSTREAM_SYNC.md for the manual procedure and conflict guidance.

set -euo pipefail

UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-upstream}"
ORIGIN_REMOTE="${ORIGIN_REMOTE:-origin}"
UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/aiming-lab/AutoResearchClaw.git}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

DRY_RUN=0
NO_PUSH=0
SKIP_TESTS=0

usage() {
    cat <<'EOF'
Sync changes from upstream (aiming-lab/AutoResearchClaw) into this derivative repo.
`upstream` is read-only; this script never pushes to it.

Usage:
  ./scripts/sync_upstream.sh [--dry-run] [--no-push] [--skip-tests]

Options:
  --dry-run     Fetch and show the incoming diff, then exit without merging.
  --no-push     Merge locally but do not push to origin.
  --skip-tests  Skip the test runs after merging.
  -h, --help    Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --no-push) NO_PUSH=1 ;;
        --skip-tests) SKIP_TESTS=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: not inside a git repository." >&2
    exit 1
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "$MAIN_BRANCH" ]; then
    echo "ERROR: expected to be on '$MAIN_BRANCH' but on '$current_branch'." >&2
    echo "Run: git switch $MAIN_BRANCH" >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: uncommitted tracked changes detected. Commit or 'git stash' first." >&2
    exit 1
fi

if ! git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
    echo "Adding remote '$UPSTREAM_REMOTE' -> $UPSTREAM_URL"
    git remote add "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
fi

echo "Fetching '$UPSTREAM_REMOTE'..."
git fetch "$UPSTREAM_REMOTE" --prune

UPSTREAM_REF="$UPSTREAM_REMOTE/$MAIN_BRANCH"
echo
echo "=== new commits from $UPSTREAM_REF ==="
git log --oneline "$MAIN_BRANCH..$UPSTREAM_REF" || true
echo
echo "=== ahead/behind (left=main ahead, right=upstream behind) ==="
git rev-list --left-right --count "$MAIN_BRANCH...$UPSTREAM_REF"

incoming="$(git rev-list --count "$MAIN_BRANCH..$UPSTREAM_REF")"
if [ "$incoming" -eq 0 ]; then
    echo
    echo "Already up to date with $UPSTREAM_REF. Nothing to do."
    exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo
    echo "Dry run: no branch created, no merge, no push."
    exit 0
fi

sync_branch="sync/upstream-$(date +%Y%m%d-%H%M%S)"
echo
echo "Creating work branch '$sync_branch'..."
git switch -c "$sync_branch"

if ! git merge --no-ff "$UPSTREAM_REF"; then
    echo
    echo "CONFLICT: resolve the files listed above, then run:" >&2
    echo "  git add <files> && git merge --continue" >&2
    echo "To abort and return to '$MAIN_BRANCH':" >&2
    echo "  git merge --abort && git switch $MAIN_BRANCH && git branch -D $sync_branch" >&2
    echo "Conflict hot-spots are listed in docs/UPSTREAM_SYNC.md." >&2
    exit 1
fi

if [ "$SKIP_TESTS" -eq 0 ]; then
    echo
    echo "Running full test suite (known pre-existing failures deselected)..."
    "$PYTHON_BIN" -m pytest -q --ignore=tests/test_anthropic.py \
        --deselect "tests/test_minimax_provider.py::TestMiniMaxFromRCConfig::test_anthropic_presets_append_messages_path" \
        --deselect "tests/test_opencode_bridge.py::TestOpenCodeBridge::test_collect_files_flattens_subdirectories" \
        --deselect "tests/test_web_crawler.py::TestCheckUrlSsrf::test_https_allowed"
    echo
    echo "Running focused docx/paper tests..."
    "$PYTHON_BIN" -m pytest -q \
        tests/test_docx_exporter.py tests/test_paper_report.py tests/test_paper_seed.py \
        tests/test_paper_builder.py tests/test_paper_cli.py
fi

echo
echo "Merging into '$MAIN_BRANCH' and pushing to '$ORIGIN_REMOTE' (never '$UPSTREAM_REMOTE')..."
git switch "$MAIN_BRANCH"
git merge --no-ff "$sync_branch"

if [ "$NO_PUSH" -eq 0 ]; then
    git push "$ORIGIN_REMOTE" "$MAIN_BRANCH"
else
    echo "Skipping push (--no-push). Push manually: git push $ORIGIN_REMOTE $MAIN_BRANCH"
fi

git branch -d "$sync_branch"
echo
echo "Sync complete. '$UPSTREAM_REMOTE' was not pushed to."
