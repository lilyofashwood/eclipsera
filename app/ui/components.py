"""Reusable UI helpers for the Streamlit application."""

from __future__ import annotations

import base64
import io
import subprocess
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import streamlit as st
from PIL import Image


def inject_css() -> None:
    """Load the app-specific CSS into the current Streamlit page."""
    css_path = Path(__file__).with_name("styles.css")
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_plane_gallery(planes: Iterable[dict]) -> None:
    planes = list(planes)
    if not planes:
        st.caption("No bit-plane previews were generated for this run.")
        return

    st.subheader("Bit-plane previews")
    cols_per_row = 3
    for index in range(0, len(planes), cols_per_row):
        row = planes[index : index + cols_per_row]
        columns = st.columns(len(row))
        for column, plane in zip(columns, row):
            column.image(
                plane["image_bytes"],
                caption=plane["label"],
                use_column_width=True,
            )


def render_artifact_downloads(artifacts: Iterable[dict]) -> None:
    artifacts = list(artifacts)
    if not artifacts:
        st.caption("No downloadable artifacts were produced.")
        return

    st.subheader("Extracted artifacts")
    for artifact in artifacts:
        label = f"Download {artifact['name']} ({artifact['source']})"
        st.download_button(
            label,
            data=artifact["bytes"],
            file_name=artifact["name"],
            mime="application/x-7z-compressed",
            key=f"artifact-{artifact['source']}-{artifact['name']}",
        )


def render_text_findings(text_lines: Iterable[str], *, header: str = "Text findings") -> None:
    lines = [line for line in text_lines if line]
    if not lines:
        st.caption("No candidate text snippets detected yet.")
        return

    st.subheader(header)
    snippet = "\n".join(lines[:50])
    st.code(snippet)


def render_meta(meta: Dict[str, Any]) -> None:
    """Display image metadata in a compact format."""
    format_name = meta.get("format", "unknown")
    width = meta.get("width", 0)
    height = meta.get("height", 0)
    size_bytes = meta.get("size_bytes", 0)
    size_mb = size_bytes / (1024 * 1024)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Format", format_name)
    with col2:
        st.metric("Dimensions", f"{width}×{height}")
    with col3:
        st.metric("Size", f"{size_mb:.2f} MB")
    with col4:
        st.metric("Bytes", f"{size_bytes:,}")


def render_recovered_text_primary(result: Dict[str, Any]) -> None:
    """Display the primary recovered text card with copy and save buttons."""
    best_candidate = result.get("best_candidate")
    if not best_candidate:
        st.info("No hidden text detected. Try adjusting options or check diagnostics.")
        return

    st.subheader("🔓 recovered text")
    text = best_candidate.get("text", "")

    # Large read-only text area
    st.text_area(
        "Recovered message",
        value=text,
        height=200,
        disabled=True,
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.button(
            "📋 Copy",
            key="copy-recovered-text",
            help="Copy to clipboard",
            on_click=lambda: st.write(""),  # Placeholder for copy action
        )
    with col2:
        st.download_button(
            "💾 Save .txt",
            data=text.encode("utf-8"),
            file_name="recovered_text.txt",
            mime="text/plain",
            key="save-recovered-text",
        )


def render_all_candidates(result: Dict[str, Any]) -> None:
    """Display all candidate texts with their metadata."""
    candidates = result.get("candidates", [])
    if not candidates:
        return

    st.subheader("all candidates")

    for idx, candidate in enumerate(candidates):
        source = candidate.get("source", "unknown")
        selector = candidate.get("selector", "")
        text = candidate.get("text", "")
        bytes_len = candidate.get("bytes_len", 0)

        with st.expander(f"#{idx+1} — {source} ({selector}) — {bytes_len} bytes", expanded=(idx == 0)):
            st.text_area(
                f"Candidate {idx+1}",
                value=text,
                height=100,
                disabled=True,
                label_visibility="collapsed",
                key=f"candidate-text-{idx}",
            )
            st.button(
                "📋 Copy",
                key=f"copy-candidate-{idx}",
                help="Copy to clipboard",
            )


def _generate_lsb_visualization(image_path: Path | str | None, channels: Iterable[str]) -> Optional[bytes]:
    """Generate a binary visualization for the provided channels' LSB."""

    if image_path is None:
        return None

    try:
        with Image.open(image_path) as src:
            img = src.convert("RGBA")
    except Exception:
        return None

    width, height = img.size
    plane_img = Image.new("L", (width, height))
    pixels = plane_img.load()

    channel_map = {"R": 0, "G": 1, "B": 2, "A": 3}
    indices = [channel_map[ch.upper()] for ch in channels if ch.upper() in channel_map]
    if not indices:
        return None

    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            bits = [(pixel[idx] & 1) for idx in indices]
            value = 255 if any(bits) else 0
            pixels[x, y] = value

    try:
        buf = io.BytesIO()
        plane_img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def render_lsb_breakdown(result: Dict[str, Any]) -> None:
    """Display LSB overall and per-channel findings with visuals."""

    recovered = result.get("recovered_texts", [])
    lsb_candidates = {
        candidate.get("selector", ""): candidate
        for candidate in recovered
        if candidate.get("source") == "lsb"
    }

    image_path = result.get("bitplane_path")
    image_path_obj = None
    if image_path:
        candidate_path = Path(image_path)
        if candidate_path.exists():
            image_path_obj = candidate_path

    st.subheader("LSB analysis")

    def render_section(title: str, selector_keys: Iterable[str], channels: Iterable[str], key_suffix: str) -> None:
        candidate = next((lsb_candidates.get(key) for key in selector_keys if key in lsb_candidates), None)
        image_bytes = _generate_lsb_visualization(image_path_obj, channels)

        st.markdown(f"**{title}**")
        if image_bytes:
            st.image(image_bytes, caption=f"{title} LSB visualization", use_column_width=True)
        else:
            st.caption("No visualization available for this plane.")

        text_value = candidate.get("text", "") if candidate else ""
        if not text_value:
            text_value = "No text recovered for this plane."

        st.text_area(
            f"{title} text",
            value=text_value,
            height=160,
            disabled=True,
            label_visibility="collapsed",
            key=f"lsb-text-{key_suffix}",
        )

    render_section("LSB overall (RGB)", ["RGB", "RGBA"], ["R", "G", "B"], "overall")
    render_section("R plane", ["R"], ["R"], "r")
    render_section("G plane", ["G"], ["G"], "g")
    render_section("B plane", ["B"], ["B"], "b")


def render_recovered_text(recovered_texts: Iterable[dict]) -> None:
    """Display recovered text from targeted extraction (e.g., zsteg) - legacy format."""
    texts = list(recovered_texts)
    if not texts:
        return

    st.subheader("🔓 Recovered Text")
    st.success("Hidden message(s) detected!")

    for candidate in texts:
        label = candidate.get("label", "Unknown")
        selector = candidate.get("selector", "")
        text = candidate.get("text", "")

        with st.expander(f"{label} ({selector})", expanded=(len(texts) == 1)):
            st.code(text, language=None)


def render_diagnostics(recovered_texts: Iterable[dict]) -> None:
    """Display technical diagnostics about where text was found."""
    texts = list(recovered_texts)
    if not texts:
        return

    with st.expander("🔬 Diagnostics", expanded=False):
        st.caption("Technical details about recovered data")

        for candidate in texts:
            label = candidate.get("label", "Unknown")
            selector = candidate.get("selector", "")
            bytes_len = candidate.get("bytes_len", 0)
            hex_preview = candidate.get("hex_preview", "")

            st.markdown(f"**{label}** (`{selector}`)")
            st.text(f"Length: {bytes_len} bytes")
            if hex_preview:
                st.text(f"First 64 bytes (hex): {hex_preview}")
            st.markdown("---")


def render_analyzer_status_table(results: dict) -> None:
    """Display analyzer status in a clean table format - legacy version."""
    if not results:
        return

    st.subheader("📊 Analyzer Status")

    # Group by status
    ok_analyzers = []
    skipped_analyzers = []
    error_analyzers = []

    for analyzer, data in sorted(results.items()):
        if not isinstance(data, dict):
            continue

        status = data.get("status", "unknown")
        reason = data.get("reason", "") or data.get("error", "")

        if status == "ok":
            ok_analyzers.append(analyzer)
        elif status == "skipped":
            skipped_analyzers.append((analyzer, reason))
        else:
            error_analyzers.append((analyzer, reason))

    # Display in a compact format
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("✅ Successful", len(ok_analyzers))
        if ok_analyzers:
            with st.expander("Details", expanded=False):
                for analyzer in ok_analyzers:
                    st.text(f"• {analyzer}")

    with col2:
        st.metric("⏭️ Skipped", len(skipped_analyzers))
        if skipped_analyzers:
            with st.expander("Details", expanded=False):
                for analyzer, reason in skipped_analyzers:
                    st.text(f"• {analyzer}")
                    if reason:
                        st.caption(f"  {reason}")

    with col3:
        st.metric("❌ Errors", len(error_analyzers))
        if error_analyzers:
            with st.expander("Details", expanded=True):
                for analyzer, reason in error_analyzers:
                    st.text(f"• {analyzer}")
                    if reason:
                        st.caption(f"  {reason}")


def _trim_log(log_content: str, max_lines: int = 150) -> str:
    """Trim log to first/last N lines if too long."""
    lines = log_content.split("\n")
    if len(lines) <= max_lines * 2:
        return log_content

    first = lines[:max_lines]
    last = lines[-max_lines:]
    trimmed_count = len(lines) - (max_lines * 2)

    return "\n".join(first) + f"\n\n... [{trimmed_count} lines omitted] ...\n\n" + "\n".join(last)


def render_analyzers_table(result: Dict[str, Any]) -> None:
    """Display analyzer status table with expandable logs."""
    analyzers = result.get("analyzers", [])
    if not analyzers:
        st.caption("No analyzer information available.")
        return

    # Display table header
    for analyzer in analyzers:
        name = analyzer.get("name", "unknown")
        status = analyzer.get("status", "unknown")
        reason = analyzer.get("reason", "")
        stdout_path = analyzer.get("stdout_path")
        stderr_path = analyzer.get("stderr_path")

        # Status icon
        if status == "ok":
            icon = "✅"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"

        # Create expander for each analyzer
        with st.expander(f"{icon} {name} — {status}", expanded=False):
            if reason:
                st.caption(f"Reason: {reason}")

            # Show trimmed logs if available
            if stdout_path:
                try:
                    stdout = Path(stdout_path).read_text(encoding="utf-8", errors="ignore")
                    if stdout.strip():
                        st.text("stdout (trimmed):")
                        st.code(_trim_log(stdout, 150), language=None)
                        st.download_button(
                            "Download full stdout",
                            data=stdout,
                            file_name=f"{name}_stdout.log",
                            mime="text/plain",
                            key=f"download-stdout-{name}",
                        )
                except Exception:
                    pass

            if stderr_path:
                try:
                    stderr = Path(stderr_path).read_text(encoding="utf-8", errors="ignore")
                    if stderr.strip():
                        st.text("stderr (trimmed):")
                        st.code(_trim_log(stderr, 150), language=None)
                        st.download_button(
                            "Download full stderr",
                            data=stderr,
                            file_name=f"{name}_stderr.log",
                            mime="text/plain",
                            key=f"download-stderr-{name}",
                        )
                except Exception:
                    pass


def _generate_bitplane(image_path: str, channel: str, bit: int) -> Optional[bytes]:
    """Generate a single bit-plane image."""
    try:
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size

        # Create new image for this bit plane
        plane_img = Image.new("L", (width, height))
        pixels = plane_img.load()

        channel_idx = {"R": 0, "G": 1, "B": 2, "A": 3}.get(channel, 0)

        for y in range(height):
            for x in range(width):
                pixel = img.getpixel((x, y))
                channel_value = pixel[channel_idx]
                bit_value = (channel_value >> bit) & 1
                pixels[x, y] = 255 if bit_value else 0

        buf = io.BytesIO()
        plane_img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def render_bitplane_explorer(result: Dict[str, Any]) -> None:
    """Display bit-plane explorer with lazy generation."""
    image_path = result.get("bitplane_path")
    if not image_path or not Path(image_path).exists():
        st.caption("Bit-plane explorer not available for this image.")
        return

    st.caption("Click any bit-plane to view full size. OCR attempts are experimental.")

    channels = ["R", "G", "B", "A"]
    bits = list(range(8))

    # Create grid of bit-planes
    for channel in channels:
        st.markdown(f"**{channel} channel**")
        cols = st.columns(8)
        for bit_idx, col in zip(bits, cols):
            with col:
                if st.button(f"Bit {bit_idx}", key=f"bitplane-{channel}-{bit_idx}"):
                    plane_bytes = _generate_bitplane(image_path, channel, bit_idx)
                    if plane_bytes:
                        st.image(plane_bytes, caption=f"{channel} Bit {bit_idx}", use_column_width=True)


def _attempt_decode_text(data: bytes, method: str) -> Optional[str]:
    """Attempt to decode data using various methods."""
    try:
        if method == "utf-8":
            text = data.decode("utf-8", errors="ignore")
        elif method == "utf-16le":
            text = data.decode("utf-16le", errors="ignore")
        elif method == "utf-16be":
            text = data.decode("utf-16be", errors="ignore")
        elif method == "base64→utf-8":
            decoded = base64.b64decode(data)
            text = decoded.decode("utf-8", errors="ignore")
        elif method == "zlib→utf-8":
            decompressed = zlib.decompress(data)
            text = decompressed.decode("utf-8", errors="ignore")
        elif method == "url-decode":
            text = data.decode("utf-8", errors="ignore")
            import urllib.parse
            text = urllib.parse.unquote(text)
        elif method == "rot13":
            text = data.decode("utf-8", errors="ignore")
            text = text.translate(str.maketrans(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm"
            ))
        else:
            return None

        # Filter out binary-looking content
        printable_ratio = sum(1 for c in text if c.isprintable() or c in '\n\r\t') / max(len(text), 1)
        if printable_ratio > 0.7 and len(text.strip()) > 10:
            return text
        return None
    except Exception:
        return None


def render_channel_text_dumps(result: Dict[str, Any]) -> None:
    """Display channel text dumps with multiple decoder attempts."""
    image_path = result.get("bitplane_path")
    if not image_path or not Path(image_path).exists():
        st.caption("Channel text dumps not available.")
        return

    methods = ["utf-8", "utf-16le", "utf-16be", "base64→utf-8", "zlib→utf-8", "url-decode", "rot13"]

    # Extract raw data from LSB of each channel
    try:
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size

        for channel_name, channel_idx in [("R", 0), ("G", 1), ("B", 2), ("A", 3)]:
            # Extract LSB bits for this channel
            bits = []
            for y in range(height):
                for x in range(width):
                    pixel = img.getpixel((x, y))
                    channel_value = pixel[channel_idx]
                    bits.append(channel_value & 1)

            # Convert bits to bytes
            data = bytearray()
            for i in range(0, len(bits), 8):
                chunk = bits[i:i+8]
                if len(chunk) == 8:
                    value = sum(bit << (7 - idx) for idx, bit in enumerate(chunk))
                    data.append(value)

            # Try each decoding method
            found_any = False
            for method in methods:
                text = _attempt_decode_text(bytes(data), method)
                if text:
                    if not found_any:
                        st.markdown(f"**{channel_name} channel**")
                        found_any = True

                    with st.expander(f"{method} ({len(text)} chars)", expanded=False):
                        st.text_area(
                            f"{channel_name}-{method}",
                            value=text[:1000],  # Limit display
                            height=100,
                            disabled=True,
                            label_visibility="collapsed",
                            key=f"channel-dump-{channel_name}-{method}",
                        )

    except Exception as e:
        st.caption(f"Error extracting channel data: {e}")


def render_diagnostics_detailed(result: Dict[str, Any]) -> None:
    """Display detailed diagnostics with selectors and hex previews."""
    selectors_hit = result.get("selectors_hit", [])
    if not selectors_hit:
        st.caption("No selectors produced results.")
        return

    st.caption("Selectors that yielded text with hex previews")

    for selector_info in selectors_hit:
        tool = selector_info.get("tool", "unknown")
        selector = selector_info.get("selector", "")
        bytes_len = selector_info.get("bytes_len", 0)

        st.markdown(f"**{tool}** — `{selector}` — {bytes_len} bytes")

        # Find matching candidate to get hex preview
        candidates = result.get("candidates", [])
        for candidate in candidates:
            if candidate.get("selector") == selector:
                hex_preview = candidate.get("hex_preview", "")
                if hex_preview:
                    st.code(hex_preview, language=None)
                break

        st.markdown("---")


def render_summary_tab(result: Dict[str, Any]) -> None:
    """Render the summary tab content."""
    st.caption("Concise analysis overview")

    # Show meta info
    render_meta(result.get("meta", {}))

    st.markdown("---")

    # Show which selectors hit
    selectors_hit = result.get("selectors_hit", [])
    if selectors_hit:
        st.markdown("**Detected selectors:**")
        for sel in selectors_hit:
            st.text(f"• {sel.get('tool')} — {sel.get('selector')}")
    else:
        st.info("No selectors detected hidden text.")

    st.markdown("---")

    # Show best candidate info
    best = result.get("best_candidate")
    if best:
        st.markdown("**Best candidate path:**")
        st.text(f"{best.get('source')} → {best.get('selector')} ({best.get('bytes_len')} bytes)")
    else:
        st.caption("No best candidate identified.")
