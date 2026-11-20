"""Dashboard overview."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import db
from components import cards


def render() -> None:
    """Show today's attendance metrics and latest check-ins."""
    with st.container(key="dashboard_page"):
        st.markdown(
            cards.page_header(
                "Dashboard", datetime.now().strftime("%m/%d/%y")
            ),
            unsafe_allow_html=True,
        )

        try:
            metrics = db.dashboard_metrics()
            events = db.recent_activity(limit=8)
        except Exception:
            metrics = {"total": 0, "present": 0, "absent": 0}
            events = []
            st.markdown(
                cards.inline_alert(
                    "We couldn’t load today’s figures. Refresh the page to try again."
                ),
                unsafe_allow_html=True,
            )

        with st.container(key="dashboard_stats"):
            stat_columns = st.columns(3, gap="medium")
            values = (
                ("Total Students", metrics["total"]),
                ("Present Today", metrics["present"]),
                ("Absent Today", metrics["absent"]),
            )
            for column, (label, value) in zip(stat_columns, values):
                with column:
                    st.markdown(
                        cards.stat_card(label, cards.format_count(value)),
                        unsafe_allow_html=True,
                    )

        st.markdown(cards.activity_card(events), unsafe_allow_html=True)
