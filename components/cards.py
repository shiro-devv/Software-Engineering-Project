"""Small, presentation-only HTML building blocks used by the pages."""

from __future__ import annotations

import base64
import html
import textwrap
from typing import Any, Mapping, Sequence

from db import format_time


def escape(value: Any) -> str:
    """Escape any value for safe interpolation into custom HTML."""
    return html.escape(str(value), quote=True)


def html_block(markup: str) -> str:
    """Normalise custom HTML for Streamlit's Markdown renderer.

    Markdown terminates a raw HTML block at a blank line, so removed blank
    lines keep the entire fragment in one HTML block.  Dedenting prevents a
    four-space indent from being interpreted as a code block.
    """
    dedented = textwrap.dedent(markup).strip()
    return "\n".join(line for line in dedented.splitlines() if line.strip())


def page_header(title: str, right_text: str | None = None) -> str:
    """Render the large page title and optional right-aligned meta text."""
    right = ""
    if right_text:
        right = f'<span class="page-header-meta">{escape(right_text)}</span>'
    return html_block(
        f"""
        <header class="page-header">
            <h1>{escape(title)}</h1>
            {right}
        </header>
        """
    )


def stat_card(label: str, value: int | str) -> str:
    """One of the light blue-grey dashboard statistics cards."""
    return html_block(
        f"""
        <section class="stat-card" aria-label="{escape(label)}: {escape(value)}">
            <div class="stat-label">{escape(label)}</div>
            <div class="stat-value">{escape(value)}</div>
        </section>
        """
    )


def activity_card(events: Sequence[Mapping[str, Any]]) -> str:
    """Build the dashboard activity card with a friendly empty state."""
    if events:
        rows = "".join(
            f"""
            <div class="activity-row">
                <div class="activity-copy">
                    <strong>{escape(event.get("name", "Unknown"))}</strong>
                    <span> marked present</span>
                </div>
                <time class="activity-time">{escape(format_time(event.get("time")))}</time>
            </div>
            """
            for event in events
        )
        body = f'<div class="activity-list">{rows}</div>'
    else:
        body = """
        <div class="activity-empty">
            <span class="activity-empty-mark" aria-hidden="true">◎</span>
            <div class="activity-empty-title">No check-ins yet today.</div>
            <span class="activity-empty-copy">Scan a student to start today’s activity.</span>
        </div>
        """

    return html_block(
        f"""
        <section class="activity-card" aria-labelledby="activity-title">
            <h2 id="activity-title">Activity</h2>
            {body}
        </section>
        """
    )


def photo_data_uri(photo: bytes | None) -> str | None:
    """Turn a stored photo into a safe data URI for an <img> tag."""
    if not photo:
        return None
    if photo.startswith(b"\x89PNG"):
        mime = "image/png"
    elif photo.startswith(b"GIF8"):
        mime = "image/gif"
    elif photo.startswith(b"RIFF") and photo[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(photo).decode('ascii')}"


def student_card_content(student: Mapping[str, Any]) -> str:
    """Markup for a student card's photo and copy.

    The edit and delete widgets are actual Streamlit buttons positioned over
    this markup by CSS, keeping keyboard controls real while preserving the
    exact card appearance.
    """
    name = escape(student.get("name", "Student"))
    status = str(student.get("status", "absent")).capitalize()
    photo_uri = photo_data_uri(student.get("photo"))

    if photo_uri:
        photo = (
            f'<img src="{photo_uri}" alt="Photo of {name}" loading="lazy" />'
        )
    else:
        initials = "".join(
            part[0] for part in str(student.get("name", "")).split()[:2] if part
        ).upper()
        photo = (
            '<span class="student-photo-fallback" aria-hidden="true">'
            f"{escape(initials or '?')}</span>"
            '<span class="sr-only">No photo available</span>'
        )

    return html_block(
        f"""
        <div class="student-card-content">
            <div class="student-photo">{photo}</div>
            <div class="student-name">{name}</div>
            <div class="student-status">{escape(status)} today</div>
        </div>
        """
    )


def inline_alert(message: str, tone: str = "error") -> str:
    """On-brand inline feedback; never Streamlit's default alert box."""
    safe_tone = "error" if tone == "error" else "info"
    return html_block(
        f"""
        <div class="inline-alert inline-alert--{safe_tone}" role="alert">
            <span class="inline-alert-dot" aria-hidden="true"></span>
            <span>{escape(message)}</span>
        </div>
        """
    )


def format_count(value: int | str) -> str:
    """Small formatter kept here so every metric uses the same locale style."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)
