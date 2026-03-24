from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from sfcr.extract.schema import (
    MAX_LENGTH_SOURCE_TEXT,
    Evidence,
    ExtractionLLM,
    ResponseLLM,
    VerifiedExtraction,
    VerifierNote,
)
from sfcr.extract.verify import _NO_SECTION, verify_extraction
from sfcr.ingest.schema import IngestionResult
from sfcr.llm.llm_text_client import LLMTextClient
from sfcr.runtime_resources import bundled_fields_path
from sfcr.utils.page_ranges import load_pdf_page_offset_info, resolve_pdf_page_span
from sfcr.utils.textnorm import normalize_hyphenation

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    fitz = None
    _FITZ_IMPORT_ERROR = e

# ---------- field taxonomy ----------


@dataclass
class FieldDef:
    id: str
    subsection_hint: str  # "A".."E" (usually), could be "D"/"E"
    unit: str  # "EUR" or "%"
    typical_scale: float | None
    keywords: List[str]
    notes: str | None


def load_fields(path: Path | None = None) -> List[FieldDef]:
    path = path or bundled_fields_path()
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: List[FieldDef] = []
    for r in rows:
        subsection_hint = r.get("subsection_hint")
        if subsection_hint is None:
            subsection_hint = r.get("section_hint", "E")
        out.append(
            FieldDef(
                id=r["id"],
                subsection_hint=subsection_hint,
                unit=r["unit"],
                typical_scale=r.get("typical_scale"),
                keywords=r.get("keywords", []),
                notes=r.get("notes", ""),
            )
        )
    return out


def _subsection_span_for(
    sub_id: str, ingestion: IngestionResult
) -> Optional[Tuple[int, int]]:
    for s in ingestion.subsections:
        if sub_id == getattr(s, "code", None):
            return s.start_page, s.end_page
    return None


def _letter_from_sub_hint(sub_hint: str) -> str:
    if sub_hint and len(sub_hint) > 0:
        first_char = sub_hint[0].upper()
        if first_char in ("A", "B", "C", "D", "E"):
            return first_char
    if sub_hint.startswith("S."):
        return "E"
    return "E"


# ---------- simple text utilities ----------


def extract_text_pages(pdf_path: Path, start: int, end: int) -> Tuple[str, List[str]]:
    """
    Return (joined_text, page_texts[]), inclusive 1-based pages.
    """
    _ensure_fitz()
    doc = fitz.open(pdf_path)
    try:
        start0 = max(1, start) - 1
        end0 = min(end, doc.page_count) - 1
        pages = []
        for i in range(start0, end0 + 1):
            p = doc.load_page(i)
            pages.append(p.get_text("text"))
        return ("\n".join(pages), pages)
    finally:
        doc.close()


# TODO this needs some work
def harvest_scale_tokens(page_texts: List[str]) -> List[Tuple[str, str]]:
    """
    Very small heuristic: look for scale phrases commonly near tables/captions.
    Returned as [(token_text, source_tag), ...] in precedence order.
    """
    tokens: List[Tuple[str, str]] = []
    # naive scan of first 3 lines of first few pages for captions
    for idx, t in enumerate(page_texts[:3]):
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        for ln in lines[:5]:
            if any(
                key in ln
                for key in (
                    "Angaben in",
                    "in TEUR",
                    "in Mio",
                    "EUR",
                    "Euro",
                    "TEUR",
                    "Mio",
                    "Mrd",
                )
            ):
                tokens.append((ln, "caption"))
    # column/row hints (very rough)
    for t in page_texts[:2]:
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        for ln in lines[:30]:
            if any(k in ln for k in ("EUR", "TEUR", "Mio", "Mrd", "in EUR", "in TEUR")):
                tokens.append((ln, "column"))
    # nearby fallback
    if not tokens and page_texts:
        tokens.append((page_texts[0][:200], "nearby"))
    return tokens


def _mk_snippet_hash(*parts: object, length: int = 16) -> str:
    basis = " | ".join(str(p) for p in parts if p is not None and str(p).strip())
    if not basis:
        basis = "empty"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:length]


_EVIDENCE_WS_RE = re.compile(r"\s+")


def _normalize_evidence_text(text: str) -> str:
    return _EVIDENCE_WS_RE.sub(" ", normalize_hyphenation(text or "")).strip().lower()


def _source_text_locators(source_text: str) -> List[str]:
    normalized = _normalize_evidence_text(source_text)
    if not normalized:
        return []

    locators: List[str] = []

    def add(candidate: str, *, min_length: int = 8) -> None:
        candidate = candidate.strip()
        if len(candidate) < min_length or candidate in locators:
            return
        locators.append(candidate)

    add(normalized)

    if normalized.endswith("..."):
        without_ellipsis = normalized[:-3].rstrip()
        add(without_ellipsis)
        for size in (160, 120, 80, 60):
            add(without_ellipsis[:size], min_length=20)

    return locators


def _locate_evidence_page(
    source_text: Optional[str], page_texts: Optional[List[str]], page_start: int
) -> Optional[int]:
    if not page_texts:
        return None

    locators = _source_text_locators(source_text or "")
    if not locators:
        return None

    normalized_pages = [_normalize_evidence_text(page_text) for page_text in page_texts]
    for locator in locators:
        for idx, page_text in enumerate(normalized_pages):
            if locator and locator in page_text:
                return page_start + idx

    return None


def _page_text_for_evidence(
    evidence: List[Evidence], page_texts: List[str], page_start: int
) -> Optional[str]:
    if not evidence:
        return None

    page_idx0 = evidence[0].page - page_start
    if 0 <= page_idx0 < len(page_texts):
        return page_texts[page_idx0]
    return None


_SII_RATIO_FIELD_ID = "sii_ratio_pct"
_SII_RATIO_TOLERANCE = 0.2


def _verified_numeric_value(
    verified_by_field: dict[str, VerifiedExtraction],
    field_id: str,
    *,
    unit: str,
) -> Optional[float]:
    row = verified_by_field.get(field_id)
    if row is None or not row.verified or row.unit != unit or row.value_canonical is None:
        return None
    try:
        return float(row.value_canonical)
    except (TypeError, ValueError):
        return None


def _ratio_check_for_field(
    field_id: str, verified_by_field: dict[str, VerifiedExtraction]
) -> Optional[Tuple[float, float]]:
    if field_id != _SII_RATIO_FIELD_ID:
        return None

    eof_total = _verified_numeric_value(verified_by_field, "eof_total", unit="EUR")
    scr_total = _verified_numeric_value(verified_by_field, "scr_total", unit="EUR")
    if eof_total is None or scr_total in (None, 0.0):
        return None

    expected_ratio = round(100.0 * eof_total / scr_total, 2)
    return expected_ratio, _SII_RATIO_TOLERANCE


@dataclass
class _PendingVerification:
    index: int
    field: FieldDef
    llm_out: ExtractionLLM
    page_text_for_scale: Optional[str]


@dataclass
class LLMExtractor:
    """
    Orchestrates extraction for ANY provider/model by calling a text client.

    - builds prompt
    - calls text_client.generate_raw(...)
    - parses ResponseLLM JSON
    - returns ExtractionLLM with deterministic evidence snippet_hash
    """

    text_client: LLMTextClient
    output_max_tokens: int = 400  # used by Ollama; OpenAI ignores in options

    def extract(
        self,
        field: FieldDef,
        section_text: str,
        page_start: int,
        page_end: int,
        page_texts: Optional[List[str]] = None,
    ) -> ExtractionLLM:
        prompt = self._build_prompt(field, section_text, page_start, page_end)

        raw = self.text_client.generate_raw(
            prompt=prompt,
            json_schema=ResponseLLM.model_json_schema(),
            options={"num_predict": self.output_max_tokens},
        )

        raw = raw.strip()
        if not raw:
            return ExtractionLLM(
                field_id=field.id, status="not_found", evidence=[], source_text=None
            )

        parsed = ResponseLLM.model_validate_json(raw)

        src_text = (parsed.source_text or "").strip()
        if len(src_text) > MAX_LENGTH_SOURCE_TEXT:
            src_text = src_text[: MAX_LENGTH_SOURCE_TEXT - 3] + "..."

        evidence_page = _locate_evidence_page(src_text or None, page_texts, page_start)
        evidence = []
        if evidence_page is not None:
            sh = _mk_snippet_hash(src_text, field.id, evidence_page)
            evidence = [Evidence(page=evidence_page, ref=None, snippet_hash=sh)]

        return ExtractionLLM(
            field_id=field.id,
            status=parsed.status,
            value_unscaled=parsed.value_unscaled,
            unit=parsed.unit,
            scale=parsed.scale,
            evidence=evidence,
            source_text=src_text or None,
        )

    def _build_prompt(
        self, field: FieldDef, text: str, page_start: int, page_end: int
    ) -> str:
        field_keywords = " bzw. ".join((field.keywords or []))
        return f"""
You are an information extraction engine for German SFCR sections.

Task:
Extract exactly one value for the field below from the provided section text.
If the value is not uniquely and explicitly present, set status to "not_found" or "ambiguous"
and set all numeric fields to null.

Field:
- field_id: {field.id}
- expected_unit: {field.unit}
- page_range: {page_start}-{page_end}
- helpful_keywords: {field_keywords}
- notes: {field.notes}

Return ONLY one JSON object with EXACTLY these keys (always present):
status, value_unscaled, scale, unit, source_text

Definitions:
- value_unscaled: the number as printed, WITHOUT applying scale and WITHOUT any thousands separators
- scale: 1 | 1000 | 1000000 | 1000000000 | null
- unit: "EUR" for monetary amounts, "%" for percentages, else null
- source_text: verbatim excerpt (<={MAX_LENGTH_SOURCE_TEXT} chars) that includes the value AND the nearby label/keyword

Rules:
1) Number parsing (German locale):
   - Thousands separators may be ".", spaces, NBSP.
   - Decimal separator may be ",".
2) Previous year in parentheses:
   - If you see "X (Y)" where X and Y are numbers next to each other,
     treat X as current year and Y as previous year. Return X.
3) Disambiguation:
   - Prefer a number that appears on the SAME LINE (or same table row) as one of the helpful_keywords.
   - If no plausible candidate remains, set status="not_found".
   - If multiple plausible candidates remain, set status="ambiguous".
4) Scale detection (set scale, do NOT multiply into value_unscaled):
   - If the relevant row/column/caption/nearby text indicates:
     * "EUR" or "€" -> scale = 1 (unless TEUR/Tsd/Mio/Mrd is stated)
     * "TEUR", "Tsd", "Tsd €", "Tausend" -> scale = 1000
     * "Mio", "Million" -> scale = 1000000
     * "Mrd", "Milliarde" -> scale = 1000000000
   - If no scale info is present, set scale=null
5) If status != "ok":
   - value_unscaled=null, scale=null, unit=null
   - source_text may be null
6) Treat hyphenated line breaks as merged words (e.g. "Mindestkapitalanfor-\\nderung" -> "Mindestkapitalanforderung").
7) Output ONLY JSON. No prose, no markdown.

Section text:
---
{text}
---
""".strip()


# ---------- Orchestration ----------


def _section_span_for(
    letter: str, ingestion: IngestionResult
) -> Optional[Tuple[int, int]]:
    for s in ingestion.sections:
        if s.section == letter:
            return (s.start_page, s.end_page)
    return None


def _ensure_fitz() -> None:
    if fitz is None:  # pragma: no cover
        raise RuntimeError(
            "PyMuPDF (fitz) is required to extract text from PDF pages. "
            "Install it with: pip install pymupdf"
        ) from _FITZ_IMPORT_ERROR


def extract_for_document(
    doc_id: str,
    pdf_path: Path,
    ingestion_json: Path,
    fields_yaml: Path,
    extractor: LLMExtractor,
) -> List[VerifiedExtraction]:
    """f
    Run extraction + verification for a single document.
    """

    ingestion = IngestionResult(
        **json.loads(ingestion_json.read_text(encoding="utf-8"))
    )
    field_defs = load_fields(fields_yaml)

    offset_info = load_pdf_page_offset_info(pdf_path)
    page_count = offset_info.page_count
    offset_arabic = offset_info.offset_arabic
    offset_roman = offset_info.offset_roman
    offset_confidence = offset_info.confidence

    print(f"Determining page offset for f{doc_id}")
    print("PDF pages:", page_count)
    print("Arabic offset:", offset_arabic)
    print("Roman offset:", offset_roman)
    print("Confidence:", offset_confidence)

    results: List[Optional[VerifiedExtraction]] = [None] * len(field_defs)
    verified_by_field: dict[str, VerifiedExtraction] = {}
    pending_ratio_verifications: list[_PendingVerification] = []

    for idx, f in enumerate(field_defs):
        span = _subsection_span_for(f.subsection_hint, ingestion)
        if not span:
            letter = _letter_from_sub_hint(f.subsection_hint)
            span = _section_span_for(letter, ingestion)
        if not span:
            # no section → not found
            results[idx] = (
                VerifiedExtraction(
                    doc_id=doc_id,
                    field_id=f.id,
                    status="not_found",
                    verified=False,
                    value_canonical=None,
                    unit=f.unit if f.unit in ("EUR", "%") else None,
                    confidence=0.0,
                    evidence=[],
                    source_text=None,
                    scale_applied=None,
                    verifier_notes=[VerifierNote(code=_NO_SECTION)],
                )
            )
            continue

        start, end = span
        start, end = resolve_pdf_page_span(
            start,
            end,
            offset_arabic=offset_arabic,
            page_count=page_count,
        )

        section_text, page_texts = extract_text_pages(pdf_path, start, end)
        section_text, page_texts = (
            normalize_hyphenation(section_text),
            [normalize_hyphenation(page_text) for page_text in page_texts],
        )
        # LLM pass
        llm_out = extractor.extract(
            f, section_text, start, end, page_texts=page_texts
        )

        # Only use page text that is backed by localized evidence.
        page_text_for_scale = _page_text_for_evidence(llm_out.evidence, page_texts, start)

        pending = _PendingVerification(
            index=idx,
            field=f,
            llm_out=llm_out,
            page_text_for_scale=page_text_for_scale,
        )
        if f.id == _SII_RATIO_FIELD_ID:
            pending_ratio_verifications.append(pending)
            continue

        ver = verify_extraction(
            doc_id=doc_id,
            extr=llm_out,
            expected_unit=f.unit,
            typical_scale=f.typical_scale,
            page_text_for_scale=page_text_for_scale,
            ratio_check=None,
        )
        results[idx] = ver
        if ver.verified:
            verified_by_field[f.id] = ver

    for pending in pending_ratio_verifications:
        ratio_check = _ratio_check_for_field(pending.field.id, verified_by_field)
        ver = verify_extraction(
            doc_id=doc_id,
            extr=pending.llm_out,
            expected_unit=pending.field.unit,
            typical_scale=pending.field.typical_scale,
            page_text_for_scale=pending.page_text_for_scale,
            ratio_check=ratio_check,
        )
        results[pending.index] = ver
        if ver.verified:
            verified_by_field[pending.field.id] = ver

    return [result for result in results if result is not None]


def write_jsonl(rows: List[VerifiedExtraction], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(
                json.dumps(r.model_dump(exclude_none=True), ensure_ascii=False) + "\n"
            )
