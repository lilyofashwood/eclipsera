"""Streamlit entrypoint for the unified Eclipsera experience."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict

import streamlit as st

from app.adapters.decoder_adapter import DecoderOptions, analyze_image
from app.adapters.encoder_adapter import EncoderOptions, encode_text_to_image
from app.ui.components import (
    inject_css,
    render_all_candidates,
    render_analyzer_status_table,
    render_analyzers_table,
    render_artifact_downloads,
    render_bitplane_explorer,
    render_channel_text_dumps,
    render_diagnostics,
    render_diagnostics_detailed,
    render_meta,
    render_plane_gallery,
    render_recovered_text,
    render_recovered_text_primary,
    render_summary_tab,
    render_text_findings,
)

st.set_page_config(page_title="eclipsera", page_icon="🌘", layout="wide")
inject_css()

# Branding with eclipse glyph
st.markdown("# 🌘 eclipsera")
st.caption("A calm Tokyo café for clandestine pixels.")

uploaded_file = st.file_uploader(
    "Upload a carrier/target image",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=False,
    help="Use the same image for encrypting or decrypting hidden payloads.",
)

# Show thumbnail preview when file is uploaded
if uploaded_file:
    col_preview, col_meta = st.columns([1, 2])
    with col_preview:
        st.image(uploaded_file, caption="Uploaded image", use_column_width=True)
    with col_meta:
        from PIL import Image
        img_bytes = uploaded_file.getvalue()
        try:
            with Image.open(io.BytesIO(img_bytes)) as img:
                st.caption(f"**Format:** {img.format}")
                st.caption(f"**Size:** {img.width} × {img.height}")
                st.caption(f"**File size:** {len(img_bytes) / 1024:.1f} KB")
        except Exception:
            pass

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
        st.info("⚠️ **Important:** Use the downloaded PNG directly. Re-saving through Preview, Twitter, iMessage, or screenshot tools may alter LSB data and destroy the hidden message.")
        st.json(encode_result.get("options_applied", {}))

else:  # Decrypt
    col1, col2, col3 = st.columns(3)
    with col1:
        password = st.text_input(
            "Password (optional)",
            value="",
            type="password",
            disabled=disabled,
            help="Passphrase for tools like steghide/outguess when needed.",
        )
    with col2:
        deep_analysis = st.checkbox(
            "Deep analysis",
            value=False,
            help="Runs outguess in addition to the standard analyzers.",
            disabled=disabled,
        )
    with col3:
        show_everything = st.checkbox(
            "Show everything",
            value=True,
            help="Display all analysis tabs including bit-planes and channel dumps.",
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
        # Primary results - always visible
        st.markdown("---")

        # Display recovered text prominently
        render_recovered_text_primary(decode_result)

        # Display all candidates
        render_all_candidates(decode_result)

        st.markdown("---")

        # Tabbed interface for detailed analysis
        tabs = st.tabs([
            "Summary",
            "Analyzers",
            "Bit-plane Explorer",
            "Channel Text Dumps",
            "Diagnostics",
            "Logs"
        ])

        with tabs[0]:  # Summary
            render_summary_tab(decode_result)

        with tabs[1]:  # Analyzers
            render_analyzers_table(decode_result)

        with tabs[2]:  # Bit-plane Explorer
            render_bitplane_explorer(decode_result)

        with tabs[3]:  # Channel Text Dumps
            render_channel_text_dumps(decode_result)

        with tabs[4]:  # Diagnostics
            render_diagnostics_detailed(decode_result)

        with tabs[5]:  # Logs
            st.text_area(
                "Full analyzer logs",
                value=decode_result.get("logs", "No logs available"),
                height=400,
                disabled=True,
                label_visibility="collapsed",
            )
            st.download_button(
                "Download full logs",
                data=decode_result.get("logs", ""),
                file_name="analyzer_logs.txt",
                mime="text/plain",
                key="download-logs",
            )

        # Legacy views (for backward compatibility, hidden in expander)
        with st.expander("🔧 Legacy views", expanded=False):
            render_analyzer_status_table(decode_result.get("results", {}))
            render_text_findings(decode_result.get("text_lines", []))
            render_plane_gallery(decode_result.get("planes", []))
            render_artifact_downloads(decode_result.get("artifacts", []))
