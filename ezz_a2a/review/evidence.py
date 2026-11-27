"""Stage review evidence before execution and publish without replacing files."""

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

EVIDENCE_JSON_INDENT = 2


@dataclass(frozen=True)
class Publication:
    published: bool
    pending: Path | None = None
    warning: str | None = None


def _write_durably(path: Path, text: str, mode: str) -> None:
    with path.open(mode, encoding="utf-8") as staged_file:
        staged_file.write(text)
        staged_file.flush()
        os.fsync(staged_file.fileno())


class EvidenceStore:
    def __init__(self, output: Path):
        self.output = output
        if os.path.lexists(output):
            raise FileExistsError("Output already exists; choose another")
        output.parent.mkdir(parents=True, exist_ok=True)
        self.pending = output.with_name(f".{uuid.uuid4().hex}.pending")
        _write_durably(self.pending, "{}\n", mode="x")

    def write(self, evidence: dict) -> None:
        text = json.dumps(evidence, ensure_ascii=False, indent=EVIDENCE_JSON_INDENT) + "\n"
        _write_durably(self.pending, text, mode="w")

    def publish(self) -> Publication:
        """Hard-link the staged file to the output path, which never overwrites."""
        try:
            os.link(self.pending, self.output)
        except OSError as error:
            return Publication(False, self.pending, type(error).__name__)
        try:
            self.pending.unlink()
        except OSError as error:
            return Publication(True, self.pending, type(error).__name__)
        return Publication(True)
