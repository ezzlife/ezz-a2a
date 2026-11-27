"""Evidence must survive publication errors without replacing prior results."""

import json

import pytest

from ezz_a2a.review.evidence import EvidenceStore


def test_unsupported_hardlinks_preserve_complete_staged_result(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    store = EvidenceStore(output)
    evidence = {"answer": "resultado completo ≠ parcial"}
    store.write(evidence)
    expected = store.pending.read_bytes()

    def unavailable(*args):
        raise OSError("synthetic unsupported filesystem")

    monkeypatch.setattr("ezz_a2a.review.evidence.os.link", unavailable)
    publication = store.publish()
    assert not publication.published
    assert publication.pending == store.pending
    assert store.pending.read_bytes() == expected
    assert json.loads(expected) == evidence
    assert not output.exists()


def test_output_created_during_review_is_never_replaced(tmp_path):
    output = tmp_path / "result.json"
    store = EvidenceStore(output)
    store.write({"answer": "paid result"})
    expected = store.pending.read_bytes()
    sentinel = b"existing evidence must survive"
    output.write_bytes(sentinel)
    publication = store.publish()
    assert not publication.published
    assert output.read_bytes() == sentinel
    assert store.pending.read_bytes() == expected


def test_cleanup_failure_after_publication_is_only_a_warning(tmp_path, monkeypatch):
    from pathlib import Path

    output = tmp_path / "result.json"
    store = EvidenceStore(output)
    store.write({"answer": "complete"})

    def blocked(*args, **kwargs):
        raise PermissionError("synthetic antivirus lock")

    monkeypatch.setattr(Path, "unlink", blocked)
    publication = store.publish()
    assert publication.published
    assert publication.pending == store.pending
    assert publication.warning
    assert json.loads(output.read_text(encoding="utf-8")) == {"answer": "complete"}


def test_preexisting_output_rejected_without_staging(tmp_path):
    output = tmp_path / "result.json"
    output.write_bytes(b"sentinel")
    with pytest.raises(FileExistsError):
        EvidenceStore(output)
    assert list(tmp_path.iterdir()) == [output]


def test_successful_publication_preserves_exact_bytes_and_removes_staging(tmp_path):
    output = tmp_path / "result.json"
    store = EvidenceStore(output)
    store.write({"status": "completed"})
    expected = store.pending.read_bytes()
    publication = store.publish()
    assert publication.published
    assert not store.pending.exists()
    assert output.read_bytes() == expected
