#!/usr/bin/env python3
"""Verify vendored encoder/decoder files against MANIFEST.sha256."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO_ROOT / "vendor"
MANIFEST_PATH = VENDOR_DIR / "MANIFEST.sha256"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest for *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, str]:
    """Load expected hashes from MANIFEST.sha256."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Missing manifest at {MANIFEST_PATH}")

    entries: dict[str, str] = {}
    for raw_line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError(f"Malformed manifest line: {raw_line!r}")
        digest, rel_path = parts
        entries[rel_path] = digest
    return entries


def compute_current_hashes() -> dict[str, str]:
    """Compute current hashes for all files in vendor/ (excluding manifest)."""
    if not VENDOR_DIR.exists():
        raise FileNotFoundError(f"Vendor directory not found at {VENDOR_DIR}")

    hashes: dict[str, str] = {}
    for path in sorted(VENDOR_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.name == MANIFEST_PATH.name and path.parent == VENDOR_DIR:
            # Skip the manifest itself from the recomputed hashes.
            continue
        rel_path = f"vendor/{path.relative_to(VENDOR_DIR).as_posix()}"
        hashes[rel_path] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print matching entries as well as failures.",
    )
    args = parser.parse_args()

    expected = load_manifest()
    current = compute_current_hashes()

    ok = True

    for rel_path in sorted(set(expected) | set(current)):
        exp = expected.get(rel_path)
        cur = current.get(rel_path)
        if exp != cur:
            ok = False
            if exp is None:
                print(f"[ERROR] New file missing from manifest: {rel_path}")
            elif cur is None:
                print(f"[ERROR] File missing locally: {rel_path}")
            else:
                print(f"[ERROR] Hash mismatch for {rel_path}: expected {exp}, got {cur}")
        elif args.verbose:
            print(f"[OK] {rel_path}")

    if not ok:
        print("Vendor integrity check failed.", file=sys.stderr)
        return 1

    if args.verbose:
        print("Vendor integrity check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
