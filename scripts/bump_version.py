"""Bump version across all release files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATHS = (ROOT / "custom_components" / "blockheat" / "manifest.json",)
PYPROJECT_PATH = ROOT / "pyproject.toml"


def update_manifest(path: Path, version: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = version
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"  Updated {path.relative_to(ROOT)}")


def update_pyproject(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'^version\s*=\s*"[^"]*"', re.MULTILINE)
    if not pattern.search(text):
        print(f"  Warning: no version line found in {path.relative_to(ROOT)}")
        return
    new_text = pattern.sub(f'version = "{version}"', text, count=1)
    path.write_text(new_text, encoding="utf-8")
    print(f"  Updated {path.relative_to(ROOT)}")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <version>", file=sys.stderr)
        return 1

    version = sys.argv[1]
    if not SEMVER_RE.fullmatch(version):
        print(f"Invalid semver: {version!r}", file=sys.stderr)
        return 1

    print(f"Bumping version to {version}:")
    for path in MANIFEST_PATHS:
        update_manifest(path, version)
    update_pyproject(PYPROJECT_PATH, version)

    print("\nNext steps:")
    files = " ".join(
        str(p.relative_to(ROOT)) for p in (*MANIFEST_PATHS, PYPROJECT_PATH)
    )
    print(f"  git add {files}")
    print(f'  git commit -m "chore: bump version to {version}"')
    print(f"  git tag v{version}")
    print("  git push && git push --tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
