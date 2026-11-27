"""Definitions imported from unlisted files are attached without calling any model."""

import json

import pytest

from ezz_a2a.review.task import REVIEW_INSTRUCTIONS, prepare_review

HELPERS = '''HELPER_LIMIT = 5


def clean(value):
    return value.strip()


def unused(value):
    return value


class Builder:
    def build(self):
        return "built"
'''
SOURCE = '''from .helpers import clean, Builder, HELPER_LIMIT, unused

def run(value):
    return clean(value) + Builder().build() + str(HELPER_LIMIT)
'''


def make_repository(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def review(tmp_path, listed=("pkg/service.py",)):
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "id": "synthetic", "objective": "Review", "base_commit": "synthetic",
        "dependencies": [], "files": list(listed), "acceptance": ["No edits"], "checks": [],
    }), encoding="utf-8")
    return prepare_review(task, tmp_path)


def definitions_by_symbol(context):
    return {entry["symbol"]: entry for entry in context["definitions"]}


def test_used_imported_symbols_are_attached_with_their_location(tmp_path):
    make_repository(tmp_path, {"pkg/service.py": SOURCE, "pkg/helpers.py": HELPERS})
    _, _, context, prompt = review(tmp_path)
    found = definitions_by_symbol(context)
    assert set(found) == {"clean", "Builder", "HELPER_LIMIT"}
    assert found["clean"]["path"] == "pkg/helpers.py"
    assert found["clean"]["lines"] == "4-5"
    assert found["clean"]["content"] == "def clean(value):\n    return value.strip()"
    assert found["Builder"]["content"].startswith("class Builder:")
    assert "def clean(value)" in prompt
    assert context["omitted"] == 0


def test_absolute_imports_resolve_from_the_repository_root(tmp_path):
    make_repository(tmp_path, {
        "pkg/service.py": "from shared.tools import clean\nclean(1)\n",
        "shared/tools.py": HELPERS,
    })
    _, _, context, _ = review(tmp_path)
    assert definitions_by_symbol(context)["clean"]["path"] == "shared/tools.py"


def test_symbols_already_in_a_listed_file_are_not_repeated(tmp_path):
    make_repository(tmp_path, {"pkg/service.py": SOURCE, "pkg/helpers.py": HELPERS})
    _, _, context, _ = review(tmp_path, ["pkg/service.py", "pkg/helpers.py"])
    assert context["definitions"] == []


@pytest.mark.parametrize("module", ["evidence/leaked.py", "tasks/leaked.py", "vendor/leaked.py",
                                    "pkg/leaked_pb2.py"])
def test_excluded_locations_are_never_attached(tmp_path, module):
    dotted = module[:-len(".py")].replace("/", ".")
    make_repository(tmp_path, {
        "pkg/service.py": f"from {dotted} import clean\nclean(1)\n",
        module: HELPERS,
    })
    _, _, context, prompt = review(tmp_path)
    assert context["definitions"] == []
    assert "value.strip()" not in prompt


def test_unparsable_and_non_python_sources_are_skipped(tmp_path):
    make_repository(tmp_path, {"pkg/broken.py": "def (:\n", "docs/notes.md": "from .x import y\n"})
    _, _, context, _ = review(tmp_path, ["pkg/broken.py", "docs/notes.md"])
    assert context["definitions"] == []


def test_the_prompt_limit_drops_the_longest_definitions_and_counts_them(tmp_path, monkeypatch):
    make_repository(tmp_path, {"pkg/service.py": SOURCE, "pkg/helpers.py": HELPERS})
    _, _, full, prompt = review(tmp_path)
    monkeypatch.setattr("ezz_a2a.review.task.MAX_PROMPT_CHARACTERS", len(prompt) - 1)
    _, _, context, limited = review(tmp_path)
    kept = definitions_by_symbol(context)
    assert "Builder" not in kept
    assert context["omitted"] == len(full["definitions"]) - len(kept) >= 1
    assert len(limited) <= len(prompt) - 1


def test_instructions_tell_the_reviewer_how_to_use_the_context():
    assert "context" in REVIEW_INSTRUCTIONS.lower()
