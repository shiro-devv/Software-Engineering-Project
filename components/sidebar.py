"""Custom navy navigation rail built on top of ``st.sidebar``."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Final

import streamlit as st

NAV_ITEMS: Final[tuple[tuple[str, str], ...]] = (
    ("dashboard", "Dashboard"),
    ("students", "Students"),
    ("attendance", "Attendance"),
)

# Drop a square/oval logo at assets/logo.png (or .jpg / .svg) to replace the
# cream placeholder without editing this module.
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_LOGO_CANDIDATES = (
    _ASSETS_DIR / "logo.png",
    _ASSETS_DIR / "logo.jpg",
    _ASSETS_DIR / "logo.jpeg",
    _ASSETS_DIR / "logo.svg",
)


def _logo_markup() -> str:
    for path in _LOGO_CANDIDATES:
        if path.exists():
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".svg": "image/svg+xml",
            }[path.suffix.lower()]
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return (
                f'<div class="sidebar-logo-wrap">'
                f'<img class="sidebar-logo-image" src="data:{mime};base64,{data}" '
                f'alt="Attendance app logo" /></div>'
            )

    return (
        '<div class="sidebar-logo-wrap">'
        '<div class="sidebar-logo" role="img" aria-label="Roll Call">'
        "<span>ROLL CALL</span>"
        "</div>"
        "</div>"
    )


def render() -> None:
    """Draw the fixed custom sidebar.

    The current page uses a primary button, which gives it a persistent
    light-blue pill through CSS.  The controls stay real Streamlit buttons so
    keyboard users can tab through the navigation like any other control.
    """
    page = st.session_state.get("page", "dashboard")

    with st.sidebar:
        st.markdown(_logo_markup(), unsafe_allow_html=True)

        for slug, label in NAV_ITEMS:
            if st.button(
                label,
                key=f"nav_{slug}",
                width="stretch",
                type="primary" if slug == page else "secondary",
            ):
                if st.session_state.get("page") != slug:
                    st.session_state.page = slug
                    st.rerun()

        if st.button(
            "Logout",
            key="logout_nav",
            width="stretch",
            type="secondary",
        ):
            st.session_state.clear()
            st.session_state["logged_in"] = False
            st.session_state["page"] = "login"
            st.rerun()
