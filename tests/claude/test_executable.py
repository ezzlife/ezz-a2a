"""Executable discovery with real files and POSIX installation layouts."""

import os
from pathlib import Path

import pytest

from ezz_a2a.claude import executable


def posix_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(executable, "IS_WINDOWS", False, raising=False)
    monkeypatch.setattr(executable.shutil, "which", lambda _: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


def test_posix_native_install_is_found_outside_path(monkeypatch, tmp_path):
    posix_environment(monkeypatch, tmp_path)
    binary = tmp_path / ".local/bin/claude"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    assert executable.resolve_claude_executable() == str(binary.resolve())


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX executable permissions")
def test_explicit_non_executable_file_is_rejected(tmp_path):
    binary = tmp_path / "claude"
    binary.write_text("not executable", encoding="utf-8")
    binary.chmod(0o644)
    with pytest.raises(FileNotFoundError):
        executable.resolve_claude_executable(str(binary))


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX symlinks")
def test_path_symlink_resolves_to_executable(monkeypatch, tmp_path):
    binary = tmp_path / "claude-version"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    link = tmp_path / "claude"
    link.symlink_to(binary)
    monkeypatch.setattr(executable.shutil, "which", lambda _: str(link))
    assert executable.resolve_claude_executable() == str(binary.resolve())
