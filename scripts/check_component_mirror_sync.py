"""Guard against drift between primary and mirror Blockheat component trees."""

from __future__ import annotations

from pathlib import Path

EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_NAMES = {".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc"}


def _iter_files(root: Path) -> set[Path]:
    files: set[Path] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDED_NAMES:
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.add(path.relative_to(root))
    return files


def compare_trees(primary: Path, mirror: Path) -> tuple[bool, list[str]]:
    """Compare two component trees and return (ok, details)."""
    details: list[str] = []

    primary_files = _iter_files(primary)
    mirror_files = _iter_files(mirror)

    only_primary = sorted(primary_files - mirror_files)
    only_mirror = sorted(mirror_files - primary_files)

    for rel in only_primary:
        details.append(f"missing in mirror: {rel}")
    for rel in only_mirror:
        details.append(f"missing in primary: {rel}")

    for rel in sorted(primary_files & mirror_files):
        primary_bytes = (primary / rel).read_bytes()
        mirror_bytes = (mirror / rel).read_bytes()
        if primary_bytes != mirror_bytes:
            details.append(f"content mismatch: {rel}")

    return (len(details) == 0), details


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    primary = repo_root / "custom_components" / "blockheat"
    mirror = repo_root / "homeassistant" / "custom_components" / "blockheat"

    if not primary.exists():
        print(f"Primary component directory not found: {primary}")
        return 1

    if not mirror.exists():
        print(f"Mirror directory not present, skipping drift check: {mirror}")
        return 0

    ok, details = compare_trees(primary, mirror)
    if ok:
        print("Blockheat component mirror is in sync.")
        return 0

    print("Blockheat component mirror drift detected:")
    for item in details:
        print(f"- {item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
