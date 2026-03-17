from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_release_version.py"
SPEC = importlib.util.spec_from_file_location("release_version_validation", SCRIPT_PATH)
assert SPEC
assert SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

resolve_release_version = MODULE.resolve_release_version


def _write_manifest(path: Path, version: str | None) -> Path:
    payload: dict[str, object] = {"domain": "blockheat"}
    if version is not None:
        payload["version"] = version
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_pyproject(path: Path, version: str) -> Path:
    path.write_text(
        "\n".join(
            [
                "[project]",
                'name = "blockheat"',
                f'version = "{version}"',
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_resolve_release_version_returns_synced_version(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "manifest.json", "0.2.0")
    pyproject = _write_pyproject(tmp_path / "pyproject.toml", "0.2.0")

    assert resolve_release_version((manifest,), pyproject) == "0.2.0"


def test_resolve_release_version_rejects_pyproject_mismatch(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "manifest.json", "0.2.0")
    pyproject = _write_pyproject(tmp_path / "pyproject.toml", "0.3.0")

    with pytest.raises(ValueError, match="Version mismatch"):
        resolve_release_version((manifest,), pyproject)


@pytest.mark.parametrize(
    ("manifest_version", "pyproject_version", "message"),
    [
        (None, "0.2.0", "Missing version"),
        ("beta", "0.2.0", "Invalid version"),
        ("0.2.0", "beta", "Invalid version"),
    ],
)
def test_resolve_release_version_rejects_invalid_or_missing_versions(
    tmp_path: Path,
    manifest_version: str | None,
    pyproject_version: str,
    message: str,
) -> None:
    manifest = _write_manifest(tmp_path / "manifest.json", manifest_version)
    pyproject = _write_pyproject(tmp_path / "pyproject.toml", pyproject_version)

    with pytest.raises(ValueError, match=message):
        resolve_release_version((manifest,), pyproject)
