"""
pdf_page_offset.py

Detects page-number offset between PDF page indices and the printed page numbers
found in headers/footers.

Typical use:
    from pdf_page_offset import detect_pdf_page_offset
    result = detect_pdf_page_offset("document.pdf")
    print(result.offset_arabic, result.confidence)

Requires:
    PyMuPDF (fitz): pip install pymupdf

Notes / limitations:
- If the document uses images for page numbers (scanned pages) or the numbers
  are not extractable as text, this will likely return low confidence or None.
- Front matter sometimes uses Roman numerals (i, ii, iii...) and then switches
  to Arabic (1,2,3...). This module reports both if detected.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    fitz = None
    _FITZ_IMPORT_ERROR = e


# ----------------------------
# Data structures
# ----------------------------


@dataclass(frozen=True)
class PageNumberHit:
    pdf_page_index: int  # 0-based
    region: str  # "header" or "footer"
    raw_text: str  # line text used for extraction
    printed_kind: str  # "arabic" or "roman"
    printed_value: int  # normalized to int (roman converted)
    score: float  # heuristic score


@dataclass(frozen=True)
class OffsetDetectionResult:
    page_count: int
    # Dominant offsets (pdf_page_num - printed_num), where pdf_page_num is 1-based.
    offset_arabic: Optional[int]
    offset_roman: Optional[int]

    # Confidence in [0,1] (for arabic section, because that's usually what users want)
    confidence: float

    # Diagnostics
    samples_arabic: int
    samples_roman: int
    hits: List[PageNumberHit]

    # Per-page chosen (best) printed numbers (None if not detected)
    per_page_printed: Dict[int, Tuple[str, int]]  # page_index -> (kind, value)


# ----------------------------
# Public API
# ----------------------------


def detect_pdf_page_offset(
    pdf_path: str,
    *,
    max_pages: Optional[int] = None,
    sample_strategy: str = "all",
    header_frac: float = 0.14,
    footer_frac: float = 0.14,
    min_hits_for_decision: int = 6,
) -> OffsetDetectionResult:
    """
    Detect page-number offset for a PDF by extracting candidate printed page
    numbers from header/footer text regions.

    Args:
        pdf_path: path to PDF
        max_pages: limit pages analyzed (None = all)
        sample_strategy:
            - "all": analyze every page
            - "smart": analyze a subset (first 12, last 12, then every 5th) for speed
        header_frac/footer_frac: fraction of page height treated as header/footer zones
        min_hits_for_decision: minimum arabic hits needed before reporting an offset

    Returns:
        OffsetDetectionResult
    """
    _ensure_fitz()

    doc = fitz.open(pdf_path)
    try:
        page_indices = _select_pages(
            len(doc), max_pages=max_pages, strategy=sample_strategy
        )
        hits: List[PageNumberHit] = []
        per_page_best: Dict[int, PageNumberHit] = {}

        for i in page_indices:
            page = doc.load_page(i)
            page_hits = _extract_page_number_hits(
                page,
                pdf_page_index=i,
                header_frac=header_frac,
                footer_frac=footer_frac,
            )
            hits.extend(page_hits)

            best = _choose_best_hit(page_hits)
            if best is not None:
                per_page_best[i] = best

        per_page_printed: Dict[int, Tuple[str, int]] = {
            i: (hit.printed_kind, hit.printed_value) for i, hit in per_page_best.items()
        }

        offset_arabic, conf_arabic, n_arabic = _infer_offset(
            per_page_best, kind="arabic"
        )
        offset_roman, conf_roman, n_roman = _infer_offset(per_page_best, kind="roman")

        # Confidence: focus on arabic section as "main" pages; if none, fall back to roman.
        if offset_arabic is not None:
            confidence = conf_arabic
        elif offset_roman is not None:
            confidence = (
                conf_roman * 0.7
            )  # roman-only is often front matter; be slightly conservative
        else:
            confidence = 0.0

        # Only accept arabic offset if we have enough evidence; otherwise set to None.
        if n_arabic < min_hits_for_decision:
            offset_arabic = None
            if offset_roman is None:
                confidence = 0.0

        return OffsetDetectionResult(
            page_count=len(doc),
            offset_arabic=offset_arabic,
            offset_roman=offset_roman,
            confidence=float(max(0.0, min(1.0, confidence))),
            samples_arabic=n_arabic,
            samples_roman=n_roman,
            hits=sorted(hits, key=lambda h: (h.pdf_page_index, -h.score)),
            per_page_printed=per_page_printed,
        )
    finally:
        doc.close()


# ----------------------------
# Core logic
# ----------------------------

_ROMAN_RE = re.compile(r"^(?=[ivxlcdm]+$)[ivxlcdm]+$", re.IGNORECASE)
# Common page number patterns:
#  - "12"
#  - "- 12 -"
#  - "Page 12"
#  - "12 / 120" or "12 of 120"
#  - "xii"
#  - "(12)"
_PAGE_NUM_TOKEN_RE = re.compile(
    r"""
    (?:
        \bpage\s*(?P<arabic1>\d{1,6})\b |
        \b(?P<arabic2>\d{1,6})\s*(?:/|of)\s*\d{1,6}\b |
        ^\s*[-–—(]*\s*(?P<arabic3>\d{1,6})\s*[-–—)]*\s*$ |
        ^\s*[-–—(]*\s*(?P<roman>[ivxlcdm]{1,12})\s*[-–—)]*\s*$
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Noise patterns that often appear in headers/footers and include numbers
# but are not page numbers (dates, version strings, etc.). We don’t ban them
# outright; we penalize them.
_DATEISH_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b")
_TIMEISH_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_VERSIONISH_RE = re.compile(r"\b(v|ver|version)\.?\s*\d", re.IGNORECASE)


def _ensure_fitz() -> None:
    if fitz is None:  # pragma: no cover
        raise RuntimeError(
            "PyMuPDF (fitz) is required for reliable header/footer page-number detection. "
            "Install it with: pip install pymupdf"
        ) from _FITZ_IMPORT_ERROR


def _select_pages(
    n_pages: int, *, max_pages: Optional[int], strategy: str
) -> List[int]:
    if n_pages <= 0:
        return []
    if max_pages is not None:
        n_pages = min(n_pages, max_pages)

    if strategy == "all":
        return list(range(n_pages))

    if strategy == "smart":
        # First 12, last 12, plus every 5th in between
        first = list(range(min(12, n_pages)))
        last = list(range(max(0, n_pages - 12), n_pages))
        middle = list(range(0, n_pages, 5))
        idxs = sorted(set(first + middle + last))
        return idxs

    raise ValueError(f"Unknown sample_strategy={strategy!r}. Use 'all' or 'smart'.")


def _extract_page_number_hits(
    page: "fitz.Page",
    *,
    pdf_page_index: int,
    header_frac: float,
    footer_frac: float,
) -> List[PageNumberHit]:
    """
    Extract candidate page number tokens from header/footer regions.
    Uses coordinates from PyMuPDF text dictionary.
    """
    rect = page.rect
    height = rect.height
    width = rect.width

    header_ymax = rect.y0 + height * header_frac
    footer_ymin = rect.y1 - height * footer_frac

    # Get structured text with positions
    d = page.get_text("dict")

    # Collect "lines" as concatenated spans, keeping a bbox per line.
    header_lines: List[Tuple[str, fitz.Rect]] = []
    footer_lines: List[Tuple[str, fitz.Rect]] = []

    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue  # non-text
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue

            # Compute a bbox for the line from its spans
            x0 = min(s["bbox"][0] for s in spans)
            y0 = min(s["bbox"][1] for s in spans)
            x1 = max(s["bbox"][2] for s in spans)
            y1 = max(s["bbox"][3] for s in spans)
            bbox = fitz.Rect(x0, y0, x1, y1)

            # Assign to header/footer if the line bbox lies in those zones
            if bbox.y1 <= header_ymax:
                header_lines.append((text, bbox))
            elif bbox.y0 >= footer_ymin:
                footer_lines.append((text, bbox))

    hits: List[PageNumberHit] = []
    hits.extend(
        _lines_to_hits(header_lines, pdf_page_index, region="header", page_width=width)
    )
    hits.extend(
        _lines_to_hits(footer_lines, pdf_page_index, region="footer", page_width=width)
    )
    return hits


def _lines_to_hits(
    lines: List[Tuple[str, "fitz.Rect"]],
    pdf_page_index: int,
    *,
    region: str,
    page_width: float,
) -> List[PageNumberHit]:
    hits: List[PageNumberHit] = []
    for text, bbox in lines:
        # Try to extract a page number candidate from this line.
        candidate = _extract_candidate_from_text(text)
        if candidate is None:
            continue

        kind, value, match_strength = candidate

        # Score heuristics
        # 1) Center-ish lines are often page numbers (but corners also common)
        center_x = (bbox.x0 + bbox.x1) / 2.0
        dist_to_center = abs(center_x - page_width / 2.0) / (page_width / 2.0)  # 0..1+
        center_score = max(0.0, 1.0 - dist_to_center)  # 1 at center, 0 at far edges

        # 2) Short lines tend to be page numbers
        length_penalty = min(
            1.0, max(0.0, (len(text) - 6) / 30.0)
        )  # grows after ~6 chars
        short_score = 1.0 - 0.7 * length_penalty

        # 3) Penalize date/time/version-y lines
        noise_pen = 0.0
        if _DATEISH_RE.search(text):
            noise_pen += 0.5
        if _TIMEISH_RE.search(text):
            noise_pen += 0.3
        if _VERSIONISH_RE.search(text):
            noise_pen += 0.3
        noise_score = max(0.0, 1.0 - noise_pen)

        # 4) Reward explicit "Page N" and "N of M" etc. via match_strength
        # match_strength in [0.7, 1.2] from extractor
        score = match_strength * (
            0.55 * short_score + 0.30 * center_score + 0.15 * noise_score
        )

        hits.append(
            PageNumberHit(
                pdf_page_index=pdf_page_index,
                region=region,
                raw_text=text,
                printed_kind=kind,
                printed_value=value,
                score=float(score),
            )
        )
    return hits


def _extract_candidate_from_text(text: str) -> Optional[Tuple[str, int, float]]:
    """
    Returns (kind, value, match_strength) where kind is 'arabic' or 'roman'.
    match_strength is a heuristic weight: higher for explicit patterns like 'Page 12'.
    """
    t = text.strip()

    m = _PAGE_NUM_TOKEN_RE.search(t)
    if not m:
        # Sometimes a line contains multiple tokens; consider isolated numeric token at end.
        # E.g., "Chapter 3" should not be page number; so be conservative here.
        return None

    if m.group("arabic1"):
        v = int(m.group("arabic1"))
        return "arabic", v, 1.2  # "Page N"
    if m.group("arabic2"):
        v = int(m.group("arabic2"))
        return "arabic", v, 1.1  # "N / M" or "N of M"
    if m.group("arabic3"):
        v = int(m.group("arabic3"))
        return "arabic", v, 1.0  # isolated
    if m.group("roman"):
        r = m.group("roman")
        if not _ROMAN_RE.match(r):
            return None
        v_r = _roman_to_int(r)
        if v_r is None:
            return None
        return "roman", v_r, 0.95

    return None


def _choose_best_hit(hits: List[PageNumberHit]) -> Optional[PageNumberHit]:
    if not hits:
        return None
    # Prefer higher score; if tie, prefer footer (common), then shorter raw_text.
    return max(
        hits,
        key=lambda h: (h.score, 1 if h.region == "footer" else 0, -len(h.raw_text)),
    )


def _infer_offset(
    per_page_best: Dict[int, PageNumberHit],
    *,
    kind: str,
) -> Tuple[Optional[int], float, int]:
    """
    Infer dominant offset for a given kind ('arabic' or 'roman').

    Returns:
        (offset, confidence, n_samples)

    offset definition:
        offset = (pdf_page_num_1based) - (printed_value)
    """
    offsets = []
    for page_index, hit in per_page_best.items():
        if hit.printed_kind != kind:
            continue
        pdf_num = page_index + 1
        offsets.append(pdf_num - hit.printed_value)

    n = len(offsets)
    if n == 0:
        return None, 0.0, 0

    c = Counter(offsets)
    offset, count = c.most_common(1)[0]

    # Confidence heuristic:
    # - dominance ratio
    # - and penalty if distribution is messy
    dominance = count / n
    spread_penalty = 0.0
    if len(c) > 1:
        # penalize if second most common is close
        second = c.most_common(2)[1][1]
        spread_penalty = min(0.25, (second / n) * 0.5)

    confidence = max(0.0, min(1.0, dominance - spread_penalty))

    # Also sanity check: if offset varies too wildly, refuse.
    if dominance < 0.55 and n >= 8:
        return None, confidence, n

    return int(offset), float(confidence), n


# ----------------------------
# Roman helpers
# ----------------------------

_ROMAN_MAP = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}


def _roman_to_int(s: str) -> Optional[int]:
    """
    Convert Roman numerals to int. Returns None on invalid forms.
    Accepts common lowercase too.
    """
    s = s.strip().upper()
    if not s or not _ROMAN_RE.match(s):
        return None

    total = 0
    prev = 0
    for ch in reversed(s):
        val = _ROMAN_MAP.get(ch)
        if val is None:
            return None
        if val < prev:
            total -= val
        else:
            total += val
            prev = val

    # Basic validity check: re-encode and compare (guards against weird invalid forms)
    if _int_to_roman(total) != s:
        return None
    return total


def _int_to_roman(n: int) -> str:
    if not (0 < n < 4000):
        return ""
    vals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    for v, sym in vals:
        while n >= v:
            out.append(sym)
            n -= v
    return "".join(out)


# ----------------------------
# Optional CLI
# ----------------------------


def _main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover
    import argparse
    import json

    p = argparse.ArgumentParser(description="Detect printed-page offset in a PDF.")
    p.add_argument("pdf", help="Path to PDF file")
    p.add_argument("--strategy", default="smart", choices=["smart", "all"])
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--json", action="store_true", help="Print full JSON result")

    args = p.parse_args(argv)

    res = detect_pdf_page_offset(
        args.pdf,
        sample_strategy=args.strategy,
        max_pages=args.max_pages,
    )

    if args.json:
        payload = {
            "page_count": res.page_count,
            "offset_arabic": res.offset_arabic,
            "offset_roman": res.offset_roman,
            "confidence": res.confidence,
            "samples_arabic": res.samples_arabic,
            "samples_roman": res.samples_roman,
            "per_page_printed": {str(k): v for k, v in res.per_page_printed.items()},
            "top_hits_preview": [
                {
                    "pdf_page_index": h.pdf_page_index,
                    "region": h.region,
                    "raw_text": h.raw_text,
                    "kind": h.printed_kind,
                    "value": h.printed_value,
                    "score": h.score,
                }
                for h in res.hits[:50]
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Pages: {res.page_count}")
        print(
            f"Arabic offset: {res.offset_arabic} (samples={res.samples_arabic}, confidence={res.confidence:.2f})"
        )
        print(f"Roman  offset: {res.offset_roman} (samples={res.samples_roman})")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
