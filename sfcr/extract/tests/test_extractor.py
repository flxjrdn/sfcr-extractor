from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from sfcr.extract.extractor import LLMExtractor
from sfcr.extract.schema import MAX_LENGTH_SOURCE_TEXT, Evidence
from sfcr.llm.llm_text_client import LLMTextClient

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
    )

    assert out.status == "ok"
    assert out.value_unscaled == 123456.0
    assert out.scale == 1000.0
    assert out.unit == "EUR"
    assert out.evidence and isinstance(out.evidence[0], Evidence)
    assert out.evidence[0].page == 5
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
