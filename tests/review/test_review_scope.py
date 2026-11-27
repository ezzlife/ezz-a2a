"""Exercise actual scope barriers on existing files, including Windows junctions."""

import json
import os
import subprocess
from contextlib import contextmanager

import pytest

from ezz_a2a.review.task import prepare_review


def task_for(repository, name):
    path = repository / "task.json"
    path.write_text(json.dumps({
        "id": "synthetic", "objective": "Review", "base_commit": "synthetic",
        "dependencies": [], "files": [name], "acceptance": ["Read only"], "checks": [],
    }), encoding="utf-8")
    return path


@pytest.mark.parametrize("name", [
    "src/private.db", "src/.env", "src/.hidden/source.py",
])
def test_existing_disallowed_source_hits_specific_filter(tmp_path, name):
    source = tmp_path / name
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic contents")
    with pytest.raises(ValueError, match="not allowed"):
        prepare_review(task_for(tmp_path, name), tmp_path)


@pytest.mark.parametrize("name", [
    "evidence/previous-review.json", "tasks/other-task.json",
    "evidence/previous-source.ts", "tasks/other-source.php",
])
def test_generated_evidence_and_task_files_are_not_review_sources(tmp_path, name):
    source = tmp_path / name
    source.parent.mkdir(parents=True)
    source.write_text('{"sources": "previous snapshot"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Evidence or task"):
        prepare_review(task_for(tmp_path, name), tmp_path)


@contextmanager
def directory_link(link, target):
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, check=False)
        if result.returncode:
            pytest.skip("El entorno no permite crear un junction de Windows")
    else:
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("El entorno no permite crear un enlace simbolico")
    try:
        yield
    finally:
        if os.name == "nt":
            link.rmdir()  # Remove only the junction, never its target.
        else:
            link.unlink()


def test_junction_or_symlink_cannot_escape_the_repository(tmp_path):
    repository = tmp_path / "repository"
    root = repository / "src"
    root.mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    sentinel = target / "source.py"
    sentinel.write_bytes(b"synthetic private content")
    with directory_link(root / "alias", target):
        with pytest.raises(ValueError, match="outside the repository"):
            prepare_review(task_for(repository, "src/alias/source.py"), repository)
    assert sentinel.read_bytes() == b"synthetic private content"


def test_alias_cannot_hide_resolved_hidden_directory(tmp_path):
    root = tmp_path / "src"
    hidden = root / ".private"
    hidden.mkdir(parents=True)
    (hidden / "source.py").write_bytes(b"synthetic content")
    with directory_link(root / "alias", hidden):
        with pytest.raises(ValueError, match="not allowed"):
            prepare_review(task_for(tmp_path, "src/alias/source.py"), tmp_path)


@pytest.mark.parametrize("target_directory,source_name,requested", [
    ("node_modules", "source.ts", "src/alias/source.ts"),
    ("dist", "source.js", "src/alias/source.js"),
    (".github/private", "ci.yml", ".github/workflows/ci.yml"),
])
def test_directory_alias_cannot_bypass_context_policy(
        tmp_path, target_directory, source_name, requested):
    target = tmp_path / target_directory
    target.mkdir(parents=True)
    (target / source_name).write_bytes(b"synthetic source")
    alias = tmp_path / requested
    alias.parent.parent.mkdir(parents=True, exist_ok=True)
    with directory_link(alias.parent, target):
        with pytest.raises(ValueError, match="not allowed"):
            prepare_review(task_for(tmp_path, requested), tmp_path)


def test_non_utf8_source_has_a_specific_preflight_error(tmp_path):
    source = tmp_path / "src/source.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="Cannot read UTF-8 source"):
        prepare_review(task_for(tmp_path, "src/source.py"), tmp_path)
