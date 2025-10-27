"""Streamlit entrypoint for the unified Eclipsera experience."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules["app"] = importlib.import_module("app")

import streamlit as st

from app.adapters.decoder_adapter import DecoderOptions, analyze_image
from app.adapters.encoder_adapter import EncoderOptions, encode_text_to_image
from app.ui.components import (
    inject_css,
    render_artifact_downloads,
    render_plane_gallery,
    render_text_findings,
)

st.set_page_config(page_title="Eclipsera", page_icon="🌙", layout="wide")
inject_css()

st.title("Eclipsera")
st.caption("A calm Tokyo café for clandestine pixels.")

uploaded_file = st.file_uploader(
    "Upload a carrier/target image",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=False,
    help="Use the same image for encrypting or decrypting hidden payloads.",
)

disabled = uploaded_file is None

mode = st.radio(
    "Mode",
    options=["Encrypt", "Decrypt"],
    horizontal=True,
    index=0,
    disabled=disabled,
    key="mode_choice",
)

if "encode_result" not in st.session_state:
    st.session_state["encode_result"] = None
if "decode_result" not in st.session_state:
    st.session_state["decode_result"] = None

cover_bytes: bytes | None = uploaded_file.getvalue() if uploaded_file else None
filename = uploaded_file.name if uploaded_file else "upload.png"
studio_stem = Path(filename).stem

st.markdown("---")

if mode == "Encrypt":
    text_to_hide = st.text_area(
        "Text to hide",
        placeholder="Eclipsera golden vector v1: hello, moon.",
        disabled=disabled,
        height=180,
    )

    cola, colb, colc = st.columns(3)
    with cola:
        twitter_safe = st.checkbox(
            "Twitter-safe",
            value=True,
            help="Re-compress the image to stay under ~900 KB before embedding.",
            disabled=disabled,
        )
        zlib_toggle = st.checkbox(
            "zlib compress",
            value=False,
            help="Compress the message before hiding it.",
            disabled=disabled,
        )
    with colb:
        lsb_overall = st.checkbox(
            "LSB overall",
            value=False,
            help="Blend across every available channel.",
            disabled=disabled,
        )
    with colc:
        channels = st.multiselect(
            "Per-channel",
            options=["R", "G", "B", "A"],
            default=["R", "G", "B"],
            help="Select precise channels when not using LSB overall.",
            disabled=disabled or lsb_overall,
        )

    generate_clicked = st.button(
        "Generate",
        type="primary",
        use_container_width=True,
        disabled=disabled,
    )

    if generate_clicked:
        if cover_bytes is None:
            st.warning("Please upload a cover image before encoding.")
        else:
            try:
                message = text_to_hide or ""
                if not message.strip():
                    raise ValueError("Please enter a message to hide.")
                options = EncoderOptions(
                    twitter_safe=twitter_safe,
                    lsb_overall=lsb_overall,
                    channels=channels,
                    zlib=zlib_toggle,
                    output_basename=f"{studio_stem}_encoded.png",
                )
                result = encode_text_to_image(
                    cover_bytes,
                    message,
                    options=options,
                )
            except ValueError as exc:
                st.warning(str(exc))
                st.session_state["encode_result"] = None
            except Exception as exc:  # pragma: no cover - surfaced to UI
                st.error(f"Encoding failed: {exc}")
                st.session_state["encode_result"] = None
            else:
                st.session_state["encode_result"] = result
                st.success("Message embedded. Preview below.")

    encode_result: Dict[str, Any] | None = st.session_state.get("encode_result")
    if encode_result:
        st.image(
            encode_result["image_bytes"],
            caption=f"Encoded preview — plane {encode_result['plane']}",
            use_column_width=True,
        )
        st.download_button(
            "Download encoded image",
            data=encode_result["image_bytes"],
            file_name=encode_result["filename"],
            mime="image/png",
            key="download-encoded",
        )
        st.json(encode_result.get("options_applied", {}))

else:  # Decrypt
    password = st.text_input(
        "Password (optional)",
        value="",
        type="password",
        disabled=disabled,
        help="Passphrase for tools like steghide/outguess when needed.",
    )
    deep_analysis = st.checkbox(
        "Deep analysis",
        value=False,
        help="Runs outguess in addition to the standard analyzers.",
        disabled=disabled,
    )

    analyze_clicked = st.button(
        "Analyze",
        type="primary",
        use_container_width=True,
        disabled=disabled,
    )

    if analyze_clicked:
        if cover_bytes is None:
            st.warning("Please upload an image to analyze.")
        else:
            try:
                options = DecoderOptions(
                    filename=filename,
                    password=password or None,
                    deep=deep_analysis,
                )
                result = analyze_image(cover_bytes, options=options)
            except ValueError as exc:
                st.warning(str(exc))
                st.session_state["decode_result"] = None
            except Exception as exc:  # pragma: no cover
                st.error(f"Analysis failed: {exc}")
                st.session_state["decode_result"] = None
            else:
                st.session_state["decode_result"] = result
                st.success("Analysis finished.")

    decode_result: Dict[str, Any] | None = st.session_state.get("decode_result")
    if decode_result:
        st.markdown(f"**Summary:** {decode_result['summary']}")

        errors = [
            (name, data)
            for name, data in decode_result.get("results", {}).items()
            if isinstance(data, dict) and data.get("status") != "ok"
        ]
        if errors:
            for name, data in errors:
                st.warning(f"{name}: {data.get('error', 'Unknown error')}")

        render_text_findings(decode_result.get("text_lines", []))
        render_plane_gallery(decode_result.get("planes", []))
        render_artifact_downloads(decode_result.get("artifacts", []))

        with st.expander("Analyzer logs", expanded=False):
            st.text(decode_result.get("logs", ""))
