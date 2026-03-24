from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _SidebarStub:
    def header(self, *args, **kwargs) -> None:
        pass

    def warning(self, *args, **kwargs) -> None:
        pass

    def selectbox(self, *args, **kwargs):
        return None


class _StopCalled(RuntimeError):
    pass


class _StreamlitStub:
    def __init__(self) -> None:
        self.dataframe_calls: list[tuple[object, dict[str, object]]] = []
        self.markdown_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.sidebar = _SidebarStub()

    def dataframe(self, data, **kwargs) -> None:
        self.dataframe_calls.append((data, kwargs))

    def markdown(self, *args, **kwargs) -> None:
        self.markdown_calls.append((args, kwargs))

    def set_page_config(self, *args, **kwargs) -> None:
        pass

    def title(self, *args, **kwargs) -> None:
        pass

    def stop(self) -> None:
        raise _StopCalled()


def _load_ui_app(streamlit_stub: _StreamlitStub):
    module_name = "_test_sfcr_ui_app"
    sys.modules.pop(module_name, None)
    sys.modules["streamlit"] = streamlit_stub
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_ROOT / "sfcr" / "ui_app.py",
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_final_values_table_rows_preserves_literal_html_in_notes():
    ui_app = _load_ui_app(_StreamlitStub())

    rows = [
        {
            "field_id": "scr_total",
            "value_canonical": 1234,
            "unit": "EUR",
            "source_type": "extracted",
            "source_note": "<script>alert(1)</script><b>fett</b>",
        }
    ]

    assert ui_app.build_final_values_table_rows(rows) == [
        {
            "Feld": "SCR",
            "Wert": "1.234,00 EUR",
            "Hinweise": "Automatisch extrahiert – <script>alert(1)</script><b>fett</b>",
        }
    ]


def test_render_final_values_table_uses_streamlit_dataframe():
    streamlit_stub = _StreamlitStub()
    ui_app = _load_ui_app(streamlit_stub)
    table_rows = [
        {
            "Feld": "SCR",
            "Wert": "1.234,00 EUR",
            "Hinweise": "<script>alert(1)</script>",
        }
    ]

    ui_app.render_final_values_table(table_rows)

    assert streamlit_stub.dataframe_calls == [
        (
            table_rows,
            {
                "hide_index": True,
                "use_container_width": True,
            },
        )
    ]
    assert streamlit_stub.markdown_calls == []


def test_render_metric_card_escapes_dynamic_values():
    streamlit_stub = _StreamlitStub()
    ui_app = _load_ui_app(streamlit_stub)

    ui_app.render_metric_card("<b>Titel</b>", "<script>alert(1)</script>")

    assert len(streamlit_stub.markdown_calls) == 1
    args, kwargs = streamlit_stub.markdown_calls[0]
    rendered_html = args[0]

    assert "&lt;b&gt;Titel&lt;/b&gt;" in rendered_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered_html
    assert "<script>alert(1)</script>" not in rendered_html
    assert kwargs == {"unsafe_allow_html": True}


def test_main_initializes_default_db_before_listing_documents(monkeypatch, tmp_path: Path):
    streamlit_stub = _StreamlitStub()
    ui_app = _load_ui_app(streamlit_stub)
    db_path = tmp_path / "artifacts" / "sfcr.sqlite"
    captured: dict[str, Path] = {}

    monkeypatch.setattr(ui_app, "db_path_default", lambda: db_path)
    monkeypatch.setattr(
        ui_app,
        "init_db",
        lambda path: captured.setdefault("init_db", path),
    )
    monkeypatch.setattr(
        ui_app,
        "list_documents",
        lambda path: captured.setdefault("list_documents", path) and [],
    )

    with pytest.raises(_StopCalled):
        ui_app.main()

    assert captured["init_db"] == db_path
    assert captured["list_documents"] == db_path
