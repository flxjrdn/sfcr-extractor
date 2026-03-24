from __future__ import annotations

import json
from pathlib import Path

from sfcr.summarize.summarize import run_summarize
from sfcr.utils.page_ranges import PdfPageOffsetInfo


class _StubLLM:
    def __init__(self, response: str = "• Zusammenfassung"):
        self.response = response

    def generate_raw(self, prompt: str, options=None):  # pragma: no cover - trivial
        return self.response

    def was_truncated(self) -> bool:
        return False


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_summarize_applies_pdf_offset_to_summary_pages(
    monkeypatch, tmp_path: Path
):
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(
        ingest_path,
        {
            "schema_version": "1.0.0",
            "doc_id": "doc",
            "pdf_sha256": None,
            "page_count": 12,
            "sections": [
                {"section": "A", "start_page": 2, "end_page": 3},
                {"section": "E", "start_page": 7, "end_page": 8},
            ],
            "subsections": [],
            "coverage_ratio": 1.0,
            "issues": [],
        },
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    out_path = tmp_path / "doc.summaries.jsonl"

    calls: list[tuple[int, int]] = []

    monkeypatch.setattr(
        "sfcr.summarize.summarize.create_llm_text_client",
        lambda provider, model: _StubLLM(),
    )
    monkeypatch.setattr(
        "sfcr.summarize.summarize.load_pdf_page_offset_info",
        lambda _pdf_path: PdfPageOffsetInfo(
            page_count=12,
            offset_arabic=3,
            offset_roman=None,
            confidence=0.95,
        ),
    )

    def fake_extract_text_for_pages(_pdf: Path, start_page: int, end_page: int) -> str:
        calls.append((start_page, end_page))
        return f"Inhalt {start_page}-{end_page}"

    monkeypatch.setattr(
        "sfcr.summarize.summarize._extract_text_for_pages", fake_extract_text_for_pages
    )

    run_summarize(
        doc_id="doc",
        pdf_path=pdf_path,
        ingest_json=ingest_path,
        out_jsonl=out_path,
        provider="mock",
        model="mock",
    )

    assert calls == [(5, 6), (10, 11)]

    rows = [
        json.loads(line)
        for line in out_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["section_id"] for row in rows] == ["A", "E"]
    assert rows[0]["start_page"] == 5
    assert rows[0]["end_page"] == 6
    assert rows[1]["start_page"] == 10
    assert rows[1]["end_page"] == 11


def test_run_summarize_keeps_ingestion_pages_when_no_offset_is_detected(
    monkeypatch, tmp_path: Path
):
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(
        ingest_path,
        {
            "schema_version": "1.0.0",
            "doc_id": "doc",
            "pdf_sha256": None,
            "page_count": 5,
            "sections": [{"section": "B", "start_page": 3, "end_page": 4}],
            "subsections": [],
            "coverage_ratio": 1.0,
            "issues": [],
        },
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    out_path = tmp_path / "doc.summaries.jsonl"

    calls: list[tuple[int, int]] = []

    monkeypatch.setattr(
        "sfcr.summarize.summarize.create_llm_text_client",
        lambda provider, model: _StubLLM(),
    )
    monkeypatch.setattr(
        "sfcr.summarize.summarize.load_pdf_page_offset_info",
        lambda _pdf_path: PdfPageOffsetInfo(
            page_count=5,
            offset_arabic=None,
            offset_roman=None,
            confidence=0.0,
        ),
    )

    def fake_extract_text_for_pages(_pdf: Path, start_page: int, end_page: int) -> str:
        calls.append((start_page, end_page))
        return f"Inhalt {start_page}-{end_page}"

    monkeypatch.setattr(
        "sfcr.summarize.summarize._extract_text_for_pages", fake_extract_text_for_pages
    )

    run_summarize(
        doc_id="doc",
        pdf_path=pdf_path,
        ingest_json=ingest_path,
        out_jsonl=out_path,
        provider="mock",
        model="mock",
    )

    assert calls == [(3, 4)]
    row = json.loads(out_path.read_text(encoding="utf-8").strip())
    assert row["start_page"] == 3
    assert row["end_page"] == 4
