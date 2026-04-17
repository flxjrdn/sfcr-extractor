from __future__ import annotations

import html

import streamlit as st

from sfcr.db import (
    db_path_default,
    get_final_values_for_doc,
    get_summaries_for_doc,
    init_db,
    list_documents,
)

# Field label mapping
FIELD_LABELS = {
    "scr_total": "SCR",
    "mcr_total": "MCR",
    "sii_ratio_pct": "Bedeckungsquote SCR",
    "eof_total": "Eigenmittel gesamt",
    "eof_t1": "Eigenmittel Tier 1",
    "eof_t2": "Eigenmittel Tier 2",
    "tech_provisions_total": "vt. Rückstellung",
}


FIELD_ORDER = [
    "sii_ratio_pct",
    "eof_total",
    "scr_total",
    "mcr_total",
    "eof_t1",
    "eof_t2",
    "tech_provisions_total",
]


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


def field_sort_key(field_id: str) -> tuple[int, str]:
    try:
        return FIELD_ORDER.index(field_id), field_id
    except ValueError:
        return len(FIELD_ORDER), field_id


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


def format_metric_value_compact(value: str | int | float | None, unit: str = "") -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return f"{value} {unit}".strip()

    if unit == "%":
        return format_value_de(num, unit)

    abs_num = abs(num)
    if abs_num >= 1_000_000_000:
        return format_value_de(num / 1_000_000_000, "Mrd €")
    if abs_num >= 1_000_000:
        return format_value_de(num / 1_000_000, "Mio €")
    return format_value_de(num, unit)


def render_metric_card(title: str, value: str) -> None:
    safe_title = html.escape(title, quote=True)
    safe_value = html.escape(value, quote=True)
    st.markdown(
        f"""
        <div style=\"padding: 1rem 1.1rem; border: 1px solid rgba(128, 128, 128, 0.22); border-radius: 12px; background: rgba(128, 128, 128, 0.04); min-height: 92px;\">
            <div style=\"font-size: 0.82rem; color: inherit; opacity: 0.75; margin-bottom: 0.35rem;\">{safe_title}</div>
            <div style=\"font-size: 1.5rem; font-weight: 600; color: inherit;\">{safe_value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_imprint_footer() -> None:
    st.markdown("---")
    with st.expander("Impressum", expanded=False):
        st.markdown(
            """
            **Name:**<br>
            Dr. Felix Jordan<br>

            **Anschrift:**<br>
            Kobellstr. 12<br>
            80336 München<br>

            **Kontakt:**<br>
            felix.jordan@web.de
            """,
            unsafe_allow_html=True,
        )


def build_final_values_table_rows(
    rows: list[dict[str, str | int | float | None]],
) -> list[dict[str, str]]:
    table_rows: list[dict[str, str]] = []
    for row in rows:
        val = row.get("value_canonical")
        unit = row.get("unit") or ""
        value_display = format_value_de(val, str(unit))

        hint = ""
        source_type = row.get("source_type")
        source_note = row.get("source_note") or ""

        if source_type == "derived":
            hint = "Abgeleitet"
        elif source_type == "extracted":
            hint = "Automatisch extrahiert"

        if source_note:
            hint = f"{hint} – {source_note}" if hint else str(source_note)

        table_rows.append(
            {
                "Feld": display_field_name(str(row["field_id"])),
                "Wert": value_display,
                "Hinweise": hint,
            }
        )

    return table_rows


def render_final_values_table(table_rows: list[dict[str, str]]) -> None:
    st.dataframe(
        table_rows,
        hide_index=True,
        use_container_width=True,
    )


def main():
    st.set_page_config(page_title="SFCR Extractor Viewer", layout="wide")
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
            }

            :root {
                --app-border: rgba(128, 128, 128, 0.22);
                --app-header-bg: rgba(128, 128, 128, 0.12);
                --app-row-alt: rgba(128, 128, 128, 0.06);
                --app-row-hover: rgba(128, 128, 128, 0.10);
            }

            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.95rem;
                color: inherit;
                background: transparent;
            }

            thead tr th {
                text-align: left;
                background: var(--app-header-bg);
                color: inherit;
                padding: 0.8rem 0.9rem;
                border-bottom: 1px solid var(--app-border);
                font-weight: 600;
            }

            tbody tr td {
                padding: 0.8rem 0.9rem;
                border-bottom: 1px solid var(--app-border);
                color: inherit;
                background: transparent;
            }

            tbody tr:nth-child(even) td {
                background: var(--app-row-alt);
            }

            tbody tr:hover td {
                background: var(--app-row-hover);
            }

            table a {
                color: inherit;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("SFCR Viewer")

    db_path = db_path_default()
    init_db(db_path)

    # Documents sidebar
    docs = list_documents(db_path)
    display_names = [d["display_name"] for d in docs]
    st.sidebar.header("Dokumente")
    if not docs:
        st.sidebar.warning(
            "Keine Dokumente in DB gefunden. Klicke 'Init DB', dann 'Load from JSONL'."
        )

    display_name = st.sidebar.selectbox("Dokument auswählen", display_names, index=0)
    selected_doc = next((d for d in docs if d["display_name"] == display_name), None)
    doc_id = selected_doc["doc_id"] if selected_doc else None
    pdf_url = selected_doc.get("pdf_url") if selected_doc else None

    if not docs:
        st.stop()

    rows = get_final_values_for_doc(doc_id, db_path)
    rows = sorted(rows, key=lambda r: field_sort_key(r["field_id"]))
    rows_by_field = {r["field_id"]: r for r in rows}

    header_left, header_right = st.columns([3, 1])
    with header_left:
        st.markdown(f"## {display_name}")
    with header_right:
        if pdf_url:
            st.link_button("Originalbericht öffnen", pdf_url, use_container_width=True)

    st.caption(
        "Die dargestellten Kennzahlen wurden automatisiert aus öffentlich zugänglichen SFCR-Berichten extrahiert. "
        "Trotz sorgfältiger Verarbeitung und zusätzlicher Validierung kann nicht ausgeschlossen werden, dass einzelne Werte fehlerhaft sind. "
        "Die Inhalte dienen ausschließlich zu Informations- und Analysezwecken. Für verbindliche Informationen wird auf die jeweiligen Originalberichte der Unternehmen verwiesen."
    )

    metric_cols = st.columns(4)
    metric_fields = [
        ("Bedeckungsquote SCR", "sii_ratio_pct"),
        ("Eigenmittel gesamt", "eof_total"),
        ("SCR", "scr_total"),
        ("Vt. Rückstellungen", "tech_provisions_total"),
    ]
    for col, (label, field_id) in zip(metric_cols, metric_fields):
        row = rows_by_field.get(field_id)
        value = format_metric_value_compact(
            (row or {}).get("value_canonical"), (row or {}).get("unit") or ""
        )
        with col:
            render_metric_card(label, value)

    st.markdown("### Kennzahlen")

    table_rows = build_final_values_table_rows(rows)

    summaries = get_summaries_for_doc(doc_id)

    render_final_values_table(table_rows)

    st.markdown("### Zusammenfassungen")
    if not summaries:
        st.info(
            "Keine Zusammenfassungen für das Dokument gefunden. Erzeuge neue Zusammenfassungen und lade sie in die DB."
        )
    else:
        labels = [
            f"{s['section_id']} — {s.get('title') or ''}".strip(" —") for s in summaries
        ]
        tabs = st.tabs(labels)
        for tab, s in zip(tabs, summaries):
            with tab:
                meta = (
                    f"Seiten {s.get('start_page')}–{s.get('end_page')}"
                    if s.get("start_page") and s.get("end_page")
                    else ""
                )
                if meta:
                    st.caption(meta)
                st.markdown(s.get("summary") or "_(empty)_")

    render_imprint_footer()


if __name__ == "__main__":
    main()
