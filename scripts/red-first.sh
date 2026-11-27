#!/usr/bin/env bash
# Usage: scripts/red-first.sh tests/path/test_new.py [...]
# Shelve the production changes, run the new tests, show why they fail, restore.
set -euo pipefail

cd "$(dirname "$0")/.."
python=".venv/Scripts/python.exe"
[ -x "$python" ] || python=".venv/bin/python"
[ "$#" -gt 0 ] || { echo "Pass the test files to run." >&2; exit 2; }

production=()
while IFS= read -r line; do
  path="${line:3}"
  case "$path" in tests/*|.tmp/*) ;; *) production+=("$path") ;; esac
done < <(git status --porcelain --untracked-files=all)

if [ "${#production[@]}" -eq 0 ]; then
  echo "No production change to shelve: the tests would run against finished code." >&2
  exit 1
fi

git stash push --quiet --include-untracked -- "${production[@]}"
trap 'git stash pop --quiet' EXIT

echo "Shelved: ${production[*]}"
"$python" -m pytest "$@" 2>&1 | grep -E "^E  |passed|failed|error" | sort | uniq -c | sort -rn | head -20 || true
