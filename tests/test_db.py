from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from sfcr.db import connect, init_db, load_extractions_from_dir

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_connect_enables_foreign_keys_for_writable_and_readonly_connections(
    tmp_path: Path,
):
    db_path = init_db(tmp_path / "sfcr.sqlite")

    con = connect(db_path)
    try:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        con.close()

    con = connect(db_path, readonly=True)
    try:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        con.close()


@pytest.mark.parametrize("table_name", ["extractions", "summaries", "final_values"])
def test_child_tables_enforce_document_foreign_keys(
    tmp_path: Path, table_name: str
):
    db_path = init_db(tmp_path / "sfcr.sqlite")
    con = connect(db_path)
    try:
        fk_rows = con.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
        assert any(
            row["table"] == "documents"
            and row["from"] == "doc_id"
            and str(row["on_delete"]).upper() == "CASCADE"
            for row in fk_rows
        )

        with pytest.raises(sqlite3.IntegrityError):
            if table_name == "extractions":
                con.execute(
                    """
                    INSERT INTO extractions
                      (doc_id, field_id, verified)
                    VALUES (?, ?, ?)
                    """,
                    ("missing-doc", "scr_total", 0),
                )
            elif table_name == "summaries":
                con.execute(
                    """
                    INSERT INTO summaries
                      (doc_id, section_id, summary)
                    VALUES (?, ?, ?)
                    """,
                    ("missing-doc", "A", "summary"),
                )
            else:
                con.execute(
                    """
                    INSERT INTO final_values
                      (doc_id, field_id, verified, source_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("missing-doc", "scr_total", 0, "extraction"),
                )
    finally:
        con.close()


def test_deleting_document_cascades_to_all_child_tables(tmp_path: Path):
    db_path = init_db(tmp_path / "sfcr.sqlite")
    con = connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO documents
              (doc_id, year, company, display_name, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("doc-1", 2024, "ACME", "ACME (2024)", "/tmp/doc-1.pdf"),
        )
        con.execute(
            """
            INSERT INTO extractions
              (doc_id, field_id, verified)
            VALUES (?, ?, ?)
            """,
            ("doc-1", "scr_total", 1),
        )
        con.execute(
            """
            INSERT INTO summaries
              (doc_id, section_id, summary)
            VALUES (?, ?, ?)
            """,
            ("doc-1", "A", "summary"),
        )
        con.execute(
            """
            INSERT INTO final_values
              (doc_id, field_id, verified, source_type)
            VALUES (?, ?, ?, ?)
            """,
            ("doc-1", "scr_total", 1, "extraction"),
        )
        con.commit()

        con.execute("DELETE FROM documents WHERE doc_id = ?", ("doc-1",))
        con.commit()

        assert con.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM extractions").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM final_values").fetchone()[0] == 0
    finally:
        con.close()


def test_init_db_migrates_legacy_final_values_to_document_foreign_key(
    tmp_path: Path,
):
    db_path = tmp_path / "sfcr.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE documents (
              doc_id TEXT PRIMARY KEY,
              year INTEGER NOT NULL,
              company TEXT NOT NULL,
              display_name TEXT NOT NULL,
              pdf_path TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE final_values (
              doc_id TEXT NOT NULL,
              field_id TEXT NOT NULL,
              value_canonical REAL,
              unit TEXT,
              verified INTEGER NOT NULL,
              source_type TEXT NOT NULL,
              source_note TEXT,
              PRIMARY KEY (doc_id, field_id)
            )
            """
        )
        con.execute(
            """
            INSERT INTO documents
              (doc_id, year, company, display_name, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("doc-1", 2024, "ACME", "ACME (2024)", "/tmp/doc-1.pdf"),
        )
        con.executemany(
            """
            INSERT INTO final_values
              (doc_id, field_id, value_canonical, unit, verified, source_type, source_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("doc-1", "scr_total", 390.0, "pct", 1, "manual", None),
                ("missing-doc", "scr_total", 123.0, "pct", 0, "manual", None),
            ],
        )
        con.commit()
    finally:
        con.close()

    init_db(db_path)

    con = connect(db_path)
    try:
        fk_rows = con.execute("PRAGMA foreign_key_list(final_values)").fetchall()
        assert any(
            row["table"] == "documents"
            and row["from"] == "doc_id"
            and str(row["on_delete"]).upper() == "CASCADE"
            for row in fk_rows
        )
        assert [
            row["doc_id"]
            for row in con.execute(
                "SELECT doc_id FROM final_values ORDER BY doc_id"
            ).fetchall()
        ] == ["doc-1"]

        con.execute("DELETE FROM documents WHERE doc_id = ?", ("doc-1",))
        con.commit()

        assert con.execute("SELECT COUNT(*) FROM final_values").fetchone()[0] == 0
    finally:
        con.close()


def test_init_db_repairs_repo_default_database_snapshot(tmp_path: Path):
    db_path = tmp_path / "artifacts" / "sfcr.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECT_ROOT / "artifacts" / "sfcr.sqlite", db_path)

    init_db(db_path)

    con = connect(db_path)
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


def test_load_extractions_from_dir_serializes_structured_verifier_notes(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    jsonl_path = out_dir / "doc.extractions.jsonl"
    jsonl_path.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "field_id": "scr_total",
                "status": "ok",
                "verified": False,
                "value_canonical": None,
                "unit": "EUR",
                "confidence": 0.35,
                "evidence": [{"page": 7, "ref": None, "snippet_hash": "deadbeef"}],
                "source_text": "SCR 390%",
                "scale_applied": None,
                "verifier_notes": [
                    {"code": "value_not_found_in_source_text"},
                    {"code": "ratio_mismatch"},
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "sfcr.sqlite"
    init_db(db_path)
    con = connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO documents
              (doc_id, year, company, display_name, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("doc-1", 2024, "ACME", "ACME (2024)", "/tmp/doc-1.pdf"),
        )
        con.commit()
    finally:
        con.close()

    n_docs, n_rows = load_extractions_from_dir(out_dir=out_dir, db_path=db_path)

    assert (n_docs, n_rows) == (1, 1)

    con = connect(db_path, readonly=True)
    try:
        row = con.execute(
            "SELECT page, issues FROM extractions WHERE doc_id = ? AND field_id = ?",
            ("doc-1", "scr_total"),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["page"] == 7
    assert json.loads(row["issues"]) == [
        {"code": "value_not_found_in_source_text"},
        {"code": "ratio_mismatch"},
    ]


def test_load_extractions_from_dir_rejects_legacy_string_verifier_notes(
    tmp_path: Path,
):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    jsonl_path = out_dir / "doc.extractions.jsonl"
    jsonl_path.write_text(
        json.dumps(
            {
                "doc_id": "doc-1",
                "field_id": "scr_total",
                "status": "not_found",
                "verified": False,
                "value_canonical": None,
                "unit": "EUR",
                "confidence": 0.35,
                "evidence": [{"page": 7, "ref": None, "snippet_hash": "deadbeef"}],
                "source_text": "SCR nicht eindeutig",
                "scale_applied": None,
                "verifier_notes": "ratio_mismatch",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "sfcr.sqlite"
    init_db(db_path)
    con = connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO documents
              (doc_id, year, company, display_name, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("doc-1", 2024, "ACME", "ACME (2024)", "/tmp/doc-1.pdf"),
        )
        con.commit()
    finally:
        con.close()

    with pytest.raises(ValidationError):
        load_extractions_from_dir(out_dir=out_dir, db_path=db_path)
