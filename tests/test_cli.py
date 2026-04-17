from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from sfcr.runtime_resources import bundled_fields_path, bundled_ui_app_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = CliRunner()


def _load_cli():
    module_name = "_test_scripts_cli"
    sys.modules.pop(module_name, None)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_ROOT / "scripts" / "cli.py",
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_help_bootstraps_project_root_before_sfcr_imports(tmp_path: Path):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "cli.py"), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "SFCR demo pipeline" in result.stdout


def test_extract_uses_bundled_fields_yaml_when_no_override_is_passed(
    monkeypatch, tmp_path: Path
):
    cli = _load_cli()
    pdf_path = tmp_path / "doc-1.pdf"
    ingest_path = tmp_path / "doc-1.ingest.json"
    out_path = tmp_path / "doc-1.extractions.jsonl"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    ingest_path.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: SimpleNamespace(
            pdfs_dir=tmp_path,
            output_dir_ingest=tmp_path,
            output_dir_extract=tmp_path,
        ),
    )
    monkeypatch.setattr(
        cli, "create_llm_text_client", lambda provider, model="": object()
    )

    class _FakeExtractor:
        def __init__(self, text_client) -> None:
            self.text_client = text_client

    monkeypatch.setattr(cli, "LLMExtractor", _FakeExtractor)

    def fake_extract_for_document(doc_id, pdf, ingest_json, fields, extractor):
        captured["doc_id"] = doc_id
        captured["pdf"] = pdf
        captured["ingest_json"] = ingest_json
        captured["fields"] = fields
        captured["extractor"] = extractor
        return [{"doc_id": doc_id, "field_id": "scr_total"}]

    def fake_write_jsonl(rows, out):
        captured["rows"] = rows
        captured["out"] = out
        out.write_text("[]\n", encoding="utf-8")

    monkeypatch.setattr(cli, "extract_for_document", fake_extract_for_document)
    monkeypatch.setattr(cli, "write_jsonl", fake_write_jsonl)

    result = RUNNER.invoke(
        cli.app,
        [
            "extract",
            str(pdf_path),
            "--ingest-json",
            str(ingest_path),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["doc_id"] == "doc-1"
    assert captured["fields"] == bundled_fields_path()
    assert captured["out"] == out_path


def test_extract_dir_uses_bundled_fields_yaml_when_no_override_is_passed(
    monkeypatch, tmp_path: Path
):
    cli = _load_cli()
    src_dir = tmp_path / "pdfs"
    src_dir.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: SimpleNamespace(pdfs_dir=src_dir),
    )
    monkeypatch.setattr(
        cli, "create_llm_text_client", lambda provider, model="": object()
    )

    class _FakeExtractor:
        def __init__(self, text_client) -> None:
            self.text_client = text_client

    monkeypatch.setattr(cli, "LLMExtractor", _FakeExtractor)

    def fake_extract_directory(
        src_dir, fields_yaml, pattern, extractor, resume, limit, show_progress
    ):
        captured["src_dir"] = src_dir
        captured["fields_yaml"] = fields_yaml
        captured["pattern"] = pattern
        captured["resume"] = resume
        captured["limit"] = limit
        captured["show_progress"] = show_progress
        return (2, 1)

    monkeypatch.setattr(cli, "extract_directory", fake_extract_directory)

    result = RUNNER.invoke(cli.app, ["extract-dir", str(src_dir), "--no-progress"])

    assert result.exit_code == 0, result.output
    assert captured["src_dir"] == src_dir
    assert captured["fields_yaml"] == bundled_fields_path()
    assert captured["show_progress"] is False


def test_ingest_dir_creates_configured_output_directory_before_writing(
    monkeypatch, tmp_path: Path
):
    cli = _load_cli()
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "doc-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    ingest_outdir = tmp_path / "artifacts" / "ingest"
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: SimpleNamespace(
            pdfs_dir=pdf_dir,
            output_dir_ingest=ingest_outdir,
        ),
    )
    monkeypatch.setattr(cli, "_sha256", lambda path: "a" * 64)

    class _FakeLoader:
        def page_count(self) -> int:
            return 1

    class _FakeIngestor:
        def __init__(self, doc_id: str, pdf_path: str) -> None:
            captured["doc_id"] = doc_id
            captured["pdf_path"] = pdf_path
            self.loader = _FakeLoader()

        def run(self):
            return SimpleNamespace(
                sections=[
                    SimpleNamespace(section="A", start_page=1, end_page=1),
                ],
                subsections=[],
                coverage_ratio=1.0,
                issues=[],
            )

    monkeypatch.setattr(cli, "SFCRIngestor", _FakeIngestor)

    result = RUNNER.invoke(cli.app, ["ingest-dir"])

    assert result.exit_code == 0, result.output
    assert captured["doc_id"] == "doc-1"
    assert captured["pdf_path"] == str(pdf_path)
    assert ingest_outdir.is_dir()
    out_path = ingest_outdir / "doc-1.ingest.json"
    assert out_path.is_file()
    assert json.loads(out_path.read_text(encoding="utf-8")) == {
        "coverage_ratio": 1.0,
        "doc_id": "doc-1",
        "issues": [],
        "page_count": 1,
        "pdf_sha256": "a" * 64,
        "schema_version": "1.0.0",
        "sections": [{"end_page": 1, "section": "A", "start_page": 1}],
        "subsections": [],
    }


def test_ui_command_uses_bundled_ui_app_path(monkeypatch):
    cli = _load_cli()
    captured: dict[str, object] = {}

    def fake_run(args, check):
        captured["args"] = args
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(cli.sys, "executable", "/usr/bin/python-test")

    result = RUNNER.invoke(cli.app, ["ui"])

    assert result.exit_code == 0, result.output
    assert captured["args"] == [
        "/usr/bin/python-test",
        "-m",
        "streamlit",
        "run",
        str(bundled_ui_app_path()),
    ]
    assert captured["check"] is True


def test_ui_command_propagates_streamlit_failures(monkeypatch):
    cli = _load_cli()

    def fake_run(args, check):
        raise subprocess.CalledProcessError(returncode=7, cmd=args)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(cli.sys, "executable", "/usr/bin/python-test")

    result = RUNNER.invoke(cli.app, ["ui"])

    assert result.exit_code == 7


def test_db_load_initializes_default_db_before_loading(monkeypatch, tmp_path: Path):
    cli = _load_cli()

    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    db_path = output_dir / "sfcr.sqlite"
    shutil.copy2(PROJECT_ROOT / "artifacts" / "sfcr.sqlite", db_path)

    import sfcr.db as db_module

    settings = SimpleNamespace(output_dir=output_dir)
    monkeypatch.setattr(db_module, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "load_catalog", lambda: 0)
    monkeypatch.setattr(cli, "load_extractions_from_dir", lambda: (0, 0))
    monkeypatch.setattr(cli, "load_summaries_from_dir", lambda: (0, 0))
    monkeypatch.setattr(cli, "rebuild_final_values", lambda: 0)

    result = RUNNER.invoke(cli.app, ["db-load"])

    assert result.exit_code == 0, result.output

    con = db_module.connect(db_path)
    try:
        fk_rows = con.execute("PRAGMA foreign_key_list(final_values)").fetchall()
        assert any(
            row["table"] == "documents"
            and row["from"] == "doc_id"
            and str(row["on_delete"]).upper() == "CASCADE"
            for row in fk_rows
        )
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        con.close()
