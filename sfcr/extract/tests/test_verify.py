from __future__ import annotations

from sfcr.extract.schema import Evidence, ExtractionLLM
from sfcr.extract.verify import (
    _LOOKS_LIKE_PREV_YEAR_VALUE,
    _VALUE_NOT_FOUND_IN_SOURCE_TEXT,
    _coerce_scale,
    apply_scale,
    extract_current_prev_pair,
    extract_numbers_de,
    verify_extraction,
)


def _note_codes(out) -> list[str]:
    return out.verifier_notes


def _mk_extr(
    *,
    field_id: str = "x",
    status: str = "ok",
    value_unscaled: float | None = 1.0,
    unit: str | None = "EUR",
    scale: float | str | None = None,
    source_text: str | None = None,
    evidence: list[Evidence] | None = None,
) -> ExtractionLLM:
    return ExtractionLLM(
        field_id=field_id,
        status=status,
        value_unscaled=value_unscaled,
        scale=scale,
        unit=unit,
        source_text=source_text,
        evidence=evidence or [Evidence(page=1, ref=None, snippet_hash="deadbeef")],
    )


# ---------------- low-level helpers ----------------


def test_coerce_scale_accepts_numbers_and_strings():
    assert _coerce_scale(None) is None
    assert _coerce_scale(1000) == 1000.0
    assert _coerce_scale(1e6) == 1_000_000.0
    assert _coerce_scale("1000") == 1000.0
    assert _coerce_scale("1e3") == 1000.0
    assert _coerce_scale("1e6") == 1_000_000.0
    assert _coerce_scale(" TEUR ") == 1000.0
    assert _coerce_scale("mio") == 1_000_000.0
    assert _coerce_scale("mrd") == 1_000_000_000.0
    assert _coerce_scale("nonsense") is None


def test_apply_scale_defaults_to_1_when_none():
    assert apply_scale(12.0, None) == 12.0
    assert apply_scale(12.0, "1e3") == 12_000.0


def test_extract_numbers_de_handles_spaces_dots_decimals_and_parentheses_negative():
    txt = "Wert: 1 312 850 und 1.111.111 sowie 12,5 und (133 333) und 391%."
    vals = extract_numbers_de(txt)
    # Order matters: first occurrence is "1 312 850"
    assert vals[0] == 1312850.0
    assert 1111111.0 in vals
    assert 12.5 in vals
    assert -133333.0 in vals
    # Percent is still parsed as number; unit handling is elsewhere
    assert 391.0 in vals


def test_extract_current_prev_pair_parses_current_and_prev_with_spaces_and_dots():
    txt = "Die Mindestkapitalanforderung beträgt 123 456 (133 333) TEUR."
    pair = extract_current_prev_pair(txt)
    assert pair == (123456.0, 133333.0)

    txt2 = "Solvabilitätskapitalanforderung 1.234.567 (1.111.111) EUR"
    pair2 = extract_current_prev_pair(txt2)
    assert pair2 == (1234567.0, 1111111.0)


def test_extract_current_prev_pair_none_when_absent():
    assert extract_current_prev_pair("kein paar hier") is None
    assert extract_current_prev_pair("") is None
    assert extract_current_prev_pair(None) is None  # type: ignore[arg-type]


# ---------------- verify_extraction ----------------


def test_verify_gate_not_ok_or_missing_value():
    extr = _mk_extr(status="not_found", value_unscaled=None)
    out = verify_extraction(doc_id="d", extr=extr, typical_scale=1000.0)
    assert out.verified is False
    assert out.value_canonical is None
    assert _note_codes(out) == "no_value_or_not_ok"

    extr2 = _mk_extr(status="ok", value_unscaled=None)
    out2 = verify_extraction(doc_id="d", extr=extr2, typical_scale=1000.0)
    assert out2.verified is False
    assert _note_codes(out2) == "no_value_or_not_ok"

    extr3 = _mk_extr(
        status="not_found",
        value_unscaled=None,
        unit=None,
        scale=None,
        source_text="SCR 10 TEUR, alternativ SCR 12 TEUR",
    )
    out3 = verify_extraction(doc_id="d", extr=extr3, typical_scale=1000.0)
    assert out3.status == "not_found"
    assert out3.verified is False
    assert out3.value_canonical is None
    assert _note_codes(out3) == "no_value_or_not_ok"


def test_verify_uses_model_scale_as_fallback_without_evidence_signal():
    extr = _mk_extr(
        field_id="scr_total",
        value_unscaled=10.0,
        unit="EUR",
        scale=1000.0,
        source_text="SCR 10",
    )
    out = verify_extraction(doc_id="d", extr=extr, typical_scale=1_000_000.0)
    assert out.scale_applied == 1000.0
    assert out.value_canonical == 10_000.0
    assert out.verified is True


def test_verify_ignores_model_scale_if_not_allowed_and_uses_inferred_or_default():
    extr = _mk_extr(
        field_id="scr_total",
        value_unscaled=10.0,
        unit="EUR",
        scale=1234.0,  # invalid
        source_text="SCR 10 TEUR",
    )
    out = verify_extraction(doc_id="d", extr=extr, typical_scale=1_000_000.0)
    # From row snippet, infer_scale should detect TEUR => 1000
    assert out.scale_applied == 1000.0
    assert out.value_canonical == 10_000.0
    assert out.verified is True


def test_verify_assumes_scale_1_for_eur_if_no_scale_anywhere():
    extr = _mk_extr(
        field_id="eof_total",
        value_unscaled=1234.0,
        unit="EUR",
        scale=None,
        source_text="Eigenmittel insgesamt 1 234 EUR",
    )
    out = verify_extraction(
        doc_id="d", extr=extr, typical_scale=None, page_text_for_scale=None
    )
    assert out.scale_applied == 1.0
    assert out.value_canonical == 1234.0
    # verified depends on confidence; with row EUR it should be >= 0.5
    assert out.confidence >= 0.5
    assert out.verified is True


def test_verify_value_not_found_in_source_text_penalizes_confidence():
    extr = _mk_extr(
        field_id="x",
        value_unscaled=999.0,
        unit="EUR",
        scale=None,
        source_text="Der Wert beträgt 123 456 TEUR.",
    )
    out = verify_extraction(doc_id="d", extr=extr, typical_scale=1000.0)
    assert _note_codes(out) == _VALUE_NOT_FOUND_IN_SOURCE_TEXT
    assert out.confidence < 0.5
    assert out.verified is False


def test_verify_detects_prev_year_value_selected():
    extr = _mk_extr(
        field_id="mcr_total",
        value_unscaled=133333.0,  # previous year (in parentheses)
        unit="EUR",
        scale=1000.0,
        source_text="Die Mindestkapitalanforderung beträgt 123 456 (133 333) TEUR.",
    )
    out = verify_extraction(doc_id="d", extr=extr, typical_scale=1000.0)
    assert _note_codes(out) == _LOOKS_LIKE_PREV_YEAR_VALUE
    assert out.confidence < 0.5
    assert out.verified is False


def test_verify_ratio_check_boosts_confidence_for_percent_fields():
    extr = _mk_extr(
        field_id="sii_ratio_pct",
        value_unscaled=391.0,
        unit="%",
        scale=None,
        source_text="Solvabilitätsquote 391%",
    )
    out = verify_extraction(
        doc_id="d", extr=extr, typical_scale=None, ratio_check=(391.0, 0.2)
    )
    assert out.value_canonical == 391.0
    assert out.verified is True
    assert out.confidence >= 0.5


def test_verify_ratio_check_adds_mismatch_note():
    extr = _mk_extr(
        field_id="sii_ratio_pct",
        value_unscaled=389.0,
        unit="%",
        scale=None,
        source_text="Solvabilitätsquote 389%",
    )
    out = verify_extraction(
        doc_id="d", extr=extr, typical_scale=None, ratio_check=(391.0, 0.2)
    )
    assert "Verhältnis" in _note_codes(out)


def test_verify_returns_structured_verifier_notes_in_order():
    extr = _mk_extr(
        field_id="sii_ratio_pct",
        value_unscaled=390.0,
        unit="%",
        scale=None,
        source_text="Solvabilitätsquote 389%",
    )
    out = verify_extraction(
        doc_id="d", extr=extr, typical_scale=None, ratio_check=(391.0, 0.2)
    )

    assert _VALUE_NOT_FOUND_IN_SOURCE_TEXT in _note_codes(out)
    assert "Verhältnis" in _note_codes(out)
