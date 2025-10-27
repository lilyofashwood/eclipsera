"""Thin wrapper around the vendor encoder implementation."""

from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from PIL import Image

# Load the vendor encoder module without modifying its source.
VENDOR_ENCODER_DIR = Path(__file__).resolve().parents[2] / "vendor" / "encoder"
_SPEC = importlib.util.spec_from_file_location(
    "eclipsera_vendor_encoder", VENDOR_ENCODER_DIR / "app.py"
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - defensive guard
    raise ImportError("Unable to load vendor encoder module.")
_VENDOR_ENCODER = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("eclipsera_vendor_encoder", _VENDOR_ENCODER)
_SPEC.loader.exec_module(_VENDOR_ENCODER)

# Re-export the functions we need so we can call them verbatim.
compress_image_before_encoding = _VENDOR_ENCODER.compress_image_before_encoding
encode_text_into_plane = _VENDOR_ENCODER.encode_text_into_plane
encode_zlib_into_image = _VENDOR_ENCODER.encode_zlib_into_image


@dataclass
class EncoderOptions:
    """Options shared with the Streamlit UI."""

    twitter_safe: bool = True
    lsb_overall: bool = False
    channels: Iterable[str] | None = None
    zlib: bool = False
    output_basename: str = "eclipsera_encoded.png"


def _resolve_plane(
    image: Image.Image, *, lsb_overall: bool, channels: Iterable[str] | None
) -> str:
    """Translate UI toggles into the vendor plane string."""
    if lsb_overall:
        # Vendor UI treated "overall" as RGB even when alpha is present.
        return "RGB"

    ordered = ["R", "G", "B", "A"]
    if not channels:
        return "RGB"

    unique: List[str] = []
    for channel in channels:
        ch = channel.upper()
        if ch in ordered and ch not in unique:
            unique.append(ch)

    if not unique:
        return "RGB"
    return "".join(unique)


def encode_text_to_image(
    cover_image_bytes: bytes,
    text: str,
    *,
    options: EncoderOptions | Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Encode *text* into the provided cover image using the vendor encoder."""

    if not cover_image_bytes:
        raise ValueError("A cover image is required.")

    if not text:
        raise ValueError("No text supplied for embedding.")

    opts = EncoderOptions(**options) if isinstance(options, dict) else options
    if opts is None:
        opts = EncoderOptions()

    with tempfile.TemporaryDirectory(prefix="eclipsera-encode-") as tmp:
        tmp_path = Path(tmp)
        cover_path = tmp_path / "cover.png"

        # Normalize the user-provided image to PNG so the vendor helper can work with it.
        with Image.open(io.BytesIO(cover_image_bytes)) as img:
            img.save(cover_path, format="PNG")

        working_path = tmp_path / "working.png"

        if opts.twitter_safe:
            compress_image_before_encoding(str(cover_path), str(working_path))
        else:
            shutil.copyfile(cover_path, working_path)

        with Image.open(working_path) as work_img:
            plane = _resolve_plane(
                work_img, lsb_overall=opts.lsb_overall, channels=opts.channels
            )

            if opts.zlib:
                encode_zlib_into_image(
                    work_img,
                    text.encode("utf-8"),
                    str(working_path),
                    plane=plane,
                )
            else:
                encode_text_into_plane(
                    work_img,
                    text,
                    str(working_path),
                    plane=plane,
                )

        encoded_bytes = working_path.read_bytes()
        preview = Image.open(io.BytesIO(encoded_bytes))
        preview.load()

        return {
            "filename": opts.output_basename,
            "image_bytes": encoded_bytes,
            "pil_image": preview,
            "plane": plane,
            "options_applied": {
                "twitter_safe": opts.twitter_safe,
                "lsb_overall": opts.lsb_overall,
                "channels": list(opts.channels) if opts.channels else None,
                "zlib": opts.zlib,
            },
        }
