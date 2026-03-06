"""Validate that all release version files agree on one semver."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATHS = (
    ROOT / "custom_components" / "blockheat" / "manifest.json",
    ROOT / "homeassistant" / "custom_components" / "blockheat" / "manifest.json",
)
PYPROJECT_PATH = ROOT / "pyproject.toml"


def _validate_version(value: object, path: Path) -> str:
    if value is None:
        raise ValueError(f"Missing version in {path}")
    if not isinstance(value, str) or not SEMVER_RE.fullmatch(value):
        raise ValueError(f"Invalid version in {path}: {value!r}")
    return value


def load_manifest_version(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _validate_version(payload.get("version"), path)


def load_pyproject_version(path: Path) -> str:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"Missing [project] table in {path}")
    return _validate_version(project.get("version"), path)


def resolve_release_version(
    manifest_paths: Iterable[Path], pyproject_path: Path
) -> str:
    versions = {path: load_manifest_version(path) for path in manifest_paths}
    versions[pyproject_path] = load_pyproject_version(pyproject_path)

    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(
            f"{path.as_posix()}={version}" for path, version in sorted(versions.items())
        )
        raise ValueError(f"Version mismatch: {details}")

    return next(iter(unique_versions))


def main() -> int:
    try:
        version = resolve_release_version(MANIFEST_PATHS, PYPROJECT_PATH)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as err:
        print(err, file=sys.stderr)
        return 1

    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
