#!/usr/bin/env python3
"""Exercise the encoder and decoder against the provided test fixtures."""

from __future__ import annotations

import io
import json
import shutil
import sys
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.adapters.decoder_adapter import DecoderOptions, analyze_image  # noqa: E402
from app.adapters.encoder_adapter import EncoderOptions, encode_text_to_image  # noqa: E402

TEST_ROOT = REPO_ROOT / "encoding_decoding_tests"
COVER_DIR = TEST_ROOT / "sample_photos_to_encode_text_to_LSB"
ENCODED_DIR = TEST_ROOT / "sample_encrypted_photos_LSB_text"
DECODE_DIR = TEST_ROOT / "LSB_text_output_within_encrypted_photos"
RESULTS_DIR = TEST_ROOT / "results"

GOLDEN_MESSAGE = "Eclipsera golden vector v1: hello, moon."


@dataclass
class EncodeScenario:
    label: str
    encoder: EncoderOptions
    deep_analysis: bool = False
    password: Optional[str] = None


SCENARIOS: List[EncodeScenario] = [
    EncodeScenario(
        label="overall",
        encoder=EncoderOptions(twitter_safe=True, lsb_overall=True, channels=None, zlib=False),
    ),
    EncodeScenario(
        label="channels_rgb",
        encoder=EncoderOptions(
            twitter_safe=True,
            lsb_overall=False,
            channels=["R", "G", "B"],
            zlib=False,
        ),
    ),
    EncodeScenario(
        label="rgb_zlib_deep",
        encoder=EncoderOptions(
            twitter_safe=True,
            lsb_overall=False,
            channels=["R", "G", "B"],
            zlib=True,
        ),
        deep_analysis=True,
    ),
]


def ensure_directories() -> None:
    for path in (COVER_DIR, ENCODED_DIR, DECODE_DIR, RESULTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def sanitise_filename(label: str) -> str:
    safe = label.replace(" ", "_").replace(":", "_")
    safe = safe.replace("/", "_")
    return safe


def save_plane_images(subdir: Path, planes: Iterable[dict]) -> None:
    for index, plane in enumerate(planes, start=1):
        label = sanitise_filename(str(plane.get("label", f"plane_{index}")))
        plane_path = subdir / f"{index:02d}_{label}.png"
        plane_path.write_bytes(plane["image_bytes"])


def save_artifacts(subdir: Path, artifacts: Iterable[dict]) -> None:
    for artifact in artifacts:
        artifact_path = subdir / sanitise_filename(artifact["name"])
        artifact_path.write_bytes(artifact["bytes"])


def write_summary(subdir: Path, summary: str, analyzers: dict, message_found: bool) -> None:
    lines = [summary, "", f"Message detected: {'yes' if message_found else 'no'}", ""]
    lines.append("Analyzer statuses:")
    for name, data in sorted(analyzers.items()):
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        lines.append(f"- {name}: {status}")
    (subdir / "summary.txt").write_text("\n".join(lines), encoding="utf-8")


def write_text_lines(subdir: Path, text_lines: Iterable[str]) -> None:
    lines = [line for line in text_lines if line]
    if not lines:
        return
    (subdir / "text_lines.txt").write_text("\n".join(lines), encoding="utf-8")


def _bits_to_bytes(bits: List[int]) -> bytes:
    payload = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i : i + 8]
        if len(chunk) < 8:
            break
        value = 0
        for bit in chunk:
            value = (value << 1) | bit
        payload.append(value)
    return bytes(payload)


def attempt_recover_message(image_bytes: bytes, plane: str, zipped: bool) -> Optional[str]:
    if not plane:
        return None

    order = [c for c in "RGBA" if c in plane]
    if not order:
        order = ["R", "G", "B"]

    from PIL import Image  # Local import to avoid hard dependency during module load

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGBA")
        width, height = img.size
        bits: List[int] = []
        for y in range(height):
            for x in range(width):
                r, g, b, a = img.getpixel((x, y))
                channel_map = {"R": r, "G": g, "B": b, "A": a}
                for channel in order:
                    bits.append(channel_map[channel] & 1)
                    if len(bits) >= 8 and bits[-8:] == [0] * 8:
                        data_bits = bits[:-8]
                        payload = _bits_to_bytes(data_bits)
                        try:
                            if zipped:
                                payload = zlib.decompress(payload)
                            return payload.decode("utf-8", errors="ignore")
                        except Exception:
                            return None
        payload = _bits_to_bytes(bits)
        try:
            if zipped:
                payload = zlib.decompress(payload)
            return payload.decode("utf-8", errors="ignore")
        except Exception:
            return None


def run_roundtrips() -> dict:
    ensure_directories()
    cover_images = sorted(
        [p for p in COVER_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    )
    if not cover_images:
        raise FileNotFoundError(f"No cover images found in {COVER_DIR}")

    runs = []

    for cover_path in cover_images:
        cover_bytes = cover_path.read_bytes()
        for scenario in SCENARIOS:
            encoded_filename = f"{cover_path.stem}__{scenario.label}.png"
            encoded_output = ENCODED_DIR / encoded_filename

            encode_result = encode_text_to_image(
                cover_bytes,
                GOLDEN_MESSAGE,
                options=scenario.encoder,
            )
            encoded_output.write_bytes(encode_result["image_bytes"])

            recovered_message = attempt_recover_message(
                encode_result["image_bytes"],
                plane=encode_result.get("plane", ""),
                zipped=scenario.encoder.zlib,
            )

            decode_result = analyze_image(
                encode_result["image_bytes"],
                options=DecoderOptions(
                    filename=encoded_filename,
                    password=scenario.password,
                    deep=scenario.deep_analysis,
                ),
            )

            # Check for message in various sources
            recovered_texts = decode_result.get("recovered_texts", [])
            recovered_from_zsteg = None
            for candidate in recovered_texts:
                text = candidate.get("text", "")
                if GOLDEN_MESSAGE in text:
                    recovered_from_zsteg = text
                    break

            expected_core = GOLDEN_MESSAGE.rstrip(".")
            message_found = bool(
                any(GOLDEN_MESSAGE in line for line in decode_result.get("text_lines", []))
                or GOLDEN_MESSAGE in decode_result.get("logs", "")
                or (recovered_message == GOLDEN_MESSAGE)
                or (recovered_message is not None and expected_core in recovered_message)
                or (recovered_from_zsteg is not None and GOLDEN_MESSAGE in recovered_from_zsteg)
            )

            decode_subdir = DECODE_DIR / Path(encoded_filename).stem
            if decode_subdir.exists():
                shutil.rmtree(decode_subdir)
            decode_subdir.mkdir(parents=True, exist_ok=True)

            save_plane_images(decode_subdir, decode_result.get("planes", []))
            save_artifacts(decode_subdir, decode_result.get("artifacts", []))
            write_text_lines(decode_subdir, decode_result.get("text_lines", []))
            write_summary(
                decode_subdir,
                decode_result.get("summary", ""),
                decode_result.get("results", {}),
                message_found,
            )

            run_record = {
                "cover_image": str(cover_path.relative_to(TEST_ROOT)),
                "encoded_image": str(encoded_output.relative_to(TEST_ROOT)),
                "scenario": {
                    "label": scenario.label,
                    "options": {
                        "twitter_safe": scenario.encoder.twitter_safe,
                        "lsb_overall": scenario.encoder.lsb_overall,
                        "channels": list(scenario.encoder.channels) if scenario.encoder.channels else None,
                        "zlib": scenario.encoder.zlib,
                        "deep_analysis": scenario.deep_analysis,
                    },
                },
                "decode_summary": decode_result.get("summary", ""),
                "message_found": message_found,
                "plane": encode_result.get("plane"),
                "recovered_message": recovered_message,
                "recovered_from_zsteg": recovered_from_zsteg,
                "recovered_texts_count": len(recovered_texts),
            }

            runs.append(run_record)

    overall_pass = all(run["message_found"] for run in runs)
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "overall_pass": overall_pass,
        "total_runs": len(runs),
        "successful_runs": sum(1 for run in runs if run["message_found"]),
        "runs": runs,
    }


def write_reports(data: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = ["# Eclipsera Encode→Decode Report", ""]
    lines.append(f"Generated: {data['generated_at']}")
    lines.append(
        f"Overall status: {'✅ PASS' if data['overall_pass'] else '❌ FAIL'}"
    )
    lines.append(
        f"Successful runs: {data['successful_runs']} / {data['total_runs']}"
    )
    lines.append("")
    lines.append("| Cover | Variant | Message Found | Recovered Text | Notes |")
    lines.append("| --- | --- | --- | --- | --- |")
    for run in data["runs"]:
        cover = run["cover_image"]
        variant = run["scenario"]["label"]
        status = "✅" if run["message_found"] else "⚠️"

        # Show recovered text from zsteg or fallback message
        recovered = run.get("recovered_from_zsteg") or run.get("recovered_message") or ""
        if recovered:
            recovered_preview = recovered[:50] + "..." if len(recovered) > 50 else recovered
            recovered_preview = recovered_preview.replace("|", "\\|")  # Escape pipes for markdown
        else:
            recovered_preview = "(none)"

        notes = run["decode_summary"] or ""
        lines.append(f"| {cover} | {variant} | {status} | {recovered_preview} | {notes} |")

    (RESULTS_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = run_roundtrips()
    write_reports(data)
    print(
        f"Completed {data['total_runs']} runs — "
        f"{'PASS' if data['overall_pass'] else 'FAIL'}"
    )


if __name__ == "__main__":
    main()
