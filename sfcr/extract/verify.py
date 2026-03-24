from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .scale_detect import (
    ScaleHit,
    infer_scale_from_page_caption,
    infer_scale_from_source_text,
    infer_scale_near_source,
)
from .schema import ExtractionLLM, VerifiedExtraction, VerifierNote

DE_NBSP = "\u00a0"
LEADER_CHARS = r"\.\u2026\u00B7\u2219\u22EF\u2024\u2027\uf020·•⋯∙"

# Core numeric regex (German thousands '.' and decimal ',')
NUM_CORE = re.compile(
    r"""
    (?P<neg>\()?\s*
    (?P<int>(?:\d{1,3}(?:[ .\u202F\u2009]\d{3})+|\d+))
    (?P<dec>,\d+)?\s*
    (?P<pct>%){0,1}
    \)?                      # allow closing ')' for negative
    """,
    re.VERBOSE,
)

# Remove section/subsection references like "E.2.2", "A.1", "B.12.3"
_SECTION_CODE_RE = re.compile(r"\b[A-E]\.\d+(?:\.\d+)*\b", re.IGNORECASE)

# Number extractor that forbids mixing dot-grouping and space-grouping in ONE number
_NUM_EXTRACT_RE = re.compile(
    r"""
    (?P<neg>\()?\s*
    (?P<int>
        (?:\d{1,3}(?:\.\d{3})+)                # dot thousands: 1.234.567
        |
        (?:\d{1,3}(?:[ \u00a0\u202f\u2009]\d{3})+)  # space/nbsp thousands: 1 234 567 / 1 234 567 / 1 234 567
        |
        (?:\d+)                                # plain digits
    )
    (?P<dec>,\d+)?\s*
    (?P<pct>%){0,1}
    \)?                                        # allow closing ')' for negative
    """,
    re.VERBOSE,
)

ALLOWED_SCALES = {None, 1.0, 1000.0, 1_000_000.0, 1_000_000_000.0}

# Allowed thousands separators inside numbers
_SEP_CHARS = r"[ .\u00a0\u202f\u2009]"

# German number core (no sign here; parentheses handled outside)
_NUM_DE = rf"(?:\d{{1,3}}(?:{_SEP_CHARS}\d{{3}})+|\d+)"

# Optional decimal part
_NUM_DE_FULL = rf"(?:{_NUM_DE}(?:,\d+)?)"

_CURRENT_PREV_RE = re.compile(
    rf"(?P<curr>{_NUM_DE_FULL})\s*\(\s*(?P<prev>{_NUM_DE_FULL})\s*\)",
    re.VERBOSE,
)


_NO_SECTION = "no_section"
_NO_VALUE_OR_NOT_OK = "no_value_or_not_ok"
_VALUE_NOT_FOUND_IN_SOURCE_TEXT = "value_not_found_in_source_text"
_LOOKS_LIKE_PREV_YEAR_VALUE = "looks_like_prev_year_value"
_RATIO_MISMATCH = "ratio_mismatch"


@dataclass
class ParsedNumber:
    value: float
    is_percent: bool
    is_negative: bool


def _note(code: str) -> VerifierNote:
    return VerifierNote(code=code)


def _evidence_scale_hit(
    *, source_text: Optional[str], page_text: Optional[str]
) -> Optional[ScaleHit]:
    hit = infer_scale_from_source_text(source_text)
    if hit is not None:
        return hit

    if page_text:
        hit = infer_scale_near_source(page_text, source_text)
        if hit is not None:
            return hit

        hit = infer_scale_from_page_caption(page_text)
        if hit is not None:
            return hit

    return None


def _to_float_de(intpart: str, decpart: Optional[str]) -> float:
    # remove thousands separators and swap decimal comma
    i = (
        intpart.replace(".", "")
        .replace(" ", "")
        .replace(DE_NBSP, "")
        .replace("\u202f", "")
        .replace("\u2009", "")
    )
    d = decpart.replace(",", ".") if decpart else ""
    s = f"{i}{d}"
    return float(s)


def extract_numbers_de(text: str) -> List[float]:
    """
    Extract ALL German-formatted numbers from text.

    Returns a list of floats (unscaled), in textual order.
    Percent signs are ignored here; unit checks happen elsewhere.
    """
    if not text:
        return []

    # Normalize spaces like parse_number_de
    t = text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    t = re.sub(r"\s+", " ", t)

    # Remove SFCR section codes (E.2.2 etc.) so we don't pick up the "2" digits
    t = _SECTION_CODE_RE.sub(" ", t)

    values: List[float] = []

    for m in _NUM_EXTRACT_RE.finditer(t):
        try:
            val = _to_float_de(m.group("int"), m.group("dec"))
            if m.group("neg"):
                val = -val
            values.append(val)
        except Exception:
            continue

    return values


def _coerce_scale(x: Any) -> Optional[float]:
    """
    Accepts float/int/str like '1e3', '1000', or textual shorthands; returns float or None.
    """
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().lower()
        # common shorthands if they sneak in from prompts/yaml
        if s in {"teur", "tsd", "tausend", "1k"}:
            return 1e3
        if s in {"mio", "million", "1m"}:
            return 1e6
        if s in {"mrd", "milliarde", "1b"}:
            return 1e9
        try:
            return float(s)  # handles "1000", "1e3", "1e6"
        except ValueError:
            return None
    return None


def apply_scale(value: float, scale: Optional[float]) -> float:
    sc = _coerce_scale(scale)
    if sc is None:
        sc = 1.0
    return value * sc


def _parse_de_number(num_str: str) -> float:
    # same logic you already use elsewhere
    s = num_str.strip()
    s = s.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace(".", "").replace(" ", "")
    s = s.replace(",", ".")
    return float(s)


def extract_current_prev_pair(text: str) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    t = text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    t = re.sub(r"\s+", " ", t)

    m = _CURRENT_PREV_RE.search(t)
    if not m:
        return None

    try:
        curr = _parse_de_number(m.group("curr"))
        prev = _parse_de_number(m.group("prev"))
        return curr, prev
    except Exception:
        return None


# ---------------- Verification ----------------
def verify_extraction(
    *,
    doc_id: str,
    extr: ExtractionLLM,
    expected_unit: str | None = None,
    typical_scale: Optional[float],
    page_text_for_scale: str | None = None,
    ratio_check: Optional[Tuple[float, float]] = None,
) -> VerifiedExtraction:
    expected_unit_final = expected_unit if expected_unit in ("EUR", "%") else None
    base = VerifiedExtraction(
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

    # Gate
    if extr.status != "ok" or extr.value_unscaled is None:
        base.verifier_notes = [_note(_NO_VALUE_OR_NOT_OK)]
        return base

    notes: list[VerifierNote] = []

    # --- Scale resolution ----------------------------------------------------
    hit = _evidence_scale_hit(
        source_text=extr.source_text,
        page_text=page_text_for_scale,
    )

    model_scale = extr.scale if extr.scale in ALLOWED_SCALES else None
    if expected_unit_final is not None:
        unit_final = expected_unit_final
    else:
        unit_final = hit.unit if hit is not None and hit.unit is not None else extr.unit

    scale_final: float | None = None
    if unit_final != "%":
        if hit is not None and hit.scale is not None:
            scale_final = float(hit.scale)
        elif model_scale is not None:
            scale_final = float(model_scale)
        elif typical_scale is not None and unit_final == "EUR":
            scale_final = float(typical_scale)
        elif unit_final == "EUR":
            scale_final = 1.0

    # --- Canonical value from LLM value_unscaled ----------------------------
    value_canon: float | None = None

    if extr.value_unscaled is not None:
        if unit_final == "%":
            # For percent, scale is irrelevant: canonical == unscaled
            value_canon = float(extr.value_unscaled)
        else:
            # For EUR (and other numeric amounts), apply scale if known
            value_canon = (
                float(extr.value_unscaled) * float(scale_final)
                if scale_final is not None
                else None
            )

    if value_canon is not None:
        value_canon = round(value_canon, 2)

    # --- Determine unit -----------------------------------------------------
    unit = unit_final if value_canon is not None else None

    # --- Value consistency check against snippet (non-destructive) ----------
    if extr.source_text:
        pair = extract_current_prev_pair(
            extr.source_text
        )  # returns (curr, prev) or None
        candidates = []
        if pair:
            curr, prev = pair
            candidates.extend([curr, prev])
        candidates.extend(extract_numbers_de(extr.source_text))  # list[float]

        # Check if model value is among candidates (tolerance helps decimals)
        ok_match = any(
            abs(float(extr.value_unscaled) - c) <= 1e-6 * max(1.0, abs(c))
            for c in candidates
        )

        if not ok_match:
            # Not fatal (LLM might have normalized formatting), but should reduce confidence
            notes.append(_note(_VALUE_NOT_FOUND_IN_SOURCE_TEXT))

        # If we detect X(Y) and model picked Y (prev) instead of X, flag it
        if pair and abs(float(extr.value_unscaled) - pair[1]) <= 1e-6 * max(
            1.0, abs(pair[1])
        ):
            notes.append(_note(_LOOKS_LIKE_PREV_YEAR_VALUE))

    # --- Confidence ---------------------------------------------------------
    # Start low; add points for strong evidence.
    conf = 0.5

    # snippet present is good
    if extr.source_text:
        conf += 0.10

    # evidence page present is good
    if extr.evidence:
        conf += 0.10

    # penalize issues
    note_codes = [note.code for note in notes]
    if _VALUE_NOT_FOUND_IN_SOURCE_TEXT in note_codes:
        conf -= 0.35
    if _LOOKS_LIKE_PREV_YEAR_VALUE in note_codes:
        conf -= 0.25

    # Optional ratio check for percent fields
    if ratio_check and unit_final == "%":
        expected, tol = ratio_check
        if value_canon is not None and abs(value_canon - expected) <= tol:
            conf += 0.15
        else:
            notes.append(_note(_RATIO_MISMATCH))
            conf -= 0.30

    conf = round(conf, 2)
    conf = max(0.0, min(1.0, conf))

    # Decide verified: in your system "verified" really means "passed basic checks"
    blocking = any(
        note.code
        in (
            _VALUE_NOT_FOUND_IN_SOURCE_TEXT,
            _LOOKS_LIKE_PREV_YEAR_VALUE,
            _RATIO_MISMATCH,
        )
        for note in notes
    )
    verified = conf >= 0.50 and not blocking and unit_final is not None

    if unit_final == "%":
        scale_final = None

    return VerifiedExtraction(
        **{
            **base.model_dump(),
            "verified": verified,
            "value_canonical": value_canon,
            "unit": unit,
            "confidence": conf,
            "scale_applied": float(scale_final) if scale_final is not None else None,
            "verifier_notes": notes,
        }
    )
