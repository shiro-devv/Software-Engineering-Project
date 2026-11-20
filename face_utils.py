"""Face enrolment and matching helpers.

``face_recognition`` is used when it is available.  Because dlib (and therefore
``face_recognition``) is awkward to install on some machines, the module also
ships with a dependency-light OpenCV fallback.  The fallback is intentionally
simple: a Haar face detector plus a HOG descriptor.  It is suitable for a
classroom demo, not for security-critical identification.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

import db

try:  # pragma: no cover - availability depends on the host machine
    import face_recognition as _face_recognition
except Exception:  # ImportError, dlib load failures, unsupported Python, ...
    _face_recognition = None

try:  # pragma: no cover - availability depends on the host machine
    import cv2 as _cv2
except Exception:
    _cv2 = None


FACE_MATCH_TOLERANCE = 0.5
FACE_RECOGNITION_AVAILABLE = _face_recognition is not None
OPENCV_AVAILABLE = _cv2 is not None
MAX_ENCODING_EDGE = 1800
MAX_SAVED_PHOTO_EDGE = 800


class FaceProcessingError(Exception):
    """A user-safe face processing error with an on-brand message."""

    def __init__(self, message: str, code: str = "face_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class FaceMatch:
    """The closest enrolled student for a captured face."""

    student_id: int
    name: str
    distance: float


def recognition_backend() -> str | None:
    """Return the active recognition backend identifier."""
    if FACE_RECOGNITION_AVAILABLE:
        return "face_recognition"
    if OPENCV_AVAILABLE:
        return "opencv"
    return None


def backend_label() -> str:
    """Human-friendly backend name for inline helper text."""
    labels = {
        "face_recognition": "face_recognition",
        "opencv": "OpenCV fallback",
        None: "unavailable",
    }
    return labels[recognition_backend()]


def _decode_rgb(image_bytes: bytes) -> np.ndarray:
    """Open common image formats and return a sanitised RGB array."""
    if not image_bytes:
        raise FaceProcessingError(
            "We didn't receive an image. Please try again.", "no_image"
        )
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", image.size, (248, 246, 238))
                alpha = image.getchannel("A")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            if max(image.size) > MAX_ENCODING_EDGE:
                image.thumbnail((MAX_ENCODING_EDGE, MAX_ENCODING_EDGE))
            return np.asarray(image, dtype=np.uint8).copy()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise FaceProcessingError(
            "That image couldn't be opened. Please use a clear JPG or PNG photo.",
            "bad_image",
        ) from exc


def prepare_photo(image_bytes: bytes) -> tuple[np.ndarray, bytes]:
    """Return an RGB array and a compact JPEG suitable for the database."""
    rgb = _decode_rgb(image_bytes)
    try:
        image = Image.fromarray(rgb)
        image.thumbnail((MAX_SAVED_PHOTO_EDGE, MAX_SAVED_PHOTO_EDGE))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return rgb, output.getvalue()
    except (OSError, ValueError) as exc:
        raise FaceProcessingError(
            "We couldn't prepare that photo. Please try another image.",
            "bad_image",
        ) from exc


def _face_recognition_encoding(rgb: np.ndarray) -> np.ndarray:
    """Extract a 128-D dlib embedding, rejecting zero or multiple faces."""
    assert _face_recognition is not None
    try:
        locations = _face_recognition.face_locations(
            rgb, number_of_times_to_upsample=1, model="hog"
        )
    except Exception as exc:
        raise FaceProcessingError(
            "Face detection couldn't start. Check the face_recognition/dlib installation.",
            "backend_error",
        ) from exc

    if not locations:
        raise FaceProcessingError(
            "We couldn't spot a face. Face the camera in even light and try again.",
            "no_face",
        )
    if len(locations) > 1:
        raise FaceProcessingError(
            "More than one face is in frame. Please scan one student at a time.",
            "multiple_faces",
        )

    try:
        encodings = _face_recognition.face_encodings(
            rgb, known_face_locations=locations, num_jitters=1, model="small"
        )
    except Exception as exc:
        raise FaceProcessingError(
            "We found a face but couldn't read it. Please try a clearer photo.",
            "encoding_failed",
        ) from exc

    if not encodings:
        raise FaceProcessingError(
            "We found a face but couldn't read it. Please try a clearer photo.",
            "encoding_failed",
        )
    return np.asarray(encodings[0], dtype=np.float32)


@lru_cache(maxsize=1)
def _haar_cascade() -> Any:
    if _cv2 is None:
        return None
    path = _cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = _cv2.CascadeClassifier(path)
    return None if cascade.empty() else cascade


def _opencv_encoding(rgb: np.ndarray) -> np.ndarray:
    """Create a normalised HOG descriptor from one detected face."""
    if _cv2 is None:
        raise FaceProcessingError(
            "Face recognition isn't available. Install face_recognition or OpenCV.",
            "backend_unavailable",
        )
    cascade = _haar_cascade()
    if cascade is None:
        raise FaceProcessingError(
            "The OpenCV face model couldn't load. Reinstall opencv-python-headless.",
            "backend_error",
        )

    try:
        gray = _cv2.cvtColor(rgb, _cv2.COLOR_RGB2GRAY)
        equalised = _cv2.equalizeHist(gray)
        faces = cascade.detectMultiScale(
            equalised,
            scaleFactor=1.08,
            minNeighbors=6,
            minSize=(64, 64),
        )
    except Exception as exc:
        raise FaceProcessingError(
            "Face detection couldn't start. Please try again.", "backend_error"
        ) from exc

    if len(faces) == 0:
        raise FaceProcessingError(
            "We couldn't spot a face. Face the camera in even light and try again.",
            "no_face",
        )
    if len(faces) > 1:
        # Haar occasionally reports a small false positive in a portrait (a
        # hand, a pattern on clothing, a face in a poster).  Only treat the
        # capture as a group photo when the runner-up face is large enough to
        # be a real person standing beside the student.
        ranked = sorted(
            faces, key=lambda box: int(box[2]) * int(box[3]), reverse=True
        )
        largest_area = int(ranked[0][2]) * int(ranked[0][3])
        second_area = int(ranked[1][2]) * int(ranked[1][3])
        if second_area >= largest_area * 0.3:
            raise FaceProcessingError(
                "More than one face is in frame. Please scan one student at a time.",
                "multiple_faces",
            )
        faces = [ranked[0]]

    x, y, width, height = (int(value) for value in faces[0])
    margin = int(min(width, height) * 0.16)
    x0 = max(0, x - margin)
    y0 = max(0, y - margin)
    x1 = min(gray.shape[1], x + width + margin)
    y1 = min(gray.shape[0], y + height + margin)
    face = _cv2.resize(
        _cv2.equalizeHist(gray[y0:y1, x0:x1]), (64, 64), interpolation=_cv2.INTER_AREA
    )

    hog = _cv2.HOGDescriptor(
        (64, 64), (16, 16), (8, 8), (8, 8), 9
    )
    descriptor = np.asarray(hog.compute(face), dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(descriptor))
    if norm < 1e-8:
        raise FaceProcessingError(
            "That face wasn't clear enough. Please try another photo.",
            "encoding_failed",
        )
    return descriptor / norm


def compute_face_encoding(image_bytes: bytes) -> np.ndarray:
    """Detect exactly one face and return its embedding.

    Raises :class:`FaceProcessingError` with a friendly explanation for the
    common cases: no face, multiple faces, an unreadable image, or no backend.
    """
    rgb = _decode_rgb(image_bytes)
    backend = recognition_backend()
    if backend == "face_recognition":
        return _face_recognition_encoding(rgb)
    if backend == "opencv":
        return _opencv_encoding(rgb)
    raise FaceProcessingError(
        "Face recognition isn't available. Install face_recognition or OpenCV, then restart the app.",
        "backend_unavailable",
    )


def serialize_encoding(encoding: np.ndarray) -> bytes:
    """Serialise a numpy embedding for the BLOB column."""
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(encoding, dtype=np.float32), allow_pickle=False)
    return buffer.getvalue()


def deserialize_encoding(blob: bytes | None) -> np.ndarray | None:
    """Restore an embedding, tolerating legacy raw-array blobs."""
    if not blob:
        return None
    try:
        return np.asarray(
            np.load(io.BytesIO(blob), allow_pickle=False), dtype=np.float32
        ).reshape(-1)
    except (ValueError, OSError):
        try:
            return np.frombuffer(blob, dtype=np.float32).copy()
        except (ValueError, TypeError):
            return None


@st.cache_resource(show_spinner=False)
def load_known_faces(cache_revision: int) -> list[dict[str, Any]]:
    """Cache enrolled embeddings until the student roster changes."""
    del cache_revision  # Only used as part of the cache key.
    known: list[dict[str, Any]] = []
    for row in db.list_face_encodings():
        encoding = deserialize_encoding(row.get("face_encoding"))
        if encoding is not None and encoding.size:
            known.append(
                {
                    "id": int(row["id"]),
                    "name": str(row["name"]),
                    "encoding": encoding,
                }
            )
    return known


def invalidate_known_faces() -> None:
    """Clear the resource cache and move the session cache key forward."""
    load_known_faces.clear()
    revision = int(st.session_state.get("students_revision", 0))
    st.session_state.students_revision = revision + 1


def find_best_match(
    encoding: np.ndarray,
    known_faces: list[dict[str, Any]],
    tolerance: float = FACE_MATCH_TOLERANCE,
) -> FaceMatch | None:
    """Return the nearest enrolled face inside the tolerance window."""
    if not known_faces:
        return None

    compatible = [
        face
        for face in known_faces
        if face["encoding"].size == encoding.size
    ]
    if not compatible:
        raise FaceProcessingError(
            "This roster uses a different face-recognition backend. Re-save the student photos to re-enrol them.",
            "backend_mismatch",
        )

    distances = np.array(
        [
            float(np.linalg.norm(face["encoding"] - encoding))
            for face in compatible
        ]
    )
    best_index = int(np.argmin(distances))
    best_distance = float(distances[best_index])
    if best_distance > tolerance:
        return None

    best = compatible[best_index]
    return FaceMatch(
        student_id=int(best["id"]),
        name=str(best["name"]),
        distance=best_distance,
    )
