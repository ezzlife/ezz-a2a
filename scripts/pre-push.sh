#!/usr/bin/env bash
# Run what CI runs, on the same Python, before pushing.
set -euo pipefail

CI_PYTHON_VERSION="3.11"
cd "$(dirname "$0")/.."
python=".venv/Scripts/python.exe"
[ -x "$python" ] || python=".venv/bin/python"

version="$("$python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [ "$version" != "$CI_PYTHON_VERSION" ]; then
  echo "The venv runs Python $version but CI runs $CI_PYTHON_VERSION; rebuild .venv with $CI_PYTHON_VERSION." >&2
  exit 1
fi

"$python" -m pytest
"$python" -m pyflakes ezz_a2a tests
"$python" -m ezz_a2a.demo
