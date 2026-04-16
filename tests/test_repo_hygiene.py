from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "--no-index", "-v", path],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_gitignore_covers_typical_generated_artifacts() -> None:
    ignored_paths = [
        ".DS_Store",
        "pkg/__MACOSX/metadata",
        "logs/autobuild.jsonl",
        "tmp/scratch.sqlite",
        "tmp/scratch.sqlite-wal",
    ]

    for path in ignored_paths:
        result = _check_ignore(path)
        assert result.returncode == 0, path


def test_demo_database_stays_explicitly_unignored() -> None:
    result = _check_ignore("artifacts/sfcr.sqlite")

    assert result.returncode == 0
    assert "!artifacts/sfcr.sqlite" in result.stdout


def test_generated_playbook_jsonl_is_removed_and_now_ignored() -> None:
    assert not (PROJECT_ROOT / "ace_playbook.jsonl").exists()

    result = _check_ignore("ace_playbook.jsonl")
    assert result.returncode == 0
