"""Multi-language source snapshots preserve content and enforce scope limits."""

import hashlib
import json

import pytest

from ezz_a2a.review.task import prepare_review
from ezz_a2a.settings import MAX_PROMPT_CHARACTERS


@pytest.fixture
def review_file(tmp_path):
    def write(name, content):
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(content)
        task = tmp_path / "task.json"
        task.write_text(json.dumps({
            "id": "multilanguage", "objective": "Review selected sources",
            "base_commit": "declared", "dependencies": [], "files": [name],
            "acceptance": ["Report concrete defects"], "checks": [],
        }), encoding="utf-8")
        return task
    return write


@pytest.mark.parametrize("name,content", [
    ("backend/main.go", "package main\n"),
    ("backend/Review.java", "class Review {}\n"),
    ("server/index.js", "export const value = 1;\n"),
    ("server/index.mjs", "export default 1;\n"),
    ("server/index.cjs", "module.exports = 1;\n"),
    ("frontend/index.ts", "export const value: number = 1;\n"),
    ("server/index.mts", "export default 1;\n"),
    ("server/index.cts", "export = 1;\n"),
    ("react/Hello.jsx", "export default () => <p>Hola</p>;\n"),
    ("react/Hello.tsx", "export default () => <p>Hola</p>;\n"),
    ("angular/app.component.ts", "export class AppComponent {}\n"),
    ("angular/app.component.html", "<h1>{{ title }}</h1>\n"),
    ("vue/Hello.vue", "<template><p>Hola</p></template>\n"),
    ("laravel/app/Example.php", "<?php class Example {}\n"),
    ("laravel/resources/views/hello.blade.php", "<h1>{{ $title }}</h1>\n"),
    ("web/index.html", '<p lang="es">Revisión</p>\n'),
    ("styles/main.css", ".title { color: red; }\n"),
    ("styles/main.scss", "$color: red;\n.title { color: $color; }\n"),
    ("styles/main.sass", "$color: red\n.title\n  color: $color\n"),
    ("styles/main.less", "@color: red;\n.title { color: @color; }\n"),
])
def test_selected_language_source_reaches_prompt_with_exact_snapshot(
        tmp_path, review_file, name, content):
    raw = content.encode("utf-8")
    task_file = review_file(name, raw)
    task, sources, _, prompt = prepare_review(task_file, tmp_path)
    assert task["files"] == [name]
    assert sources == [{"path": name, "content": content,
                        "sha256": hashlib.sha256(raw).hexdigest()}]
    assert json.loads(prompt.partition("\n")[2])["sources"] == sources


@pytest.mark.parametrize("name", [
    "src/.private/key.ts", "src/.secret.php", "src/.env.js",
])
def test_new_language_suffix_does_not_allow_hidden_sources(tmp_path, review_file, name):
    task_file = review_file(name, b"private content")
    with pytest.raises(ValueError, match="not allowed"):
        prepare_review(task_file, tmp_path)


def test_non_utf8_frontend_source_is_rejected(tmp_path, review_file):
    task_file = review_file("frontend/App.vue", b"\xff\xfe")
    with pytest.raises(ValueError, match="Cannot read UTF-8 source"):
        prepare_review(task_file, tmp_path)


def test_large_frontend_source_is_rejected_before_sending(tmp_path, review_file):
    task_file = review_file("frontend/App.tsx", b"x" * MAX_PROMPT_CHARACTERS)
    with pytest.raises(ValueError, match="Context exceeds"):
        prepare_review(task_file, tmp_path)
