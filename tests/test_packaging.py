from __future__ import annotations

import ast
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from setuptools.build_meta import build_sdist

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "sfcr"
STDLIB_MODULES = set(sys.stdlib_module_names)
RUNTIME_IMPORT_TO_DISTRIBUTION = {
    "fitz": "pymupdf",
    "pydantic_settings": "pydantic-settings",
    "yaml": "pyyaml",
}
OPTIONAL_IMPORT_TO_EXTRA = {
    "openai": "openai",
}
BUNDLED_RUNTIME_RESOURCES = {
    "sfcr/data/catalog.csv",
    "sfcr/data/manual_overrides.yaml",
    "sfcr/extract/fields.yaml",
    "sfcr/ui_app.py",
}


def _load_project_table() -> dict:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        if "tomllib" in sys.modules:
            pyproject = tomllib.load(handle)
        else:
            pyproject = tomli.load(handle)
    return pyproject["project"]


def _requirement_name(spec: str) -> str:
    name_chars: list[str] = []
    for char in spec.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            name_chars.append(char)
            continue
        break
    return "".join(name_chars).lower().replace("_", "-")


def _iter_runtime_python_files() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "tests" not in path.parts and not path.name.startswith("test_")
    )


def _iter_third_party_import_roots() -> set[str]:
    imports: set[str] = set()
    for path in _iter_runtime_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])

    return {
        name
        for name in imports
        if name not in STDLIB_MODULES and name not in {"__future__", "sfcr"}
    }


def _build_wheel(tmp_path: Path) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(tmp_path),
            str(PROJECT_ROOT),
        ],
        check=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    wheels = sorted(tmp_path.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def _build_sdist(tmp_path: Path) -> Path:
    filename = build_sdist(str(tmp_path))
    sdist_path = tmp_path / filename
    assert sdist_path.is_file()
    return sdist_path


def test_runtime_dependencies_cover_actual_runtime_imports() -> None:
    project = _load_project_table()
    runtime_dependency_names = {
        _requirement_name(spec) for spec in project["dependencies"]
    }
    import_roots = _iter_third_party_import_roots()

    undeclared_runtime_imports = {
        name
        for name in import_roots
        if name not in OPTIONAL_IMPORT_TO_EXTRA
        and _requirement_name(RUNTIME_IMPORT_TO_DISTRIBUTION.get(name, name))
        not in runtime_dependency_names
    }

    assert undeclared_runtime_imports == set()
    assert "pytest" not in runtime_dependency_names


def test_dev_extra_contains_pytest() -> None:
    project = _load_project_table()
    dev_dependency_names = {
        _requirement_name(spec) for spec in project["optional-dependencies"]["dev"]
    }

    assert "pytest" in dev_dependency_names


def test_optional_runtime_imports_are_declared_via_matching_extras() -> None:
    project = _load_project_table()
    optional_dependencies = project["optional-dependencies"]
    import_roots = _iter_third_party_import_roots()

    for import_root, extra_name in OPTIONAL_IMPORT_TO_EXTRA.items():
        if import_root not in import_roots:
            continue

        extra_dependency_names = {
            _requirement_name(spec) for spec in optional_dependencies[extra_name]
        }
        expected_distribution = _requirement_name(
            RUNTIME_IMPORT_TO_DISTRIBUTION.get(import_root, import_root)
        )
        assert expected_distribution in extra_dependency_names


def test_requirements_txt_delegates_to_dev_extra() -> None:
    lines = [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert lines == ["-e .[dev]"]


def test_make_install_targets_use_documented_extras() -> None:
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "$(PYTHON) -m pip install -e '.[dev]'" in makefile
    assert "$(PYTHON) -m pip install -e '.[dev,openai]'" in makefile


def test_devcontainer_uses_declared_requirements_without_manual_runtime_pip_installs() -> (
    None
):
    devcontainer = (PROJECT_ROOT / ".devcontainer" / "devcontainer.json").read_text(
        encoding="utf-8"
    )

    assert "python3 -m pip install --user -r requirements.txt" in devcontainer
    assert "pip3 install --user streamlit" not in devcontainer


def test_runtime_resource_files_exist_inside_package_tree() -> None:
    missing = [
        resource
        for resource in BUNDLED_RUNTIME_RESOURCES
        if not (PROJECT_ROOT / resource).is_file()
    ]

    assert missing == []


def test_built_wheel_contains_all_bundled_runtime_resources(tmp_path: Path) -> None:
    wheel_path = _build_wheel(tmp_path)

    with zipfile.ZipFile(wheel_path) as wheel_zip:
        members = set(wheel_zip.namelist())

    missing = sorted(
        resource for resource in BUNDLED_RUNTIME_RESOURCES if resource not in members
    )
    assert missing == []


def test_built_sdist_contains_all_bundled_runtime_resources(tmp_path: Path) -> None:
    sdist_path = _build_sdist(tmp_path)

    with tarfile.open(sdist_path, "r:gz") as sdist_tar:
        members = {member.name for member in sdist_tar.getmembers() if member.isfile()}

    missing = sorted(
        resource
        for resource in BUNDLED_RUNTIME_RESOURCES
        if not any(
            member == resource or member.endswith(f"/{resource}") for member in members
        )
    )
    assert missing == []
