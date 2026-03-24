from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from sfcr.extract.extractor import LLMExtractor, extract_for_document, load_fields
from sfcr.extract.schema import (
    MAX_LENGTH_SOURCE_TEXT,
    Evidence,
    ExtractionLLM,
    VerifiedExtraction,
)
from sfcr.extract.verify import _NO_SECTION
from sfcr.llm.llm_text_client import LLMTextClient
from sfcr.runtime_resources import bundled_fields_path
from sfcr.utils.page_ranges import PdfPageOffsetInfo

# ---------------------------
# Test helpers
# ---------------------------


class _StubTextClient(LLMTextClient):
    """
    Simple stub: returns the provided `raw` string verbatim.
    Also records last prompt so tests can assert it.
    """

    def __init__(self, raw: str):
        self._raw = raw
        self.last_prompt: Optional[str] = None
        self.last_json_schema: Optional[dict[str, Any]] = None
        self.last_options: Optional[dict[str, Any]] = None

    def generate_raw(
        self,
        prompt: str,
        *,
        strict_schema: bool = True,
        json_schema: Optional[dict[str, Any]] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> str:
        self.last_prompt = prompt
        self.last_json_schema = json_schema
        self.last_options = options
        return self._raw


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- change this helper -------------------------------------------------


def _ingestion_payload(
    *,
    sections: list[dict[str, Any]],
    subsections: list[dict[str, Any]],
    page_count: int = 3,
):
    # Minimal shape required by IngestionResult(**json.loads(...))
    return {
        "doc_id": "d",
        "pdf_sha256": None,
        "page_count": page_count,
        "sections": sections,
        "subsections": subsections,
        "coverage_ratio": 1.0,
        "issues": [],
    }


def _fields_yaml_one(
    *,
    field_id: str,
    subsection_hint: str,
    unit: str = "EUR",
    typical_scale: float | None = None,
):
    # load_fields expects list[dict]
    rows = [
        {
            "id": field_id,
            "subsection_hint": subsection_hint,
            "unit": unit,
            "typical_scale": typical_scale,
            "keywords": ["TestKeyword"],
            "notes": "",
        }
    ]
    return yaml_dump(rows)


def yaml_dump(obj: Any) -> str:
    # Avoid importing yaml in tests if you prefer; but extractor.py uses yaml anyway.
    import yaml  # type: ignore

    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)


# ---------------------------
# Tests: LLMExtractor.extract
# ---------------------------


def test_llm_extractor_empty_raw_returns_not_found():
    client = _StubTextClient(raw="   \n")
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "x",
            "unit": "EUR",
            "keywords": ["K"],
            "notes": "",
            "subsection_hint": "E",
        },
    )
    out = ex.extract(field, "some text", 10, 12)

    assert out.field_id == "x"
    assert out.status == "not_found"
    assert out.evidence == []
    assert out.source_text is None


def test_llm_extractor_parses_response_and_creates_snippet_hash_hex():
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 123456.0,
            "scale": 1000.0,
            "unit": "EUR",
            "source_text": "Mindestkapitalanforderung 123 456 (133 333) TEUR",
            "notes": None,
        },
        ensure_ascii=False,
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "mcr_total",
            "unit": "EUR",
            "keywords": ["Mindestkapitalanforderung"],
            "notes": "",
            "subsection_hint": "E.2",
        },
    )
    out = ex.extract(
        field,
        "section text",
        5,
        7,
        page_texts=[
            "Vorseite ohne Treffer",
            "Mindestkapitalanforderung 123 456 (133 333) TEUR",
            "Nachlauf",
        ],
    )

    assert out.status == "ok"
    assert out.value_unscaled == 123456.0
    assert out.scale == 1000.0
    assert out.unit == "EUR"
    assert out.evidence and isinstance(out.evidence[0], Evidence)
    assert out.evidence[0].page == 6
    assert out.evidence[0].snippet_hash is not None
    assert re.fullmatch(
        r"[a-f0-9]{16}", out.evidence[0].snippet_hash
    )  # extractor uses length=16


def test_llm_extractor_truncates_source_text_to_max_chars():
    long_src = "X" * (MAX_LENGTH_SOURCE_TEXT + 50)
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 1.0,
            "scale": None,
            "unit": "EUR",
            "source_text": long_src,
        }
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "foo",
            "unit": "EUR",
            "keywords": ["K"],
            "notes": "",
            "subsection_hint": "E",
        },
    )
    out = ex.extract(field, "t", 1, 1)

    assert out.source_text is not None
    assert len(out.source_text) <= MAX_LENGTH_SOURCE_TEXT
    assert out.source_text.endswith("...")
    assert out.evidence == []


def test_llm_extractor_uses_actual_evidence_page_within_multi_page_span():
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 12.0,
            "scale": 1000.0,
            "unit": "EUR",
            "source_text": "SCR-Bedeckung 12 TEUR",
        }
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "scr_total",
            "unit": "EUR",
            "keywords": ["SCR-Bedeckung"],
            "notes": "",
            "subsection_hint": "E.2",
        },
    )
    out = ex.extract(
        field,
        "joined text",
        10,
        12,
        page_texts=[
            "Seite 10 ohne Wert",
            "Seite 11 ohne Wert",
            "Tabelle: SCR-Bedeckung 12 TEUR",
        ],
    )

    assert len(out.evidence) == 1
    assert out.evidence[0].page == 12
    assert out.evidence[0].snippet_hash is not None


def test_llm_extractor_omits_evidence_when_source_text_is_not_locatable_in_multi_page_span():
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 12.0,
            "scale": 1000.0,
            "unit": "EUR",
            "source_text": "SCR-Bedeckung 12 TEUR",
        }
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "scr_total",
            "unit": "EUR",
            "keywords": ["SCR-Bedeckung"],
            "notes": "",
            "subsection_hint": "E.2",
        },
    )
    out = ex.extract(
        field,
        "joined text",
        10,
        12,
        page_texts=[
            "Seite 10 ohne Treffer",
            "Seite 11 ohne Treffer",
            "Seite 12 ebenfalls ohne Treffer",
        ],
    )

    assert out.evidence == []


def test_default_fields_yaml_includes_ratio_field_for_standard_cli_workflow():
    field_ids = [field.id for field in load_fields(bundled_fields_path())]
    assert "sii_ratio_pct" in field_ids


def test_llm_extractor_omits_evidence_without_page_texts():
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 12.0,
            "scale": 1000.0,
            "unit": "EUR",
            "source_text": "SCR-Bedeckung 12 TEUR",
        }
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "scr_total",
            "unit": "EUR",
            "keywords": ["SCR-Bedeckung"],
            "notes": "",
            "subsection_hint": "E.2",
        },
    )
    out = ex.extract(field, "joined text", 10, 10)

    assert out.evidence == []


def test_llm_extractor_omits_evidence_when_source_text_is_not_locatable_in_single_page():
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 12.0,
            "scale": 1000.0,
            "unit": "EUR",
            "source_text": "SCR-Bedeckung 12 TEUR",
        }
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "scr_total",
            "unit": "EUR",
            "keywords": ["SCR-Bedeckung"],
            "notes": "",
            "subsection_hint": "E.2",
        },
    )
    out = ex.extract(
        field,
        "joined text",
        10,
        10,
        page_texts=["Seite 10 ohne Treffer"],
    )

    assert out.evidence == []


def test_llm_extractor_accepts_ambiguous_status_and_prompt_mentions_it():
    raw = json.dumps(
        {
            "status": "ambiguous",
            "value_unscaled": None,
            "scale": None,
            "unit": None,
            "source_text": "SCR 10 TEUR, alternativ SCR 12 TEUR",
        },
        ensure_ascii=False,
    )
    client = _StubTextClient(raw=raw)
    ex = LLMExtractor(text_client=client)

    field = type(
        "F",
        (),
        {
            "id": "scr_total",
            "unit": "EUR",
            "keywords": ["SCR"],
            "notes": "",
            "subsection_hint": "E.2",
        },
    )
    out = ex.extract(field, "section text", 5, 7)

    assert out.status == "ambiguous"
    assert out.value_unscaled is None
    assert out.scale is None
    assert out.unit is None
    assert client.last_prompt is not None
    assert 'status to "not_found" or "ambiguous"' in client.last_prompt
    assert 'set status="ambiguous"' in client.last_prompt
    assert (
        "status, value_unscaled, scale, unit, source_text"
        in client.last_prompt
    )
    assert "status, value_unscaled, scale, unit, source_text, scale_source, notes" not in client.last_prompt


# ---------------------------
# Tests: extract_for_document orchestration
# ---------------------------


def test_extract_for_document_prefers_subsection_span_over_section(
    monkeypatch, tmp_path: Path
):
    """
    If subsection_hint exists in ingestion.subsections, extract_for_document must use that span.
    We assert this by checking the page_start/page_end passed into extract_text_pages via monkeypatch.
    """
    # ingestion: subsection E.2 spans 2..2, section E spans 1..3
    ingestion = _ingestion_payload(
        sections=[{"section": "E", "start_page": 1, "end_page": 3}],
        subsections=[
            {
                "section": "E",
                "code": "E.2",
                "title": "Sub",
                "start_page": 2,
                "end_page": 2,
            }
        ],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        _fields_yaml_one(
            field_id="scr_total",
            subsection_hint="E.2",
            unit="EUR",
            typical_scale=1000.0,
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")  # won't be opened due to monkeypatch

    called = {}

    def fake_extract_text_pages(_pdf_path: Path, start: int, end: int):
        called["start"] = start
        called["end"] = end
        # return "section_text", page_texts list size = end-start+1
        return "Some content", ["Angaben in TEUR\nSome content"]

    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages", fake_extract_text_pages
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)

    # extractor stub returns ok, with evidence page == page_start
    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 10.0,
            "scale": 1000.0,
            "unit": "EUR",
            "source_text": "SCR 10 TEUR",
        }
    )
    extractor = LLMExtractor(text_client=_StubTextClient(raw))

    res = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert called["start"] == 2
    assert called["end"] == 2
    assert len(res) == 1
    assert isinstance(res[0], VerifiedExtraction)
    assert res[0].field_id == "scr_total"


def test_extract_for_document_falls_back_to_section_when_subsection_missing(
    monkeypatch, tmp_path: Path
):
    """
    If subsection span isn't found, extractor should infer section from first letter and use section span.
    """
    ingestion = _ingestion_payload(
        page_count=9,
        sections=[{"section": "E", "start_page": 7, "end_page": 9}],
        subsections=[],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    # subsection_hint is E.2, but ingestion has no subsections, so fall back to E section span
    _write_text(
        fields_path,
        _fields_yaml_one(
            field_id="mcr_total",
            subsection_hint="E.2",
            unit="EUR",
            typical_scale=1000.0,
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    called = {}

    def fake_extract_text_pages(_pdf_path: Path, start: int, end: int):
        called["start"] = start
        called["end"] = end
        return "Some content", ["Some content"] * (end - start + 1)

    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages", fake_extract_text_pages
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)

    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 1.0,
            "scale": None,
            "unit": "EUR",
            "source_text": "MCR 1 EUR",
        }
    )
    extractor = LLMExtractor(text_client=_StubTextClient(raw))

    res = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert called["start"] == 7
    assert called["end"] == 9
    assert len(res) == 1


def test_extract_for_document_applies_pdf_offset_via_shared_page_resolver(
    monkeypatch, tmp_path: Path
):
    ingestion = _ingestion_payload(
        page_count=12,
        sections=[{"section": "E", "start_page": 3, "end_page": 4}],
        subsections=[],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        _fields_yaml_one(
            field_id="scr_total",
            subsection_hint="E.2",
            unit="EUR",
            typical_scale=1000.0,
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    called = {}

    def fake_extract_text_pages(_pdf_path: Path, start: int, end: int):
        called["start"] = start
        called["end"] = end
        return "Some content", ["Some content"] * (end - start + 1)

    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages", fake_extract_text_pages
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)
    monkeypatch.setattr(
        "sfcr.extract.extractor.load_pdf_page_offset_info",
        lambda _pdf_path: PdfPageOffsetInfo(
            page_count=12,
            offset_arabic=2,
            offset_roman=None,
            confidence=0.9,
        ),
    )

    raw = json.dumps(
        {
            "status": "ok",
            "value_unscaled": 1.0,
            "scale": None,
            "unit": "EUR",
            "source_text": "SCR 1 EUR",
        }
    )
    extractor = LLMExtractor(text_client=_StubTextClient(raw))

    _ = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert called["start"] == 5
    assert called["end"] == 6


def test_extract_for_document_no_section_returns_not_found_verified_false(
    tmp_path: Path,
):
    """
    If neither subsection nor section span exists, result should be status=not_found with a structured no_section verifier note.
    """
    ingestion = _ingestion_payload(sections=[], subsections=[])
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        _fields_yaml_one(
            field_id="scr_total",
            subsection_hint="E.2",
            unit="EUR",
            typical_scale=1000.0,
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    # extractor won't be used, but must be provided
    extractor = LLMExtractor(text_client=_StubTextClient(raw="{}"))

    res = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert len(res) == 1
    r = res[0]
    assert r.status == "not_found"
    assert r.verified is False
    assert [note.code for note in r.verifier_notes] == [_NO_SECTION]
    assert r.value_canonical is None


def test_extract_for_document_uses_evidence_page_to_choose_page_text_for_scale(
    monkeypatch, tmp_path: Path
):
    """
    extract_for_document chooses page_text_for_scale based on llm_out.evidence[0].page.
    We simulate span start=10 end=12 with three pages, and set evidence page=12 -> should pass page_texts[2].
    """
    ingestion = _ingestion_payload(
        page_count=12,
        sections=[{"section": "E", "start_page": 10, "end_page": 12}],
        subsections=[
            {
                "section": "E",
                "code": "E.2",
                "title": "Sub",
                "start_page": 10,
                "end_page": 12,
            }
        ],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        _fields_yaml_one(
            field_id="scr_total",
            subsection_hint="E.2",
            unit="EUR",
            typical_scale=1000.0,
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    page_texts = ["p10 caption: Angaben in TEUR", "p11 ...", "p12 Einheit: Mio EUR"]

    def fake_extract_text_pages(_pdf_path: Path, start: int, end: int):
        return "Some content", page_texts

    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages", fake_extract_text_pages
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)

    captured = {}

    def fake_verify_extraction(
        *,
        doc_id,
        extr,
        expected_unit=None,
        typical_scale,
        page_text_for_scale=None,
        ratio_check=None,
    ):
        captured["page_text_for_scale"] = page_text_for_scale
        # return a minimal VerifiedExtraction that satisfies your model
        return VerifiedExtraction(
            doc_id=doc_id,
            field_id=extr.field_id,
            status=extr.status,
            verified=False,
            value_canonical=None,
            unit=extr.unit,
            confidence=0.0,
            evidence=extr.evidence,
            source_text=extr.source_text,
            scale_applied=None,
            verifier_notes=[],
        )

    monkeypatch.setattr(
        "sfcr.extract.extractor.verify_extraction", fake_verify_extraction
    )

    # Make the LLM output have evidence[0].page == 12 (span end),
    # independent of the extractor's own source-text page location logic.
    def fake_extractor_extract(
        _self, field, section_text, page_start, page_end, page_texts=None
    ):
        return ExtractionLLM(
            field_id=field.id,
            status="ok",
            value_unscaled=12.0,
            unit="EUR",
            scale=None,
            evidence=[Evidence(page=12, ref=None, snippet_hash="deadbeefdeadbeef")],
            source_text="SCR 12",
        )

    extractor = LLMExtractor(text_client=_StubTextClient(raw="{}"))
    monkeypatch.setattr(LLMExtractor, "extract", fake_extractor_extract)

    _ = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert captured["page_text_for_scale"] == page_texts[2]


def test_extract_for_document_does_not_fall_back_to_span_start_when_evidence_missing(
    monkeypatch, tmp_path: Path
):
    ingestion = _ingestion_payload(
        page_count=12,
        sections=[{"section": "E", "start_page": 10, "end_page": 12}],
        subsections=[
            {
                "section": "E",
                "code": "E.2",
                "title": "Sub",
                "start_page": 10,
                "end_page": 12,
            }
        ],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        _fields_yaml_one(
            field_id="scr_total",
            subsection_hint="E.2",
            unit="EUR",
            typical_scale=1000.0,
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    page_texts = ["p10 Angaben in TEUR", "p11 ...", "p12 Einheit: Mio EUR"]

    def fake_extract_text_pages(_pdf_path: Path, start: int, end: int):
        return "Some content", page_texts

    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages", fake_extract_text_pages
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)

    captured = {}

    def fake_verify_extraction(
        *,
        doc_id,
        extr,
        expected_unit=None,
        typical_scale,
        page_text_for_scale=None,
        ratio_check=None,
    ):
        captured["page_text_for_scale"] = page_text_for_scale
        return VerifiedExtraction(
            doc_id=doc_id,
            field_id=extr.field_id,
            status=extr.status,
            verified=False,
            value_canonical=None,
            unit=extr.unit,
            confidence=0.0,
            evidence=extr.evidence,
            source_text=extr.source_text,
            scale_applied=None,
            verifier_notes=[],
        )

    monkeypatch.setattr(
        "sfcr.extract.extractor.verify_extraction", fake_verify_extraction
    )

    def fake_extractor_extract(
        _self, field, section_text, page_start, page_end, page_texts=None
    ):
        return ExtractionLLM(
            field_id=field.id,
            status="ok",
            value_unscaled=12.0,
            unit="EUR",
            scale=None,
            evidence=[],
            source_text="SCR 12",
        )

    extractor = LLMExtractor(text_client=_StubTextClient(raw="{}"))
    monkeypatch.setattr(LLMExtractor, "extract", fake_extractor_extract)

    _ = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert captured["page_text_for_scale"] is None


def test_extract_for_document_applies_ratio_check_end_to_end_for_ratio_fields(
    monkeypatch, tmp_path: Path
):
    ingestion = _ingestion_payload(
        page_count=1,
        sections=[{"section": "E", "start_page": 1, "end_page": 1}],
        subsections=[
            {
                "section": "E",
                "code": "E.1",
                "title": "Own funds",
                "start_page": 1,
                "end_page": 1,
            },
            {
                "section": "E",
                "code": "E.2",
                "title": "SCR",
                "start_page": 1,
                "end_page": 1,
            },
        ],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        yaml_dump(
            [
                {
                    "id": "sii_ratio_pct",
                    "subsection_hint": "E.2",
                    "unit": "%",
                    "typical_scale": None,
                    "keywords": ["SCR-Quote"],
                    "notes": "",
                },
                {
                    "id": "eof_total",
                    "subsection_hint": "E.1",
                    "unit": "EUR",
                    "typical_scale": 1.0,
                    "keywords": ["Eigenmittel"],
                    "notes": "",
                },
                {
                    "id": "scr_total",
                    "subsection_hint": "E.2",
                    "unit": "EUR",
                    "typical_scale": 1.0,
                    "keywords": ["SCR"],
                    "notes": "",
                },
            ]
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "sfcr.extract.extractor.load_pdf_page_offset_info",
        lambda _p: PdfPageOffsetInfo(
            page_count=None,
            offset_arabic=None,
            offset_roman=None,
            confidence=0.0,
        ),
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)
    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages",
        lambda _pdf_path, start, end: ("Some content", ["Some content"]),
    )

    outputs = {
        "sii_ratio_pct": ExtractionLLM(
            field_id="sii_ratio_pct",
            status="ok",
            value_unscaled=400.0,
            unit="%",
            scale=None,
            evidence=[],
            source_text="SCR-Quote 400 %",
        ),
        "eof_total": ExtractionLLM(
            field_id="eof_total",
            status="ok",
            value_unscaled=391000.0,
            unit="EUR",
            scale=1.0,
            evidence=[],
            source_text="Anrechenbare Eigenmittel 391.000 EUR",
        ),
        "scr_total": ExtractionLLM(
            field_id="scr_total",
            status="ok",
            value_unscaled=100000.0,
            unit="EUR",
            scale=1.0,
            evidence=[],
            source_text="SCR 100.000 EUR",
        ),
    }

    def fake_extractor_extract(
        _self, field, section_text, page_start, page_end, page_texts=None
    ):
        return outputs[field.id]

    extractor = LLMExtractor(text_client=_StubTextClient(raw="{}"))
    monkeypatch.setattr(LLMExtractor, "extract", fake_extractor_extract)

    res = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert [row.field_id for row in res] == ["sii_ratio_pct", "eof_total", "scr_total"]
    ratio_row = res[0]
    assert ratio_row.field_id == "sii_ratio_pct"
    assert ratio_row.verified is False
    assert ratio_row.confidence < 0.5
    assert [note.code for note in ratio_row.verifier_notes] == ["ratio_mismatch"]


def test_extract_for_document_skips_ratio_check_without_verified_base_values(
    monkeypatch, tmp_path: Path
):
    ingestion = _ingestion_payload(
        page_count=1,
        sections=[{"section": "E", "start_page": 1, "end_page": 1}],
        subsections=[
            {
                "section": "E",
                "code": "E.1",
                "title": "Own funds",
                "start_page": 1,
                "end_page": 1,
            },
            {
                "section": "E",
                "code": "E.2",
                "title": "SCR",
                "start_page": 1,
                "end_page": 1,
            },
        ],
    )
    ingest_path = tmp_path / "doc.ingest.json"
    _write_json(ingest_path, ingestion)

    fields_path = tmp_path / "fields.yaml"
    _write_text(
        fields_path,
        yaml_dump(
            [
                {
                    "id": "sii_ratio_pct",
                    "subsection_hint": "E.2",
                    "unit": "%",
                    "typical_scale": None,
                    "keywords": ["SCR-Quote"],
                    "notes": "",
                },
                {
                    "id": "eof_total",
                    "subsection_hint": "E.1",
                    "unit": "EUR",
                    "typical_scale": 1.0,
                    "keywords": ["Eigenmittel"],
                    "notes": "",
                },
                {
                    "id": "scr_total",
                    "subsection_hint": "E.2",
                    "unit": "EUR",
                    "typical_scale": 1.0,
                    "keywords": ["SCR"],
                    "notes": "",
                },
            ]
        ),
    )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "sfcr.extract.extractor.load_pdf_page_offset_info",
        lambda _p: PdfPageOffsetInfo(
            page_count=None,
            offset_arabic=None,
            offset_roman=None,
            confidence=0.0,
        ),
    )
    monkeypatch.setattr("sfcr.extract.extractor.normalize_hyphenation", lambda s: s)
    monkeypatch.setattr(
        "sfcr.extract.extractor.extract_text_pages",
        lambda _pdf_path, start, end: ("Some content", ["Some content"]),
    )

    outputs = {
        "sii_ratio_pct": ExtractionLLM(
            field_id="sii_ratio_pct",
            status="ok",
            value_unscaled=391.0,
            unit="%",
            scale=None,
            evidence=[],
            source_text="SCR-Quote 391 %",
        ),
        "eof_total": ExtractionLLM(
            field_id="eof_total",
            status="ok",
            value_unscaled=391000.0,
            unit="EUR",
            scale=1.0,
            evidence=[],
            source_text="Anrechenbare Eigenmittel 391.000 EUR",
        ),
        "scr_total": ExtractionLLM(
            field_id="scr_total",
            status="not_found",
            value_unscaled=None,
            unit=None,
            scale=None,
            evidence=[],
            source_text=None,
        ),
    }

    captured_ratio_checks = {}

    def fake_extractor_extract(
        _self, field, section_text, page_start, page_end, page_texts=None
    ):
        return outputs[field.id]

    def fake_verify_extraction(
        *,
        doc_id,
        extr,
        expected_unit=None,
        typical_scale,
        page_text_for_scale=None,
        ratio_check=None,
    ):
        captured_ratio_checks[extr.field_id] = ratio_check
        captured_ratio_checks[f"{extr.field_id}:expected_unit"] = expected_unit
        return VerifiedExtraction(
            doc_id=doc_id,
            field_id=extr.field_id,
            status=extr.status,
            verified=extr.field_id != "scr_total" and extr.status == "ok",
            value_canonical=extr.value_unscaled,
            unit=extr.unit,
            confidence=0.6 if extr.status == "ok" else 0.0,
            evidence=extr.evidence,
            source_text=extr.source_text,
            scale_applied=None,
            verifier_notes=[],
        )

    extractor = LLMExtractor(text_client=_StubTextClient(raw="{}"))
    monkeypatch.setattr(LLMExtractor, "extract", fake_extractor_extract)
    monkeypatch.setattr(
        "sfcr.extract.extractor.verify_extraction", fake_verify_extraction
    )

    _ = extract_for_document(
        doc_id="d",
        pdf_path=pdf_path,
        ingestion_json=ingest_path,
        fields_yaml=fields_path,
        extractor=extractor,
    )

    assert captured_ratio_checks["eof_total"] is None
    assert captured_ratio_checks["scr_total"] is None
    assert captured_ratio_checks["sii_ratio_pct"] is None
    assert captured_ratio_checks["sii_ratio_pct:expected_unit"] == "%"
