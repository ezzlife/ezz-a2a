"""Configuration, contracts and build context pass the same source boundary."""

import hashlib
import json

import pytest

from ezz_a2a.review.task import prepare_review


@pytest.fixture
def source_task(tmp_path):
    def write(name, content=b"synthetic source\n"):
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(content)
        task = tmp_path / "review-task.json"
        task.write_text(json.dumps({
            "id": "context", "objective": "Review explicit context",
            "base_commit": "declared", "dependencies": [], "files": [name],
            "acceptance": ["Report concrete defects"], "checks": [],
        }), encoding="utf-8")
        return task
    return write


@pytest.mark.parametrize("name", [
    "deploy/compose.yaml", "deploy/service.yml", "pyproject.toml", "tsconfig.jsonc",
    "db/migration.sql", "prisma/schema.prisma", "api/schema.graphql",
    "api/query.gql", "api/service.proto", "scripts/check.sh", "scripts/check.bash",
    "scripts/check.ps1", "pom.xml", "src/application.properties", "build.gradle",
    "build.gradle.kts", "infra/main.tf", "infra/terragrunt.hcl",
    "Dockerfile", "containers/Containerfile", "Makefile", "ci/Jenkinsfile",
    "backend/go.mod", "backend/go.sum",
    ".github/workflows/ci.yml", ".github/workflows/release.yaml",
])
def test_context_file_is_snapshotted_and_included_in_prompt(tmp_path, source_task, name):
    raw = b"synthetic source\r\n"
    _, sources, _, prompt = prepare_review(source_task(name, raw), tmp_path)
    assert sources == [{"path": name, "content": raw.decode("utf-8"),
                        "sha256": hashlib.sha256(raw).hexdigest()}]
    assert json.loads(prompt.partition("\n")[2])["sources"] == sources


@pytest.mark.parametrize("name", [
    ".env", ".env.production", "config/production.env", "keys/private.key",
    "keys/private.pem", "keys/private.p12", "keys/private.pfx", "keys/private.jks",
    "keys/private.keystore", "certs/private.crt", "certs/private.cer",
    "bin/tool.exe", "bin/tool.dll", "bin/code.wasm", "artifacts/bundle.zip",
    ".github/settings.yml", ".github/workflows/sub/ci.yml",
    ".github/workflows/.private.yml", ".github/workflows/script.ps1",
    "nested/.github/workflows/ci.yml", ".private/workflows/ci.yml",
])
def test_sensitive_binary_or_hidden_context_is_rejected(tmp_path, source_task, name):
    with pytest.raises(ValueError, match="not allowed"):
        prepare_review(source_task(name), tmp_path)


@pytest.mark.parametrize("name", [
    "node_modules/pkg/index.js", "app/vendor/pkg/index.php", "frontend/dist/app.js",
    "frontend/build/app.js", "backend/target/report.xml", "coverage/report.json",
    "src/__pycache__/source.py", "src/client.generated.ts", "src/client_generated.go",
    "src/service.pb.go", "src/service_pb2.py", "assets/app.min.js", "assets/app.min.css",
    "assets/app.js.map",
])
def test_known_generated_files_are_rejected(tmp_path, source_task, name):
    with pytest.raises(ValueError, match="not allowed"):
        prepare_review(source_task(name), tmp_path)


@pytest.mark.parametrize("content", [b"a\x00b", b"{\x00}\x00"])
def test_binary_content_with_allowed_suffix_is_rejected(tmp_path, source_task, content):
    with pytest.raises(ValueError, match="Binary source"):
        prepare_review(source_task("config/settings.json", content), tmp_path)
