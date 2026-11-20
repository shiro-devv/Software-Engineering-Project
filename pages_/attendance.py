"""Face-scanning attendance screen."""

from __future__ import annotations

from typing import Any

import streamlit as st

import db
import face_utils
from components import cards
from components.mascot import mascot


_VIEWFINDER = """
<div class="viewfinder" aria-hidden="true">
    <span class="viewfinder-corner viewfinder-corner--tl"></span>
    <span class="viewfinder-corner viewfinder-corner--tr"></span>
    <span class="viewfinder-corner viewfinder-corner--bl"></span>
    <span class="viewfinder-corner viewfinder-corner--br"></span>
</div>
"""

_ERROR_COPY: dict[str, tuple[str, str]] = {
    "no_face": ("No Face Found", "Center one face in the frame and try again."),
    "multiple_faces": (
        "One Face at a Time",
        "Only the student being marked should be in frame.",
    ),
    "bad_image": ("Not Recognized", "Try again with a clearer capture."),
    "encoding_failed": ("Not Recognized", "Try again in even light."),
    "backend_unavailable": (
        "Scanner Unavailable",
        "Face recognition isn’t installed on this machine.",
    ),
    "backend_error": (
        "Scanner Unavailable",
        "The face engine couldn’t start. Please try again.",
    ),
    "backend_mismatch": (
        "Scanner Unavailable",
        "Re-save the student photos to refresh their face profile.",
    ),
}


def _set_stage(stage: str) -> None:
    st.session_state["attendance_stage"] = stage


def _start_camera() -> None:
    st.session_state["attendance_stage"] = "camera"
    st.session_state["camera_nonce"] = (
        int(st.session_state.get("camera_nonce", 0)) + 1
    )
    st.session_state.pop("attendance_result", None)
    st.rerun()


def _cancel_camera() -> None:
    _set_stage("scan")
    st.rerun()


def _scan_again() -> None:
    _set_stage("scan")
    st.session_state.pop("attendance_result", None)
    st.rerun()


def _result_lines(result: dict[str, Any]) -> str:
    kind = result.get("kind")
    if kind in {"present", "already"}:
        name = cards.escape(result.get("name", "Student"))
        status = "Present" if kind == "present" else "Already Present"
        return cards.html_block(
            f"""
            <div class="scan-result" role="status" aria-live="polite">
                <div class="scan-result-line scan-result-name">{name}</div>
                <div class="scan-result-line">{status}</div>
                <div class="scan-result-line">{cards.escape(result.get("time", ""))}</div>
            </div>
            """
        )

    title = cards.escape(result.get("title", "Not Recognized"))
    subtitle = cards.escape(result.get("subtitle", "Try again"))
    note = result.get("note")
    note_markup = (
        f'<div class="scan-result-note">{cards.escape(note)}</div>' if note else ""
    )
    return cards.html_block(
        f"""
        <div class="scan-result" role="status" aria-live="polite">
            <div class="scan-result-line">{title}</div>
            <div class="scan-result-line">{subtitle}</div>
            {note_markup}
        </div>
        """
    )


def _recognize_capture(image_bytes: bytes) -> dict[str, Any]:
    """Recognise a capture and persist attendance exactly once."""
    revision = int(st.session_state.get("students_revision", 0))
    known_faces = face_utils.load_known_faces(revision)

    try:
        encoding = face_utils.compute_face_encoding(image_bytes)
        match = face_utils.find_best_match(
            encoding, known_faces, tolerance=face_utils.FACE_MATCH_TOLERANCE
        )
    except face_utils.FaceProcessingError as exc:
        title, note = _ERROR_COPY.get(
            exc.code, ("Not Recognized", "Please try again.")
        )
        if exc.code in {"backend_unavailable", "backend_error"}:
            note = exc.message
        return {
            "kind": "error",
            "title": title,
            "subtitle": "Try again",
            "note": note,
        }
    except Exception:
        return {
            "kind": "error",
            "title": "Something Went Wrong",
            "subtitle": "Try again",
            "note": "The scan couldn’t be completed just now.",
        }

    if match is None:
        return {
            "kind": "unknown",
            "title": "Not Recognized",
            "subtitle": "Try again",
            "note": (
                "Add the student first if they aren’t enrolled yet."
                if not known_faces
                else None
            ),
        }

    try:
        created, timestamp = db.mark_present(match.student_id)
    except Exception:
        return {
            "kind": "error",
            "title": "Couldn’t Save",
            "subtitle": "Try again",
            "note": "The attendance record couldn’t be saved just now.",
        }

    return {
        "kind": "present" if created else "already",
        "name": match.name,
        "time": db.format_time(timestamp),
    }


def render() -> None:
    """Render the mascot and interactive scanner panel."""
    stage = st.session_state.get("attendance_stage", "scan")
    if stage not in {"scan", "camera", "result"}:
        stage = "scan"
        _set_stage(stage)

    with st.container(key="attendance_page"):
        st.markdown(cards.page_header("Attendance"), unsafe_allow_html=True)

        # The panel grows a little while the browser's camera widget is active.
        panel_min_height = 430 if stage == "camera" else 300
        st.markdown(
            cards.html_block(
                f"""
                <style>
                .st-key-scan_panel {{
                    min-height: {panel_min_height}px;
                }}
                </style>
                """
            ),
            unsafe_allow_html=True,
        )

        with st.container(key="attendance_stage"):
            mascot_col, panel_col = st.columns(
                [0.86, 1.36], gap="small", vertical_alignment="center"
            )

            with mascot_col:
                st.markdown(
                    cards.html_block(
                        f'<div class="attendance-mascot">{mascot(286, "walking")}</div>'
                    ),
                    unsafe_allow_html=True,
                )

            with panel_col:
                with st.container(key="scan_panel"):
                    if stage == "scan":
                        st.markdown(
                            cards.html_block(_VIEWFINDER),
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "SCAN",
                            key="scan_start",
                            type="primary",
                            width="content",
                        ):
                            _start_camera()

                    elif stage == "camera":
                        st.markdown(
                            cards.html_block(_VIEWFINDER),
                            unsafe_allow_html=True,
                        )
                        camera_key = (
                            f"attendance_camera_{st.session_state.get('camera_nonce', 0)}"
                        )
                        capture = st.camera_input(
                            "Scan a student’s face",
                            key=camera_key,
                            label_visibility="collapsed",
                            width="stretch",
                        )
                        st.markdown(
                            '<div class="camera-hint">Tap “Take Photo” when the face is inside the frame.</div>',
                            unsafe_allow_html=True,
                        )
                        if capture is not None:
                            st.session_state["attendance_result"] = _recognize_capture(
                                capture.getvalue()
                            )
                            _set_stage("result")
                            st.rerun()
                        if st.button(
                            "Cancel",
                            key="cancel_camera",
                            type="secondary",
                            width="content",
                        ):
                            _cancel_camera()

                    else:
                        result = st.session_state.get("attendance_result") or {
                            "kind": "unknown",
                            "title": "Not Recognized",
                            "subtitle": "Try again",
                        }
                        st.markdown(_result_lines(result), unsafe_allow_html=True)
                        retry = result.get("kind") in {"error", "unknown"}
                        if st.button(
                            "SCAN again" if retry else "Scan next",
                            key="scan_again",
                            type="primary",
                            width="content",
                        ):
                            _scan_again()

        if face_utils.recognition_backend() is None:
            st.markdown(
                cards.inline_alert(
                    "Face recognition isn’t available. Install face_recognition or OpenCV, then restart the app."
                ),
                unsafe_allow_html=True,
            )
        elif stage == "scan":
            student_count = db.count_students()
            if student_count == 0:
                st.markdown(
                    '<div class="scan-footnote">No students are enrolled yet. Add one from the Students page to begin.</div>',
                    unsafe_allow_html=True,
                )
