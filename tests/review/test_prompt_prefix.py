"""The prompt keeps its stable parts first and ignores the key order of the task file."""

import json

from ezz_a2a.review.task import REVIEW_INSTRUCTIONS, prepare_review

TASK_FIELDS = {
    "id": "synthetic", "objective": "Review", "base_commit": "synthetic",
    "dependencies": [], "files": ["pkg/service.py"], "acceptance": ["No edits"], "checks": [],
}
SOURCE = "def run(value):\n    return value\n"


def make_repository(tmp_path, source=SOURCE):
    path = tmp_path / "pkg/service.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def prompt_for(tmp_path, fields):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(fields), encoding="utf-8")
    return prepare_review(task_file, tmp_path)[3]


def test_key_order_in_the_task_file_does_not_change_the_prompt(tmp_path):
    make_repository(tmp_path)
    reordered = dict(reversed(list(TASK_FIELDS.items())))
    assert prompt_for(tmp_path, TASK_FIELDS) == prompt_for(tmp_path, reordered)


def test_instructions_then_task_then_sources_then_context(tmp_path):
    make_repository(tmp_path)
    prompt = prompt_for(tmp_path, TASK_FIELDS)
    body = json.loads(prompt.removeprefix(REVIEW_INSTRUCTIONS))
    assert list(body) == ["task", "sources", "context"]
    assert prompt.startswith(REVIEW_INSTRUCTIONS)
    assert prompt.index('"task"') < prompt.index('"sources"') < prompt.index('"context"')


def test_a_changed_source_leaves_the_prefix_up_to_the_sources_intact(tmp_path):
    make_repository(tmp_path)
    first = prompt_for(tmp_path, TASK_FIELDS)
    make_repository(tmp_path, SOURCE + "# edited\n")
    second = prompt_for(tmp_path, TASK_FIELDS)
    shared = first[:first.index('"sources"')]
    assert second.startswith(shared)
