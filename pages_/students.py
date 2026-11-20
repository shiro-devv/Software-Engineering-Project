"""Student roster, enrolment and management dialogs."""

from __future__ import annotations

import math
from typing import Any

import streamlit as st

import db
import face_utils
from components import cards

PER_PAGE = 6


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _next_dialog_nonce() -> int:
    nonce = int(st.session_state.get("student_dialog_nonce", 0)) + 1
    st.session_state.student_dialog_nonce = nonce
    return nonce


def _open_student_dialog(mode: str, student_id: int | None = None) -> None:
    st.session_state["student_dialog"] = {
        "mode": mode,
        "id": student_id,
        "nonce": _next_dialog_nonce(),
    }
    st.rerun()


def _close_student_dialog() -> None:
    st.session_state.pop("student_dialog", None)
    st.rerun()


def _open_delete_dialog(student_id: int) -> None:
    st.session_state["delete_dialog"] = {
        "id": student_id,
        "nonce": _next_dialog_nonce(),
    }
    st.rerun()


def _close_delete_dialog() -> None:
    st.session_state.pop("delete_dialog", None)
    st.rerun()


def _reset_students_page() -> None:
    st.session_state["student_page"] = 0


def _select_photo_source(state_key: str, source: str) -> None:
    st.session_state[state_key] = source


def _notice(message: str) -> None:
    st.session_state["students_notice"] = message


# ---------------------------------------------------------------------------
# Add / edit dialog
# ---------------------------------------------------------------------------


def _preview_markup(photo: bytes | None, label: str) -> str:
    uri = cards.photo_data_uri(photo)
    if not uri:
        return ""
    return cards.html_block(
        f"""
        <div class="dialog-photo-block">
            <span class="dialog-field-label">{cards.escape(label)}</span>
            <div class="dialog-photo-preview">
                <img src="{uri}" alt="{cards.escape(label)}" />
            </div>
        </div>
        """
    )


def _student_form(mode: str, student_id: int | None, nonce: int) -> None:
    existing: dict[str, Any] | None = None
    if student_id is not None:
        try:
            existing = db.get_student(student_id)
        except Exception:
            st.markdown(
                cards.inline_alert(
                    "We couldn’t load this student just now. Close the dialog and try again."
                ),
                unsafe_allow_html=True,
            )
            if st.button("Close", key=f"close_missing_{nonce}", width="stretch"):
                _close_student_dialog()
            return
        if existing is None:
            st.markdown(
                cards.inline_alert("This student no longer exists."),
                unsafe_allow_html=True,
            )
            if st.button("Close", key=f"close_missing_{nonce}", width="stretch"):
                _close_student_dialog()
            return

    default_name = existing["name"] if existing else ""
    default_code = existing["student_code"] if existing else ""

    name_col, code_col = st.columns(2, gap="small")
    with name_col:
        name = st.text_input(
            "Full name",
            value=default_name,
            placeholder="e.g. Maya Chen",
            max_chars=80,
            key=f"student_name_{nonce}",
        )
    with code_col:
        student_code = st.text_input(
            "Student ID",
            value=default_code,
            placeholder="e.g. 2026-001",
            max_chars=40,
            key=f"student_code_{nonce}",
        )

    st.markdown(
        '<div class="dialog-section-label">Enrolment photo</div>',
        unsafe_allow_html=True,
    )

    source_key = f"photo_source_{nonce}"
    if source_key not in st.session_state:
        st.session_state[source_key] = "upload"
    source = st.session_state[source_key]

    active_style = f"""
    <style>
    .st-key-source_upload_{nonce} div.stButton > button,
    .st-key-source_camera_{nonce} div.stButton > button {{
        background: var(--input) !important;
        color: var(--navy) !important;
        font-weight: 700 !important;
        min-height: 38px !important;
        height: 38px !important;
        font-size: 14px !important;
    }}
    .st-key-source_{source}_{nonce} div.stButton > button {{
        background: var(--navy-button) !important;
        color: #FFFFFF !important;
    }}
    .st-key-source_{source}_{nonce} div.stButton > button:hover {{
        background: var(--navy) !important;
        color: #FFFFFF !important;
    }}
    </style>
    """
    st.markdown(cards.html_block(active_style), unsafe_allow_html=True)

    source_left, source_right = st.columns(2, gap="small")
    with source_left:
        st.button(
            "Upload photo",
            key=f"source_upload_{nonce}",
            width="stretch",
            type="secondary",
            on_click=_select_photo_source,
            args=(source_key, "upload"),
        )
    with source_right:
        st.button(
            "Use camera",
            key=f"source_camera_{nonce}",
            width="stretch",
            type="secondary",
            on_click=_select_photo_source,
            args=(source_key, "camera"),
        )

    new_photo: bytes | None = None
    if source == "upload":
        photo_col, preview_col = st.columns([2.2, 1], gap="small")
        with photo_col:
            uploaded = st.file_uploader(
                "Upload a clear, front-facing photo",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"student_photo_upload_{nonce}",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                new_photo = uploaded.getvalue()

        with preview_col:
            if new_photo:
                st.markdown(
                    _preview_markup(new_photo, "New photo"),
                    unsafe_allow_html=True,
                )
            elif existing and existing.get("photo"):
                st.markdown(
                    _preview_markup(existing["photo"], "Current photo"),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div class="dialog-photo-block">
                        <span class="dialog-field-label">Preview</span>
                        <div class="dialog-photo-preview dialog-photo-preview--empty">
                            <span>No photo</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        # The camera widget shows the captured frame and its own "Clear photo"
        # control, so a second preview beside it would be redundant.
        captured = st.camera_input(
            "Take an enrolment photo",
            key=f"student_photo_camera_{nonce}",
            label_visibility="collapsed",
            width="stretch",
        )
        st.markdown(
            '<div class="camera-hint">Look straight at the camera and use even lighting.</div>',
            unsafe_allow_html=True,
        )
        if captured is not None:
            new_photo = captured.getvalue()

    st.markdown(
        '<div class="dialog-hint">Use a photo of one face, without filters or heavy shadows. '
        "The face profile is created automatically when you save.</div>",
        unsafe_allow_html=True,
    )

    error_slot = st.empty()

    cancel_col, save_col = st.columns(2, gap="small")
    with cancel_col:
        cancel = st.button(
            "Cancel",
            key=f"cancel_student_{nonce}",
            width="stretch",
            type="secondary",
        )
    with save_col:
        save = st.button(
            "Save",
            key=f"save_student_{nonce}",
            width="stretch",
            type="primary",
        )

    if cancel:
        _close_student_dialog()

    if not save:
        return

    clean_name = (name or "").strip()
    clean_code = (student_code or "").strip()
    if not clean_name or not clean_code:
        error_slot.markdown(
            cards.inline_alert("Add both a full name and a student ID."),
            unsafe_allow_html=True,
        )
        return

    if new_photo is None and existing is None:
        error_slot.markdown(
            cards.inline_alert(
                "Add a clear photo so we can create this student’s face profile."
            ),
            unsafe_allow_html=True,
        )
        return

    stored_photo = existing.get("photo") if existing else None
    stored_encoding = existing.get("face_encoding") if existing else None

    if new_photo is not None:
        try:
            _, prepared_photo = face_utils.prepare_photo(new_photo)
            encoding = face_utils.compute_face_encoding(new_photo)
            stored_photo = prepared_photo
            stored_encoding = face_utils.serialize_encoding(encoding)
        except face_utils.FaceProcessingError as exc:
            error_slot.markdown(
                cards.inline_alert(exc.message), unsafe_allow_html=True
            )
            return
        except Exception:
            error_slot.markdown(
                cards.inline_alert(
                    "We couldn’t process that photo. Please choose a clearer image."
                ),
                unsafe_allow_html=True,
            )
            return
    elif existing and not stored_encoding and existing.get("photo"):
        # Repair legacy rows that have a photo but no encoding.
        try:
            encoding = face_utils.compute_face_encoding(existing["photo"])
            stored_encoding = face_utils.serialize_encoding(encoding)
        except face_utils.FaceProcessingError as exc:
            error_slot.markdown(
                cards.inline_alert(exc.message), unsafe_allow_html=True
            )
            return

    try:
        if existing:
            updated = db.update_student(
                int(existing["id"]),
                clean_name,
                clean_code,
                stored_photo,
                stored_encoding,
            )
            if not updated:
                raise RuntimeError("Student no longer exists")
            _notice("Student details updated.")
        else:
            db.add_student(clean_name, clean_code, stored_photo, stored_encoding)
            _notice("Student added to the roster.")
    except db.DuplicateStudentCode:
        error_slot.markdown(
            cards.inline_alert(
                "That student ID is already enrolled. Use a unique ID."
            ),
            unsafe_allow_html=True,
        )
        return
    except Exception:
        error_slot.markdown(
            cards.inline_alert(
                "We couldn’t save this student just now. Please try again."
            ),
            unsafe_allow_html=True,
        )
        return

    face_utils.invalidate_known_faces()
    st.session_state.pop("student_dialog", None)
    st.rerun()


@st.dialog("Add Student", width="small", on_dismiss=_close_student_dialog)
def _add_student_dialog(nonce: int) -> None:
    _student_form("add", None, nonce)


@st.dialog("Edit Student", width="small", on_dismiss=_close_student_dialog)
def _edit_student_dialog(student_id: int, nonce: int) -> None:
    _student_form("edit", student_id, nonce)


# ---------------------------------------------------------------------------
# Delete confirmation
# ---------------------------------------------------------------------------


@st.dialog("Delete Student", width="small", on_dismiss=_close_delete_dialog)
def _delete_student_dialog(student_id: int, nonce: int) -> None:
    try:
        student = db.get_student(student_id)
    except Exception:
        student = None

    if student is None:
        st.markdown(
            cards.inline_alert("This student no longer exists."),
            unsafe_allow_html=True,
        )
        if st.button("Close", key=f"close_delete_{nonce}", width="stretch"):
            _close_delete_dialog()
        return

    st.markdown(
        cards.html_block(
            f"""
            <div class="dialog-warning">
                Delete <strong>{cards.escape(student["name"])}</strong>?
            </div>
            <div class="dialog-warning-copy">
                Their enrolment photo and attendance history will be permanently removed.
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    error_slot = st.empty()

    cancel_col, delete_col = st.columns(2, gap="small")
    with cancel_col:
        cancel = st.button(
            "Cancel",
            key=f"cancel_delete_{nonce}",
            width="stretch",
            type="secondary",
        )
    with delete_col:
        confirm = st.button(
            "Delete",
            key=f"confirm_delete_{nonce}",
            width="stretch",
            type="secondary",
        )

    if cancel:
        _close_delete_dialog()

    if confirm:
        try:
            db.delete_student(student_id)
        except Exception:
            error_slot.markdown(
                cards.inline_alert(
                    "We couldn’t delete this student just now. Please try again."
                ),
                unsafe_allow_html=True,
            )
            return
        face_utils.invalidate_known_faces()
        _notice("Student removed from the roster.")
        st.session_state.pop("delete_dialog", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def _empty_markup(searching: bool, search: str) -> str:
    if searching:
        title = "No students match your search."
        copy = f"Try a different name than “{cards.escape(search)}”."
        mark = "⌕"
    else:
        title = "No students yet. Add your first student."
        copy = "Enrol someone to start taking attendance with the camera."
        mark = "+"
    return cards.html_block(
        f"""
        <div class="students-empty">
            <span class="students-empty-mark" aria-hidden="true">{mark}</span>
            <div class="students-empty-title">{title}</div>
            <span class="students-empty-copy">{copy}</span>
        </div>
        """
    )


def render() -> None:
    """Render the paginated, searchable student card grid."""
    if "student_page" not in st.session_state:
        st.session_state.student_page = 0

    with st.container(key="students_page"):
        with st.container(key="students_header"):
            title_col, add_col = st.columns(
                [3.2, 1.1], gap="small", vertical_alignment="center"
            )
            with title_col:
                st.markdown(
                    cards.page_header("Students"), unsafe_allow_html=True
                )
            with add_col:
                if st.button(
                    "Add Student",
                    key="add_student_btn",
                    width="stretch",
                    type="secondary",
                ):
                    _open_student_dialog("add")

        search = st.text_input(
            "Search students",
            placeholder="Search...",
            key="student_search",
            label_visibility="collapsed",
            on_change=_reset_students_page,
        )

        notice = st.session_state.pop("students_notice", None)
        if notice:
            st.markdown(
                cards.inline_alert(str(notice), tone="info"),
                unsafe_allow_html=True,
            )

        try:
            total = db.count_students(search)
        except Exception:
            st.markdown(
                cards.inline_alert(
                    "We couldn’t load the student roster. Refresh the page to try again."
                ),
                unsafe_allow_html=True,
            )
            return

        if total == 0:
            st.markdown(
                _empty_markup(bool(search.strip()), search),
                unsafe_allow_html=True,
            )
        else:
            pages = max(1, math.ceil(total / PER_PAGE))
            page = min(
                max(int(st.session_state.get("student_page", 0)), 0), pages - 1
            )
            st.session_state.student_page = page

            try:
                students = db.list_students_with_status(
                    db.today_iso(),
                    search=search,
                    limit=PER_PAGE,
                    offset=page * PER_PAGE,
                )
            except Exception:
                st.markdown(
                    cards.inline_alert(
                        "We couldn’t load these students. Refresh the page to try again."
                    ),
                    unsafe_allow_html=True,
                )
                return

            with st.container(key="students_grid"):
                for index in range(0, len(students), 3):
                    row = students[index : index + 3]
                    columns = st.columns(3, gap="medium")
                    for column, student in zip(columns, row):
                        student_id = int(student["id"])
                        with column:
                            with st.container(
                                key=f"student_card_{student_id}"
                            ):
                                st.markdown(
                                    cards.student_card_content(student),
                                    unsafe_allow_html=True,
                                )
                                if st.button(
                                    "edit",
                                    key=f"edit_student_{student_id}",
                                    help=f"Edit {student['name']}",
                                ):
                                    _open_student_dialog(
                                        "edit", student_id
                                    )
                                if st.button(
                                    "delete",
                                    key=f"delete_student_{student_id}",
                                    help=f"Delete {student['name']}",
                                ):
                                    _open_delete_dialog(student_id)

            if pages > 1:
                prev_col, count_col, next_col = st.columns(
                    [1, 2, 1], gap="small", vertical_alignment="center"
                )
                with prev_col:
                    previous = st.button(
                        "Previous",
                        key="students_previous",
                        width="stretch",
                        type="secondary",
                        disabled=page == 0,
                    )
                with count_col:
                    st.markdown(
                        f'<div class="pagination-label">Page {page + 1} of {pages}</div>',
                        unsafe_allow_html=True,
                    )
                with next_col:
                    following = st.button(
                        "Next",
                        key="students_next",
                        width="stretch",
                        type="secondary",
                        disabled=page >= pages - 1,
                    )
                if previous:
                    st.session_state.student_page = page - 1
                    st.rerun()
                if following:
                    st.session_state.student_page = page + 1
                    st.rerun()

    dialog_state = st.session_state.get("student_dialog")
    if dialog_state:
        if dialog_state["mode"] == "add":
            _add_student_dialog(dialog_state["nonce"])
        else:
            _edit_student_dialog(
                int(dialog_state["id"]), dialog_state["nonce"]
            )

    delete_state = st.session_state.get("delete_dialog")
    if delete_state:
        _delete_student_dialog(int(delete_state["id"]), delete_state["nonce"])
