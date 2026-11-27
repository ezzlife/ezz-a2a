"""Found by the first known-findings review: a LIKE pattern built from input matches `_` and `%` as wildcards."""

import re

ID = "like-without-escape"
NOTE = ("SQL LIKE with a bound pattern and no ESCAPE clause: `_` and `%` typed by the "
        "user act as wildcards. Verify whether the value is escaped.")
INPUT_PATTERN = re.compile(r"\bLIKE\s+(?:\w+\()?(?:\?|:\w+|%s|\$\d+|@\w+)", re.IGNORECASE)
ESCAPE = re.compile(r"\bESCAPE\b", re.IGNORECASE)
LINES_AFTER = 2


def check(source: dict) -> list[int]:
    lines = source["content"].splitlines()
    return [number for number, line in enumerate(lines, 1)
            if INPUT_PATTERN.search(line)
            and not ESCAPE.search("\n".join(lines[number - 1:number + LINES_AFTER]))]
