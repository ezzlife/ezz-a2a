"""The report compares two recorded reviews with the figures the CLI reported."""

import json
import sys

import pytest

from ezz_a2a.review.measure import main, report

EXPECTED = {
    "real": [{"id": "R1", "anchors": [["metadata_q"]]}, {"id": "R2", "anchors": [["order by"]]}],
    "false": [{"id": "F1", "anchors": [["budget"]]}],
}


def write_evidence(path, text, metadata):
    evidence = {"responses": [{"artifacts": [{"parts": [{"text": text}], "metadata": metadata}]}]}
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return path


def metadata(output_tokens, cost_usd, cache_read):
    return {"input_tokens": 2, "output_tokens": output_tokens, "cost_usd": cost_usd,
            "cache_creation_input_tokens": 100, "cache_read_input_tokens": cache_read}


def test_report_lines_up_before_and_after(tmp_path):
    before = write_evidence(tmp_path / "before.json", "**metadata_q bug**\n**budget claim**",
                            metadata(10000, 0.2, 0))
    after = write_evidence(tmp_path / "after.json", "**metadata_q bug**\n**ORDER BY ties**",
                           metadata(6000, 0.15, 900))
    lines = report(before, after, EXPECTED).splitlines()
    assert lines[0].split() == ["metric", "before", "after"]
    rows = {line.split()[0]: line.split()[1:] for line in lines[1:]}
    assert rows["real_found"] == ["1/2", "2/2"]
    assert rows["false_flagged"] == ["1/1", "0/1"]
    assert rows["output_tokens"] == ["10000", "6000"]
    assert rows["cost_usd"] == ["0.2", "0.15"]
    assert rows["cache_read"] == ["0", "900"]
    assert len({line.index(line.split()[1]) for line in lines}) == 1


def test_protobuf_floats_are_shown_as_the_numbers_they_hold(tmp_path):
    noisy = write_evidence(tmp_path / "noisy.json", "text",
                           metadata(10690.0, 0.16187300000000002, 1710.0))
    rows = {line.split()[0]: line.split()[1:] for line in report(noisy, noisy, EXPECTED).splitlines()[1:]}
    assert rows["output_tokens"] == ["10690", "10690"]
    assert rows["cache_read"] == ["1710", "1710"]
    assert rows["cost_usd"] == ["0.161873", "0.161873"]


def test_missing_figures_are_shown_as_null(tmp_path):
    bare = write_evidence(tmp_path / "bare.json", "text", {})
    rows = {line.split()[0]: line.split()[1:] for line in report(bare, bare, EXPECTED).splitlines()[1:]}
    assert rows["output_tokens"] == ["null", "null"]
    assert rows["cost_usd"] == ["null", "null"]


def prepare_workspace(tmp_path, monkeypatch, arguments):
    evidence_directory = tmp_path / "evidence"
    evidence_directory.mkdir()
    write_evidence(evidence_directory / "first.json", "**metadata_q bug**", metadata(10, 0.1, 0))
    write_evidence(evidence_directory / "second.json", "**ORDER BY ties**", metadata(5, 0.05, 0))
    case_directory = tmp_path / "cases/sample"
    case_directory.mkdir(parents=True)
    (case_directory / "expected.json").write_text(json.dumps(EXPECTED), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["measure", *arguments])


def test_cli_finds_evidence_and_case_by_name(tmp_path, monkeypatch, capsys):
    prepare_workspace(tmp_path, monkeypatch, ["first.json", "second.json", "--case", "sample"])
    main()
    rows = {line.split()[0]: line.split()[1:] for line in capsys.readouterr().out.splitlines()[1:]}
    assert rows["real_found"] == ["1/2", "1/2"]
    assert rows["output_tokens"] == ["10", "5"]


@pytest.mark.parametrize("arguments", [
    ["../first.json", "second.json", "--case", "sample"],
    ["first.json", "missing.json", "--case", "sample"],
    ["first.json", "second.json", "--case", "other"],
])
def test_cli_rejects_names_that_are_not_listed(tmp_path, monkeypatch, arguments):
    prepare_workspace(tmp_path, monkeypatch, arguments)
    with pytest.raises(SystemExit):
        main()
