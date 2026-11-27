"""Compare two saved reviews: findings against a known case, and the CLI-reported figures."""

import argparse
import json
from pathlib import Path

from ezz_a2a.review.scoring import load_expected, score

EVIDENCE_DIRECTORY = "evidence"
CASES_DIRECTORY = "cases"
EXPECTED_FILE = "expected.json"
NULL = "null"
FIGURE_DECIMALS = 6
METRIC_COLUMN_WIDTH = 16
VALUE_COLUMN_WIDTH = 10
METADATA_ROWS = (
    ("output_tokens", "output_tokens"), ("input_tokens", "input_tokens"),
    ("cache_creation", "cache_creation_input_tokens"),
    ("cache_read", "cache_read_input_tokens"), ("cost_usd", "cost_usd"),
)


def _artifact(evidence_file: Path) -> dict:
    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
    return evidence["responses"][0]["artifacts"][0]


def _figure(metadata: dict, field: str) -> str:
    value = metadata.get(field)
    if value is None:
        return NULL
    value = round(float(value), FIGURE_DECIMALS)
    return str(int(value) if value.is_integer() else value)


def _row(label: str, before: str, after: str) -> str:
    return f"{label:<{METRIC_COLUMN_WIDTH}}{before:<{VALUE_COLUMN_WIDTH}}{after}"


def report(before_file: Path, after_file: Path, expected: dict) -> str:
    before, after = _artifact(before_file), _artifact(after_file)
    scores = [score(artifact["parts"][0]["text"], expected) for artifact in (before, after)]
    rows = [_row("metric", "before", "after"),
            _row("real_found", *(f"{len(s.real_found)}/{s.real_total}" for s in scores)),
            _row("false_flagged", *(f"{len(s.false_flagged)}/{s.false_total}" for s in scores))]
    for label, field in METADATA_ROWS:
        rows.append(_row(label, *(_figure(a.get("metadata") or {}, field)
                                  for a in (before, after))))
    return "\n".join(rows)


def _listed(parser, directory: Path, name: str, pattern: str) -> Path:
    """Return the entry that the directory listing offers under this name."""
    for entry in directory.glob(pattern):
        if entry.name == name:
            return entry
    parser.error(f"Not found in {directory.name}/: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", help="file name inside evidence/")
    parser.add_argument("after", help="file name inside evidence/")
    parser.add_argument("--case", required=True, help="folder name inside cases/")
    args = parser.parse_args()
    root = Path.cwd()
    before = _listed(parser, root / EVIDENCE_DIRECTORY, args.before, "*.json")
    after = _listed(parser, root / EVIDENCE_DIRECTORY, args.after, "*.json")
    case = _listed(parser, root / CASES_DIRECTORY, args.case, "*")
    print(report(before, after, load_expected(case / EXPECTED_FILE)))


if __name__ == "__main__":
    main()
