from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent


def bundled_catalog_path() -> Path:
    return PACKAGE_ROOT / "data" / "catalog.csv"


def bundled_manual_overrides_path() -> Path:
    return PACKAGE_ROOT / "data" / "manual_overrides.yaml"


def bundled_fields_path() -> Path:
    return PACKAGE_ROOT / "extract" / "fields.yaml"


def bundled_policy_path() -> Path:
    return PACKAGE_ROOT / "resources" / "policy.md"


def bundled_ui_app_path() -> Path:
    return PACKAGE_ROOT / "ui_app.py"
