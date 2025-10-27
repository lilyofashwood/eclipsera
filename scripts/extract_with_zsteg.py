#!/usr/bin/env python3
"""
Helper script to extract hidden text from PNG images using zsteg.
Usage: python scripts/extract_with_zsteg.py <path_to_png>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def is_printable_text(text: str) -> bool:
    """Check if text appears to be printable (not binary garbage)."""
    if not text:
        return False
    printable_chars = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
    ratio = printable_chars / len(text)
    return ratio > 0.7


def extract_with_zsteg(image_path: Path) -> None:
    """Extract hidden text from PNG using targeted zsteg selectors."""
    if not image_path.exists():
        print(f"Error: File not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    selectors = [
        ("b1,r,lsb,xy", "LSB Red"),
        ("b1,r,msb,xy", "MSB Red"),
        ("b1,g,lsb,xy", "LSB Green"),
        ("b1,b,lsb,xy", "LSB Blue"),
        ("b1,rgb,lsb,xy", "LSB RGB"),
    ]

    found_any = False

    for selector, label in selectors:
        try:
            result = subprocess.run(
                ["zsteg", "-E", selector, str(image_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                text = result.stdout.strip()
                # Filter out empty or binary-looking content
                if text and len(text) > 0 and is_printable_text(text[:200]):
                    print(f"\n=== {label} ({selector}) ===")
                    print(text)
                    found_any = True
        except subprocess.TimeoutExpired:
            print(f"Warning: Timeout for selector {selector}", file=sys.stderr)
        except FileNotFoundError:
            print("Error: zsteg not found. Please install zsteg (gem install zsteg)", file=sys.stderr)
            sys.exit(1)

    if not found_any:
        print("No hidden text detected in the image.")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_with_zsteg.py <path_to_png>", file=sys.stderr)
        sys.exit(1)

    image_path = Path(sys.argv[1])
    extract_with_zsteg(image_path)


if __name__ == "__main__":
    main()
