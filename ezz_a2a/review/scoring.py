"""Score a review against a case of known real findings and known false ones."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

FINDING_START = re.compile(r"^(#{1,6}\s|\*\*|\d+\.\s)")
HEADING = re.compile(r"^#{1,6}\s")
NOT_A_CLAIM_HEADING = re.compile(r"no defect|checked", re.IGNORECASE)


@dataclass(frozen=True)
class Score:
    real_found: list[str]
    real_total: int
    false_flagged: list[str]
    false_total: int


def load_expected(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _claims(text: str) -> list[str]:
    """Split the answer into findings; sections that only clear code are left out."""
    claims: list[list[str]] = []
    skipping = False
    for line in text.splitlines():
        if HEADING.match(line):
            skipping = bool(NOT_A_CLAIM_HEADING.search(line))
        if skipping:
            continue
        if FINDING_START.match(line) or not claims:
            claims.append([])
        claims[-1].append(line)
    return ["\n".join(lines) for lines in claims]


def _matches(claim: str, anchors: list[list[str]]) -> bool:
    return all(any(re.search(pattern, claim, re.IGNORECASE) for pattern in group)
               for group in anchors)


def _ids_in(claims: list[str], entries: list[dict]) -> list[str]:
    return [entry["id"] for entry in entries
            if any(_matches(claim, entry["anchors"]) for claim in claims)]


def score(text: str, expected: dict) -> Score:
    claims = _claims(text)
    return Score(
        real_found=_ids_in(claims, expected["real"]), real_total=len(expected["real"]),
        false_flagged=_ids_in(claims, expected["false"]), false_total=len(expected["false"]),
    )
