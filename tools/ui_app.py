from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from sfcr.db import (
    db_path_default,
    get_final_values_for_doc,
    get_summaries_for_doc,
    init_db,
    list_documents,
    load_catalog,
    load_extractions_from_dir,
    load_summaries_from_dir,
    rebuild_final_values,
)

# Field label mapping
FIELD_LABELS = {
    "scr_total": "SCR",
    "mcr_total": "MCR",
    "sii_ratio_pct": "Bedeckungsquote SCR",
    "mcr_ratio_pct": "Bedeckungsquote MCR",
    "eof_total": "Eigenmittel gesamt",
    "eof_t1": "Eigenmittel Tier 1",
    "eof_t2": "Eigenmittel Tier 2",
    "tech_provisions_total": "vt. Rückstellung",
}


# Optional: render PDF page images
def render_pdf_page(pdf_path: Path, page: int, zoom: float = 1.5) -> Optional[bytes]:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        if page < 1 or page > doc.page_count:
            return None
        pix = doc.load_page(page - 1).get_pixmap(
            matrix=fitz.Matrix(zoom, zoom), alpha=False
        )
        return pix.tobytes("png")
    except Exception:
        return None


def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        raise RuntimeError("This version of Streamlit has no rerun method.")


# Helper: display a nice field label
def display_field_name(field_id: str) -> str:
    return FIELD_LABELS.get(field_id, field_id)


def format_value_de(value: str | int | float | None, unit: str = "") -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return f"{value} {unit}".strip()

    # German notation: 1.234.567,89
    formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} {unit}".strip()


def main():
    st.set_page_config(page_title="SFCR Extractor Viewer", layout="wide")
    st.title("SFCR Viewer")

    db_path = db_path_default()

    # Documents sidebar
    docs = list_documents(db_path)
    display_names = [d["display_name"] for d in docs]
    st.sidebar.header("Dokumente")
    if not docs:
        st.sidebar.warning(
            "Keine Dokumente in DB gefunden. Klicke 'Init DB', dann 'Load from JSONL'."
        )

    display_name = st.sidebar.selectbox("Dokument auswählen", display_names, index=0)
    doc_id = None
    for d in docs:
        if d["display_name"] == display_name:
            doc_id = d["doc_id"]
            break

    # Filters
    st.sidebar.header("Filter")
    show_source = st.sidebar.checkbox("Zeige Text-Quelle")

    if st.sidebar.button(
        "1) Init DB", help="Create SQLite with tables/views if missing"
    ):
        p = init_db(db_path)
        st.success(f"DB initialized at {p}")
    if st.sidebar.button(
        "2) Load from JSONL", help="Load all *.extractions.jsonl into DB"
    ):
        n_docs = load_catalog()
        _, _ = load_extractions_from_dir()
        _, _ = load_summaries_from_dir()
        n_final = rebuild_final_values()
        st.success(f"Loaded {n_docs} docs and rebuilt {n_final} final values")
    if st.sidebar.button("↻ Refresh"):
        safe_rerun()

    if not docs:
        st.stop()

    st.header(f"{display_name}")

    # Summaries
    summaries = get_summaries_for_doc(doc_id)

    st.subheader("Zusammenfassungen")
    if not summaries:
        st.info(
            "Keine Zusammenfassungen für das Dokument gefunden. Erzeuge neue Zusammenfassungen und lade sie in die DB."
        )
    else:
        # Build stable tab order; fall back to title
        labels = [
            f"{s['section_id']} — {s.get('title') or ''}".strip(" —") for s in summaries
        ]
        tabs = st.tabs(labels)
        for tab, s in zip(tabs, summaries):
            with tab:
                meta = (
                    f"Pages {s.get('start_page')}–{s.get('end_page')}"
                    if s.get("start_page") and s.get("end_page")
                    else ""
                )
                if meta:
                    st.caption(meta)
                # The summaries are multi-line text; render as Markdown
                st.markdown(s.get("summary") or "_(empty)_")

    # Table
    rows = get_final_values_for_doc(doc_id, db_path)

    st.subheader("Werte")
    if not rows:
        st.info(
            "Für das Dokument wurden keine Werte in der DB gefunden. Extrahiere zunächst die Werte und lade sie dann in die DB."
        )
        st.stop()

    total = len(rows)
    verified = sum(1 for r in rows if r.get("verified"))
    st.write(f"Verifizierte Werte: **{verified}/{total}**")

    table_rows = []
    for r in rows:
        val = r.get("value_canonical")
        unit = r.get("unit") or ""
        value_display = format_value_de(val, unit)

        hint = ""
        source_type = r.get("source_type")
        source_note = r.get("source_note") or ""

        if source_type == "manual":
            hint = "Manuell geprüft"
        elif source_type == "derived":
            hint = "Abgeleitet"
        elif source_type == "extracted":
            hint = "Automatisch extrahiert"

        if source_note:
            hint = f"{hint} – {source_note}" if hint else source_note

        table_rows.append(
            {
                "Feld": display_field_name(r["field_id"]),
                "Wert": value_display,
                "Hinweise": hint,
            }
        )

    df = pd.DataFrame(table_rows)

    # Right-align the value column using HTML rendering (Streamlit dataframe ignores Styler alignment)
    styled = df.style.set_properties(subset=["Wert"], **{"text-align": "right"})

    st.markdown(
        styled.to_html(index=False),
        unsafe_allow_html=True,
    )

    if show_source:
        st.subheader("Textquellen")
        for r in rows:
            source_text = r.get("source_text")
            issues = r.get("issues") or ""
            if not source_text and not issues:
                continue
            header = f"{display_field_name(r['field_id'])}"
            with st.expander(header, expanded=False):
                st.write(f"Status: {r.get('status') or '—'}")
                st.write(f"Scale applied: `{r.get('scale_applied')}`")
                if source_text:
                    st.code(source_text)
                if issues:
                    st.warning(issues)


if __name__ == "__main__":
    main()
