"""Login screen."""

from __future__ import annotations

import streamlit as st

import db
from components import cards
from components.mascot import mascot


_BUBBLE_SVG = """
<svg class="login-bubble-svg" viewBox="0 0 470 380" aria-hidden="true"
     xmlns="http://www.w3.org/2000/svg">
    <path d="M120 44
             C210 4 350 35 382 122
             C400 168 373 202 351 229
             C390 225 428 232 455 247
             C420 263 389 271 356 269
             C336 311 290 344 226 351
             C141 360 53 309 35 229
             C17 148 64 78 120 44 Z"
          fill="none" stroke="currentColor" stroke-width="4"
          stroke-linecap="round" stroke-linejoin="round"
          stroke-dasharray="0.5 11" />
</svg>
"""


def _login_markup() -> str:
    return cards.html_block(
        f"""
        <div class="login-bubble-wrap">
            {_BUBBLE_SVG}
            <div class="login-bubble-inner">
                <div class="login-bubble-mascot">{mascot(190, "standing")}</div>
                <div class="login-greeting">Hi! Let’s get you<br />signed in.</div>
            </div>
        </div>
        """
    )


def render() -> None:
    """Render the two-column welcome screen."""
    with st.container(key="login_page"):
        left, right = st.columns(
            [1.14, 0.86], gap="large", vertical_alignment="center"
        )

        with left:
            st.markdown(_login_markup(), unsafe_allow_html=True)

        with right:
            with st.container(key="login_panel"):
                st.markdown(
                    cards.html_block(
                        """
                        <h1 class="login-title">WELCOME</h1>
                        <div class="login-subtitle">Please login to continue</div>
                        """
                    ),
                    unsafe_allow_html=True,
                )

                error = st.session_state.get("login_error")
                if error:
                    st.markdown(
                        cards.inline_alert(str(error)), unsafe_allow_html=True
                    )

                with st.form("login_form", clear_on_submit=False, border=False):
                    username = st.text_input(
                        "Username",
                        key="login_username",
                        placeholder="Username",
                        label_visibility="collapsed",
                        autocomplete="username",
                    )
                    password = st.text_input(
                        "Password",
                        key="login_password",
                        type="password",
                        placeholder="Password",
                        label_visibility="collapsed",
                        autocomplete="current-password",
                    )
                    submitted = st.form_submit_button(
                        "Login",
                        type="primary",
                        width="stretch",
                    )

            if submitted:
                username = (username or "").strip()
                if not username or not password:
                    st.session_state.login_error = (
                        "Please enter both your username and password."
                    )
                else:
                    try:
                        user = db.authenticate_user(username, password)
                    except Exception:
                        user = None
                        st.session_state.login_error = (
                            "We couldn’t sign you in just now. Please try again."
                        )
                    else:
                        if user is None:
                            st.session_state.login_error = (
                                "That username and password don’t match. Try again."
                            )
                        else:
                            st.session_state.logged_in = True
                            st.session_state.username = user["username"]
                            st.session_state.page = "dashboard"
                            st.session_state.pop("login_error", None)
                st.rerun()
