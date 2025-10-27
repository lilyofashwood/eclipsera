"""Reusable UI helpers for the Streamlit application."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import streamlit as st


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


def render_recovered_text(recovered_texts: Iterable[dict]) -> None:
    """Display recovered text from targeted extraction (e.g., zsteg)."""
    texts = list(recovered_texts)
    if not texts:
        return

    st.subheader("Recovered Text")
    st.success("Hidden message(s) detected!")

    for candidate in texts:
        label = candidate.get("label", "Unknown")
        selector = candidate.get("selector", "")
        text = candidate.get("text", "")

        with st.expander(f"{label} ({selector})", expanded=(len(texts) == 1)):
            st.code(text, language=None)
