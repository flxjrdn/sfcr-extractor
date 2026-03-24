from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_APP = PROJECT_ROOT / "sfcr" / "ui_app.py"
INSECURE_LOCALHOST_ENV = "SFCR_UI_ALLOW_INSECURE_LOCALHOST"
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in TRUTHY_VALUES


def build_streamlit_command(
    *,
    python_executable: str | None = None,
    allow_insecure_localhost: bool | None = None,
) -> list[str]:
    if python_executable is None:
        python_executable = sys.executable
    if allow_insecure_localhost is None:
        allow_insecure_localhost = is_truthy(os.getenv(INSECURE_LOCALHOST_ENV))

    cmd = [
        python_executable,
        "-m",
        "streamlit",
        "run",
        str(UI_APP.relative_to(PROJECT_ROOT)),
    ]
    if allow_insecure_localhost:
        cmd.extend(
            [
                "--server.address",
                "127.0.0.1",
                "--server.enableCORS",
                "false",
                "--server.enableXsrfProtection",
                "false",
            ]
        )
    return cmd


def main() -> None:
    subprocess.run(
        build_streamlit_command(),
        check=True,
        cwd=PROJECT_ROOT,
    )


if __name__ == "__main__":
    main()
