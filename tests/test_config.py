from __future__ import annotations

from pathlib import Path

from sfcr.config import Settings


def test_settings_resolve_relative_paths_against_project_root_not_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project-root"
    other_cwd = tmp_path / "elsewhere"
    project_root.mkdir()
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    settings = Settings(
        project_root=project_root,
        data_dir="data",
        pdfs_dir="pdfs",
        output_dir="artifacts",
    )

    assert settings.project_root == project_root.resolve()
    assert settings.data_dir == (project_root / "data").resolve()
    assert settings.pdfs_dir == (project_root / "pdfs").resolve()
    assert settings.output_dir == (project_root / "artifacts").resolve()


def test_settings_instantiation_and_derived_paths_do_not_create_directories(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project-root"
    project_root.mkdir()

    settings = Settings(project_root=project_root)

    expected_paths = [
        settings.data_dir,
        settings.pdfs_dir,
        settings.output_dir,
        settings.output_dir_ingest,
        settings.output_dir_extract,
        settings.output_dir_summaries,
    ]

    assert all(not path.exists() for path in expected_paths)
