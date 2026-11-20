"""Entry point for the classroom attendance app.

Run with:

    streamlit run app.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import streamlit as st

import db
from components import sidebar
from pages_ import attendance, dashboard, login, students

APP_DIR = Path(__file__).resolve().parent
STYLES_PATH = APP_DIR / "styles.css"


st.set_page_config(
    page_title="Roll Call · Student Attendance",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def _bootstrap_database() -> bool:
    db.init_db()
    return True


def _inject_styles() -> None:
    css = STYLES_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _init_session() -> None:
    defaults = {
        "logged_in": False,
        "username": "",
        "page": "login",
        "students_revision": 0,
        "attendance_stage": "scan",
        "student_page": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def main() -> None:
    _inject_styles()
    _init_session()

    try:
        _bootstrap_database()
    except Exception:
        st.markdown(
            textwrap.dedent(
                """
                <div class="fatal-card">
                    <h1>We couldn’t open the attendance database.</h1>
                    <div class="fatal-copy">Check that the app can write to its <code>data/</code> folder, then refresh.</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
        st.stop()

    if not st.session_state.logged_in:
        st.session_state.page = "login"
        # There is intentionally no sidebar on the login screen.
        st.markdown(
            textwrap.dedent(
                """
                <style>
                    section[data-testid="stSidebar"],
                    [data-testid="stSidebarCollapsedControl"],
                    [data-testid="collapsedControl"] { display: none !important; }
                </style>
                """
            ),
            unsafe_allow_html=True,
        )
        login.render()
        return

    if st.session_state.page == "login":
        st.session_state.page = "dashboard"

    page = st.session_state.get("page", "dashboard")
    if page not in {"dashboard", "students", "attendance"}:
        page = "dashboard"
        st.session_state.page = page

    sidebar.render()

    renderers = {
        "dashboard": dashboard.render,
        "students": students.render,
        "attendance": attendance.render,
    }
    renderers[page]()


if __name__ == "__main__":
    main()
