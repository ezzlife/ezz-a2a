"""Found by the first known-findings review: paginating over a non-unique ORDER BY repeats or skips rows."""

import re

ID = "order-by-without-tiebreaker"
NOTE = ("Paginated query (OFFSET) ordered by a single column that may not be unique: "
        "ties can repeat or skip rows between pages. Verify there is a unique tiebreaker.")
ORDER_BY = re.compile(r"\bORDER\s+BY\s+([^\n]*?)\s*(?:\bLIMIT\b|\bOFFSET\b|[\"'`)]|$)",
                      re.IGNORECASE)
UNIQUE_COLUMN = re.compile(r"(?:^|\.|_)(?:row)?id\b", re.IGNORECASE)
OFFSET = re.compile(r"\bOFFSET\b", re.IGNORECASE)
LINES_AROUND = 3


def _is_single_non_unique(clause: str) -> bool:
    return "," not in clause and not UNIQUE_COLUMN.search(clause.split()[0] if clause else "")


def check(source: dict) -> list[int]:
    lines = source["content"].splitlines()
    hits = []
    for number, line in enumerate(lines, 1):
        found = ORDER_BY.search(line)
        window = "\n".join(lines[max(number - 1 - LINES_AROUND, 0):number + LINES_AROUND])
        if found and _is_single_non_unique(found.group(1)) and OFFSET.search(window):
            hits.append(number)
    return hits
