from __future__ import annotations

from typing import Any


def derive_values_for_doc(
    values_by_field: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Derive trusted values from other trusted values.
    Currently:
      sii_ratio_pct = 100 * eof_total / scr_total
    """
    out: list[dict[str, Any]] = []

    eof = values_by_field.get("eof_total")
    scr = values_by_field.get("scr_total")
    mcr = values_by_field.get("mcr_total")

    eof_val = eof.get("value_canonical") if eof else None
    scr_val = scr.get("value_canonical") if scr else None
    mcr_val = mcr.get("value_canonical") if mcr else None
    if (
        isinstance(eof_val, (str, float, int))
        and isinstance(scr_val, (str, float, int))
        and scr_val != 0
    ):
        ratio = round(100.0 * float(eof_val) / float(scr_val), 2)
        out.append(
            {
                "field_id": "sii_ratio_pct",
                "value_canonical": ratio,
                "unit": "%",
                "verified": True,
                "source_type": "derived",
                "source_note": "Eigenmittel / SCR",
            }
        )

    if (
        isinstance(eof_val, (str, float, int))
        and isinstance(mcr_val, (str, float, int))
        and mcr_val != 0
    ):
        ratio = round(100.0 * float(eof_val) / float(mcr_val), 2)
        out.append(
            {
                "field_id": "mcr_ratio_pct",
                "value_canonical": ratio,
                "unit": "%",
                "verified": True,
                "source_type": "derived",
                "source_note": "Eigenmittel / MCR",
            }
        )

    return out


def merge_final_values(
    *,
    doc_id: str,
    extracted_rows: list[dict[str, Any]],
    manual_overrides: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Precedence:
      manual override > derived > verified automatic extraction

    Important:
    - derived values are computed from the current trusted pool
      AFTER manual overrides for input fields have been applied
    - but a manual override for the derived field itself still wins
    """
    final_by_field: dict[str, dict[str, Any]] = {}

    # 1) start with verified extracted values
    for r in extracted_rows:
        if not r.get("verified"):
            continue
        field_id = r["field_id"]
        final_by_field[field_id] = {
            "doc_id": doc_id,
            "field_id": field_id,
            "value_canonical": r.get("value_canonical"),
            "unit": r.get("unit"),
            "verified": True,
            "source_type": "extracted",
            "source_note": None,
        }

    # 2) collect manual overrides for this doc
    manual_for_doc = [ov for ov in manual_overrides if ov.get("doc_id") == doc_id]
    manual_by_field = {ov["field_id"]: ov for ov in manual_for_doc}

    # 3) apply manual overrides FIRST so derived values use them as inputs
    for field_id, ov in manual_by_field.items():
        final_by_field[field_id] = {
            "doc_id": doc_id,
            "field_id": field_id,
            "value_canonical": ov.get("value_canonical"),
            "unit": ov.get("unit"),
            "verified": True,
            "source_type": "manual",
            "source_note": ov.get("note"),
        }

    # 4) derive values from the trusted pool (which now includes manual inputs)
    derived = derive_values_for_doc(final_by_field)

    # 5) apply derived values, but NEVER overwrite a manual override for the same field
    for d in derived:
        field_id = d["field_id"]
        if field_id in manual_by_field:
            continue
        final_by_field[field_id] = {
            "doc_id": doc_id,
            **d,
        }

    return list(final_by_field.values())
