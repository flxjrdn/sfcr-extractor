from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sfcr.utils.pdf_page_offset import detect_pdf_page_offset


@dataclass(frozen=True)
class PdfPageOffsetInfo:
    page_count: Optional[int]
    offset_arabic: Optional[int]
    offset_roman: Optional[int]
    confidence: float


def load_pdf_page_offset_info(pdf_path: Path | str) -> PdfPageOffsetInfo:
    try:
        offset = detect_pdf_page_offset(str(pdf_path))
    except RuntimeError:
        return PdfPageOffsetInfo(
            page_count=None,
            offset_arabic=None,
            offset_roman=None,
            confidence=0.0,
        )

    if offset is None:
        return PdfPageOffsetInfo(
            page_count=None,
            offset_arabic=None,
            offset_roman=None,
            confidence=0.0,
        )

    return PdfPageOffsetInfo(
        page_count=offset.page_count,
        offset_arabic=offset.offset_arabic,
        offset_roman=offset.offset_roman,
        confidence=offset.confidence,
    )


def resolve_pdf_page_span(
    start_page: int,
    end_page: int,
    *,
    offset_arabic: Optional[int] = None,
    page_count: Optional[int] = None,
) -> tuple[int, int]:
    start = int(start_page)
    end = int(end_page)

    if offset_arabic is not None:
        start += offset_arabic
        end += offset_arabic

    if page_count is not None:
        start = min(max(1, start), page_count)
        end = min(max(1, end), page_count)
    else:
        start = max(1, start)
        end = max(1, end)

    if end < start:
        end = start

    return start, end
