"""Test PNG decoding and text extraction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure app package is importable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.adapters.decoder_adapter import DecoderOptions, analyze_image
from app.adapters.encoder_adapter import EncoderOptions, encode_text_to_image


TEST_MESSAGE = "Eclipsera test: secure transmission confirmed."


@pytest.fixture
def sample_cover_image() -> bytes:
    """Create a simple test PNG image."""
    from PIL import Image
    import io

    # Create a small test image
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def test_png_overall_encode_decode(sample_cover_image: bytes) -> None:
    """Test encoding and decoding with LSB overall mode."""
    # Encode
    encode_result = encode_text_to_image(
        sample_cover_image,
        TEST_MESSAGE,
        options=EncoderOptions(
            twitter_safe=False,
            lsb_overall=True,
            channels=None,
            zlib=False,
        ),
    )

    assert encode_result["image_bytes"]
    assert encode_result["plane"]

    # Decode
    decode_result = analyze_image(
        encode_result["image_bytes"],
        options=DecoderOptions(filename="test_overall.png"),
    )

    # Check that we have recovered_texts
    assert "recovered_texts" in decode_result
    recovered_texts = decode_result["recovered_texts"]

    # At least one extraction should contain the message
    found = False
    for candidate in recovered_texts:
        text = candidate.get("text", "")
        if TEST_MESSAGE in text:
            found = True
            break

    assert found, f"Message not found in recovered texts: {recovered_texts}"


def test_png_channels_rgb_encode_decode(sample_cover_image: bytes) -> None:
    """Test encoding and decoding with RGB channels mode."""
    # Encode
    encode_result = encode_text_to_image(
        sample_cover_image,
        TEST_MESSAGE,
        options=EncoderOptions(
            twitter_safe=False,
            lsb_overall=False,
            channels=["R", "G", "B"],
            zlib=False,
        ),
    )

    assert encode_result["image_bytes"]

    # Decode
    decode_result = analyze_image(
        encode_result["image_bytes"],
        options=DecoderOptions(filename="test_channels.png"),
    )

    # Check that we have recovered_texts
    assert "recovered_texts" in decode_result
    recovered_texts = decode_result["recovered_texts"]

    # At least one extraction should contain the message
    found = False
    for candidate in recovered_texts:
        text = candidate.get("text", "")
        if TEST_MESSAGE in text:
            found = True
            break

    assert found, f"Message not found in recovered texts: {recovered_texts}"


def test_png_analyzers_skipped() -> None:
    """Test that steghide and outguess are marked as SKIPPED for PNG."""
    from PIL import Image
    import io

    # Create a simple PNG
    img = Image.new("RGB", (50, 50), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    # Analyze without deep mode
    result = analyze_image(png_bytes, options=DecoderOptions(filename="test.png", deep=False))

    # Check that steghide is skipped
    assert "steghide" in result["results"]
    assert result["results"]["steghide"]["status"] == "skipped"
    assert "PNG not supported" in result["results"]["steghide"]["reason"]

    # Analyze with deep mode
    result_deep = analyze_image(png_bytes, options=DecoderOptions(filename="test.png", deep=True))

    # Check that both steghide and outguess are skipped
    assert result_deep["results"]["steghide"]["status"] == "skipped"
    assert result_deep["results"]["outguess"]["status"] == "skipped"
    assert "PNG not supported" in result_deep["results"]["outguess"]["reason"]
