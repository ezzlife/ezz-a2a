"""The coordinator attaches lesson hits to the prompt, trimming them last."""

import json

from ezz_a2a.review.task import REVIEW_INSTRUCTIONS, prepare_review

HELPERS = "def clean(value):\n    return value.strip()\n"
SERVICE = 'from .helpers import clean\n\nQUERY = "SELECT 1 WHERE name LIKE ?"\nclean(QUERY)\n'


def review(tmp_path):
    for name, text in {"pkg/service.py": SERVICE, "pkg/helpers.py": HELPERS}.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "id": "synthetic", "objective": "Review", "base_commit": "synthetic",
        "dependencies": [], "files": ["pkg/service.py"], "acceptance": ["No edits"], "checks": [],
    }), encoding="utf-8")
    return prepare_review(task, tmp_path)


def test_hits_are_in_the_context_and_in_the_prompt(tmp_path):
    _, _, context, prompt = review(tmp_path)
    assert [hit["lesson"] for hit in context["lessons"]] == ["like-without-escape"]
    assert context["lessons"][0]["line"] == 3
    assert context["lessons_omitted"] == 0
    assert "like-without-escape" in prompt


def test_lessons_survive_when_definitions_have_to_go(tmp_path, monkeypatch):
    _, _, full, prompt = review(tmp_path)
    monkeypatch.setattr("ezz_a2a.review.task.MAX_PROMPT_CHARACTERS", len(prompt) - 1)
    _, _, context, limited = review(tmp_path)
    assert context["definitions"] == [] and context["omitted"] == len(full["definitions"])
    assert len(context["lessons"]) == 1 and context["lessons_omitted"] == 0
    assert len(limited) <= len(prompt) - 1


def test_lessons_are_dropped_only_after_every_definition(tmp_path, monkeypatch):
    _, _, _, prompt = review(tmp_path)
    monkeypatch.setattr("ezz_a2a.review.task.MAX_PROMPT_CHARACTERS", len(prompt) - 200)
    _, _, context, limited = review(tmp_path)
    assert context["definitions"] == []
    assert context["lessons"] == [] and context["lessons_omitted"] == 1
    assert len(limited) <= len(prompt) - 200


def test_instructions_tell_the_reviewer_to_verify_each_lesson_hit():
    assert "lessons" in REVIEW_INSTRUCTIONS.lower()
