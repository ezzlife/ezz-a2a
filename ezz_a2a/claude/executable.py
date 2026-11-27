"""Resolve native Claude binaries without executing shell launchers."""

import os
import shutil
from pathlib import Path

from ezz_a2a.claude.process_tree import IS_WINDOWS

SCRIPT_LAUNCHER_SUFFIXES = {".cmd", ".bat", ".ps1"}
NPM_NATIVE_BINARY = Path("node_modules/@anthropic-ai/claude-code/bin/claude.exe")


def _explicit_candidates(explicit: str) -> list[Path]:
    candidate = Path(explicit).expanduser()
    if not candidate.is_file():
        located = shutil.which(explicit)
        if located:
            candidate = Path(located)
    return [candidate]


def _default_candidates() -> list[Path]:
    candidates = []
    located = shutil.which("claude")
    if located:
        launcher = Path(located)
        if IS_WINDOWS:
            candidates.append(launcher.parent / NPM_NATIVE_BINARY)
        candidates.append(launcher)
    binary_name = "claude.exe" if IS_WINDOWS else "claude"
    candidates.append(Path.home() / ".local/bin" / binary_name)
    app_data = os.environ.get("APPDATA")
    if IS_WINDOWS and app_data:
        candidates.append(Path(app_data) / "npm" / NPM_NATIVE_BINARY)
    return candidates


def resolve_claude_executable(explicit: str | None = None) -> str:
    candidates = _explicit_candidates(explicit) if explicit else _default_candidates()
    for candidate in candidates:
        if (candidate.is_file()
                and candidate.suffix.lower() not in SCRIPT_LAUNCHER_SUFFIXES
                and (IS_WINDOWS or os.access(candidate, os.X_OK))):
            return str(candidate.resolve())
    raise FileNotFoundError("Executable Claude not found; pass --claude <executable-path>")
