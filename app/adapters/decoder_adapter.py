"""Adapter for the vendor decoder (AperiSolve)."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

# Ensure the vendor decoder package is importable.
VENDOR_DECODER_DIR = Path(__file__).resolve().parents[2] / "vendor" / "decoder"
if str(VENDOR_DECODER_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DECODER_DIR))

from aperisolve.analyzers.binwalk import analyze_binwalk  # type: ignore  # noqa: E402
from aperisolve.analyzers.decomposer import analyze_decomposer  # type: ignore  # noqa: E402
from aperisolve.analyzers.exiftool import analyze_exiftool  # type: ignore  # noqa: E402
from aperisolve.analyzers.foremost import analyze_foremost  # type: ignore  # noqa: E402
from aperisolve.analyzers.outguess import analyze_outguess  # type: ignore  # noqa: E402
from aperisolve.analyzers.steghide import analyze_steghide  # type: ignore  # noqa: E402
from aperisolve.analyzers.strings import analyze_strings  # type: ignore  # noqa: E402
from aperisolve.analyzers.zsteg import analyze_zsteg  # type: ignore  # noqa: E402


@dataclass
class DecoderOptions:
    """Parameters controlling how the vendor analyzers are executed."""

    filename: str = "upload.png"
    password: Optional[str] = None
    deep: bool = False


def _sanitise_filename(name: str) -> str:
    candidate = Path(name).name or "upload.png"
    if "." not in candidate:
        return candidate + ".png"
    return candidate


def _detect_format(image_bytes: bytes) -> str:
    """Detect the image format based on magic bytes."""
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "PNG"
    elif image_bytes[:2] == b'\xff\xd8':
        return "JPEG"
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return "WEBP"
    elif image_bytes[:2] == b'BM':
        return "BMP"
    return "UNKNOWN"


def _extract_meta(image_bytes: bytes) -> Dict[str, Any]:
    """Extract metadata from the image."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return {
                "format": _detect_format(image_bytes),
                "width": img.width,
                "height": img.height,
                "size_bytes": len(image_bytes),
            }
    except Exception:
        return {
            "format": "UNKNOWN",
            "width": 0,
            "height": 0,
            "size_bytes": len(image_bytes),
        }


def _detect_png(image_bytes: bytes) -> bool:
    """Detect if the image is a PNG based on magic bytes."""
    return _detect_format(image_bytes) == "PNG"


def _extract_with_zsteg(image_path: Path) -> List[Dict[str, Any]]:
    """
    Attempt to extract hidden text from PNG using targeted zsteg selectors.
    Returns a list of candidates with their selector and extracted text.
    """
    candidates: List[Dict[str, Any]] = []
    selectors = [
        ("b1,r,lsb,xy", "LSB Red"),
        ("b1,r,msb,xy", "MSB Red"),
        ("b1,g,lsb,xy", "LSB Green"),
        ("b1,b,lsb,xy", "LSB Blue"),
        ("b1,rgb,lsb,xy", "LSB RGB"),
    ]

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
                if text and len(text) > 0 and _is_printable_text(text[:200]):
                    # Get byte representation for hex preview
                    text_bytes = text.encode('utf-8', errors='ignore')
                    hex_preview = ' '.join(f'{b:02x}' for b in text_bytes[:64])

                    candidates.append({
                        "selector": selector,
                        "label": label,
                        "text": text,
                        "source": "zsteg",
                        "bytes_len": len(text_bytes),
                        "hex_preview": hex_preview,
                    })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return candidates


def _normalize_text(text: str) -> str:
    """Normalize text for deduplication."""
    return text.strip().lower()


def _deduplicate_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate candidates based on normalized text."""
    seen = set()
    unique = []
    for candidate in candidates:
        normalized = _normalize_text(candidate.get("text", ""))
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(candidate)
    return unique


def _select_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Select the best candidate from the list (longest meaningful text)."""
    if not candidates:
        return None
    # Prefer longer texts as they're more likely to be the intended message
    return max(candidates, key=lambda c: len(c.get("text", "")))


def _is_printable_text(text: str) -> bool:
    """Check if text appears to be printable (not binary garbage)."""
    if not text:
        return False
    printable_chars = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
    ratio = printable_chars / len(text)
    return ratio > 0.7


def _load_results(results_path: Path) -> Dict[str, Any]:
    if not results_path.exists():
        return {}
    return json.loads(results_path.read_text(encoding="utf-8"))


def _collect_text_lines(results: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for data in results.values():
        output = data.get("output") if isinstance(data, dict) else None
        if isinstance(output, list):
            lines.extend(str(item) for item in output if item)
    return lines


def _resolve_plane_images(output_dir: Path, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    planes: List[Dict[str, Any]] = []
    deco = results.get("decomposer")
    if not isinstance(deco, dict):
        return planes
    if deco.get("status") != "ok":
        return planes

    images = deco.get("images", {})
    if not isinstance(images, dict):
        return planes

    for group_name, entries in images.items():
        if not isinstance(entries, list):
            continue
        for rel in entries:
            if not isinstance(rel, str):
                continue
            if not rel.startswith("/image/"):
                continue
            relative = rel[len("/image/") :]
            plane_path = output_dir.parent / relative
            if not plane_path.exists():
                continue
            image_bytes = plane_path.read_bytes()
            preview = Image.open(io.BytesIO(image_bytes))
            preview.load()
            planes.append(
                {
                    "label": f"{group_name}: {plane_path.name}",
                    "image_bytes": image_bytes,
                    "pil_image": preview,
                }
            )
    return planes


def _collect_artifacts(output_dir: Path, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for name, data in results.items():
        if not isinstance(data, dict):
            continue
        download = data.get("download")
        if not isinstance(download, str):
            continue
        stem = download.rsplit("/", 1)[-1]
        archive_path = output_dir / f"{stem}.7z"
        if not archive_path.exists():
            continue
        artifacts.append(
            {
                "source": name,
                "name": archive_path.name,
                "bytes": archive_path.read_bytes(),
            }
        )
    return artifacts


def _build_summary(results: Dict[str, Any]) -> str:
    parts: List[str] = []
    for analyzer, data in sorted(results.items()):
        if not isinstance(data, dict):
            continue
        status = data.get("status", "unknown")
        parts.append(f"{analyzer}: {status}")
    return "; ".join(parts) if parts else "No analyzers executed"


def _build_analyzer_details(results: Dict[str, Any], output_dir: Path) -> List[Dict[str, Any]]:
    """Build detailed analyzer information including log paths."""
    analyzers = []
    for name, data in sorted(results.items()):
        if not isinstance(data, dict):
            continue

        status = data.get("status", "unknown")
        reason = data.get("reason", "") or data.get("error", "")

        # Look for stdout/stderr files
        stdout_path = output_dir / f"{name}.stdout"
        stderr_path = output_dir / f"{name}.stderr"

        analyzer_info = {
            "name": name,
            "status": status,
            "reason": reason,
            "stdout_path": str(stdout_path) if stdout_path.exists() else None,
            "stderr_path": str(stderr_path) if stderr_path.exists() else None,
        }
        analyzers.append(analyzer_info)

    return analyzers


def _build_selectors_hit(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a list of selectors that produced results."""
    selectors = []
    for candidate in candidates:
        selectors.append({
            "tool": candidate.get("source", "unknown"),
            "selector": candidate.get("selector", ""),
            "bytes_len": candidate.get("bytes_len", 0),
        })
    return selectors


def analyze_image(
    image_bytes: bytes,
    *,
    options: DecoderOptions | Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute the vendor analyzers and collate their results."""

    if not image_bytes:
        raise ValueError("An image is required for analysis.")

    opts = DecoderOptions(**options) if isinstance(options, dict) else options
    if opts is None:
        opts = DecoderOptions()

    image_name = _sanitise_filename(opts.filename)

    supplemental_results: Dict[str, Dict[str, Any]] = {}
    is_png = _detect_png(image_bytes)

    with tempfile.TemporaryDirectory(prefix="eclipsera-decode-") as tmp:
        tmp_path = Path(tmp)
        output_dir = tmp_path / "analysis"
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir.parent / image_name
        image_path.write_bytes(image_bytes)

        # Pre-mark non-applicable analyzers for PNG images
        if is_png:
            supplemental_results["steghide"] = {
                "status": "skipped",
                "reason": "PNG not supported by steghide (JPEG/BMP only)",
            }
            if opts.deep:
                supplemental_results["outguess"] = {
                    "status": "skipped",
                    "reason": "PNG not supported by outguess (JPEG-centric)",
                }

        analyzers: List[tuple[str, Any, tuple[Any, ...]]] = [
            ("binwalk", analyze_binwalk, (image_path, output_dir)),
            ("decomposer", analyze_decomposer, (image_path, output_dir)),
            ("exiftool", analyze_exiftool, (image_path, output_dir)),
            ("foremost", analyze_foremost, (image_path, output_dir)),
            ("strings", analyze_strings, (image_path, output_dir)),
            ("zsteg", analyze_zsteg, (image_path, output_dir)),
        ]

        # Only run steghide on non-PNG images
        if not is_png:
            analyzers.append(("steghide", analyze_steghide, (image_path, output_dir, opts.password)))

        # Only run outguess on non-PNG images when deep mode is enabled
        if opts.deep and not is_png:
            analyzers.append(
                ("outguess", analyze_outguess, (image_path, output_dir, opts.password))
            )

        for name, func, func_args in analyzers:
            try:
                func(*func_args)
            except FileNotFoundError as exc:
                supplemental_results[name] = {
                    "status": "error",
                    "error": f"Dependency missing: {exc}",
                }
            except Exception as exc:  # pragma: no cover - defensive path
                supplemental_results[name] = {
                    "status": "error",
                    "error": str(exc),
                }

        # Attempt targeted extraction for PNG images
        recovered_texts: List[Dict[str, Any]] = []
        if is_png:
            recovered_texts = _extract_with_zsteg(image_path)

        results_path = output_dir / "results.json"
        results = _load_results(results_path)
        results.update(supplemental_results)

        # Extract metadata
        meta = _extract_meta(image_bytes)

        # Deduplicate candidates and select best
        candidates = _deduplicate_candidates(recovered_texts)
        best_candidate = _select_best_candidate(candidates)

        # Build analyzer details
        analyzers = _build_analyzer_details(results, output_dir)
        selectors_hit = _build_selectors_hit(candidates)

        planes = _resolve_plane_images(output_dir, results)
        artifacts = _collect_artifacts(output_dir, results)
        summary = _build_summary(results)
        text_lines = _collect_text_lines(results)

        log_lines: List[str] = []
        for analyzer, data in sorted(results.items()):
            if not isinstance(data, dict):
                continue
            status = data.get("status", "unknown")
            if status == "ok":
                output = data.get("output")
                snippet = ", ".join(output[:3]) if isinstance(output, list) else ""
                log_lines.append(f"[{analyzer}] ok {snippet}")
            elif status == "skipped":
                reason = data.get("reason", "Not applicable")
                log_lines.append(f"[{analyzer}] skipped: {reason}")
            else:
                log_lines.append(f"[{analyzer}] {status}: {data.get('error', '')}")

        return {
            # New structured fields
            "meta": meta,
            "best_candidate": best_candidate,
            "candidates": candidates,
            "analyzers": analyzers,
            "selectors_hit": selectors_hit,
            "bitplane_path": str(image_path),  # For lazy bitplane generation
            # Existing fields (for backward compatibility)
            "summary": summary,
            "planes": planes,
            "artifacts": artifacts,
            "logs": "\n".join(log_lines),
            "results": results,
            "text_lines": text_lines,
            "recovered_texts": recovered_texts,
        }
