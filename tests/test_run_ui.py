from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_run_ui():
    module_name = "_test_scripts_run_ui"
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_ROOT / "scripts" / "run_ui.py",
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_is_truthy_accepts_common_opt_in_values():
    run_ui = _load_run_ui()

    assert run_ui.is_truthy("1")
    assert run_ui.is_truthy(" true ")
    assert run_ui.is_truthy("YES")
    assert run_ui.is_truthy("On")
    assert not run_ui.is_truthy(None)
    assert not run_ui.is_truthy("0")
    assert not run_ui.is_truthy("false")


def test_build_streamlit_command_is_secure_by_default(monkeypatch):
    run_ui = _load_run_ui()
    monkeypatch.delenv(run_ui.INSECURE_LOCALHOST_ENV, raising=False)

    cmd = run_ui.build_streamlit_command(python_executable="python-test")

    assert cmd == [
        "python-test",
        "-m",
        "streamlit",
        "run",
        "sfcr/ui_app.py",
    ]


def test_build_streamlit_command_requires_explicit_opt_in_for_insecure_localhost(
    monkeypatch,
):
    run_ui = _load_run_ui()
    monkeypatch.setenv(run_ui.INSECURE_LOCALHOST_ENV, "1")

    cmd = run_ui.build_streamlit_command(python_executable="python-test")

    assert cmd == [
        "python-test",
        "-m",
        "streamlit",
        "run",
        "sfcr/ui_app.py",
        "--server.address",
        "127.0.0.1",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
    ]


def test_devcontainer_uses_secure_ui_runner():
    content = (PROJECT_ROOT / ".devcontainer" / "devcontainer.json").read_text(
        encoding="utf-8"
    )

    assert "python3 scripts/run_ui.py" in content
    assert "--server.enableCORS false" not in content
    assert "--server.enableXsrfProtection false" not in content


def test_makefile_ui_target_uses_shared_runner():
    content = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "$(PYTHON) scripts/run_ui.py" in content


def test_readme_documents_explicit_insecure_localhost_opt_in():
    content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "For normal local development" in content
    assert "SFCR_UI_ALLOW_INSECURE_LOCALHOST=1 make ui" in content
    assert "Do not use it for shared, remote, or forwarded environments." in content
