"""Repository-level contract tests for documentation and release hygiene."""
from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility.
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
README_FILES = [ROOT / "README.md", ROOT / "README.zh-CN.md"]


def _local_markdown_links(markdown: str) -> list[str]:
    links = []
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        links.append(target.split("#", 1)[0])
    return links


def test_required_project_files_exist():
    required = [
        "LICENSE",
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "MANIFEST.in",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "src/safari_mcp/core.py",
        "src/safari_mcp/cli.py",
        "src/safari_mcp/mcp_server.py",
        "tests/e2e_mcp_roundtrip.py",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    assert missing == []


def test_readme_local_links_and_assets_exist():
    for readme in README_FILES:
        markdown = readme.read_text(encoding="utf-8")
        missing = [link for link in _local_markdown_links(markdown) if not (ROOT / link).exists()]
        assert missing == [], f"{readme.name} has broken local links: {missing}"


def test_readmes_document_real_safari_boundaries():
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    assert "real Safari.app session" in english
    assert "not an isolated automation profile" in english
    assert "Allow JavaScript from Apple Events" in english
    assert "no Linux/Windows support" in english

    assert "真正的 Safari.app" in chinese
    assert "不是隔离的自动化 profile" in chinese
    assert "允许来自 Apple 事件的 JavaScript" in chinese
    assert "Linux/Windows" in chinese


def test_ci_covers_tests_cli_smoke_mcp_import_and_artifacts():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python-version: [\"3.10\", \"3.12\"]" in workflow
    assert "python -m pytest -v" in workflow
    assert "safari-mcp --version" in workflow
    assert "safari-mcp --help" in workflow
    assert "from safari_mcp import mcp_server" in workflow
    assert "python -m build" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_version_is_consistent_between_package_and_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    init_text = (ROOT / "src/safari_mcp/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)

    assert match is not None
    assert match.group(1) == project["version"]


def test_readmes_link_release_history_and_license():
    for readme in README_FILES:
        markdown = readme.read_text(encoding="utf-8")
        assert "CHANGELOG.md" in markdown
        assert "LICENSE" in markdown


def test_changelog_documents_current_version_and_order():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    current = f"## v{project['version']}"

    assert current in changelog
    assert changelog.index("## v0.1.3") < changelog.index("## v0.1.2") < changelog.index("## v0.1.1")


def test_source_distribution_manifest_includes_release_metadata():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    for required in [
        "include CHANGELOG.md",
        "include README.zh-CN.md",
        "include .github/workflows/ci.yml",
        "recursive-include tests *.py",
        "recursive-include docs *.png *.mp4",
    ]:
        assert required in manifest


def test_ci_runs_for_main_and_version_tags():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "branches: [main]" in workflow
    assert 'tags: ["v*"]' in workflow
