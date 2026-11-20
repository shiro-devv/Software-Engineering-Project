# Roll Call — Student Attendance

A classroom attendance app built with Streamlit and face recognition. It uses
a custom cream-and-navy interface: a login screen, a live dashboard, a
searchable student roster, and a camera scanner that marks attendance once per
student per day.

The app works with two face backends:

1. **`face_recognition` / dlib** (preferred, if installed) — 128-dimensional
   face embeddings.
2. **OpenCV fallback** (installed by default) — Haar face detection plus a
   normalised HOG descriptor. No dlib build required.

The backend is selected automatically at start-up. Both use a distance
threshold of `0.5`; the two descriptor formats are intentionally incompatible,
so re-save student photos after switching backends.

---

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install the core dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 3. Run the app
python -m streamlit run app.py
```

Open <http://localhost:8501> if the browser does not open automatically.

The SQLite database and its `data/` folder are created on first launch. No
manual schema setup is needed.

### Default login

| Username | Password |
| -------- | -------- |
| `admin`  | `admin123` |

Override the seeded credentials before the **first** launch if you want a
different account:

```bash
# macOS / Linux
export ATTENDANCE_ADMIN_USERNAME=teacher
export ATTENDANCE_ADMIN_PASSWORD='choose-a-strong-password'

# Windows PowerShell
$env:ATTENDANCE_ADMIN_USERNAME = "teacher"
$env:ATTENDANCE_ADMIN_PASSWORD = "choose-a-strong-password"
```

The defaults are only used when the database has no users yet. To reset the
admin account, stop the app and delete `data/attendance.db` (this also erases
students and attendance history), then start the app again.

---

## Optional: install the preferred face backend

`face_recognition` gives better accuracy and is more robust to pose and
lighting than the OpenCV fallback. It depends on dlib, which compiles native
code and needs a C++ toolchain. Python 3.10–3.12 is the most reliable range for
prebuilt or easily built dlib wheels.

### Windows

1. Install **CMake** and the **Visual Studio Build Tools** with the
   “Desktop development with C++” workload.
2. From an activated virtual environment:

   ```powershell
   python -m pip install cmake
   python -m pip install dlib
   python -m pip install face_recognition
   ```

If the dlib build fails, a conda environment is often easier:

```powershell
conda create -n attendance python=3.11
conda activate attendance
conda install -c conda-forge dlib
pip install face_recognition
pip install -r requirements.txt
```

### macOS

```bash
brew install cmake
python -m pip install dlib face_recognition
```

On Apple Silicon, make sure the active Python and CMake are both native
`arm64` builds, otherwise the compile can fail with architecture errors.

### Linux (Debian / Ubuntu)

```bash
sudo apt update
sudo apt install -y build-essential cmake python3-dev \
    libopenblas-dev liblapack-dev
python -m pip install dlib face_recognition
```

When the installation succeeds, the app reports `face_recognition` at runtime
and uses 128-D embeddings. Nothing else needs to change.

> **If you switch from the OpenCV fallback to `face_recognition` (or back),
> open each student in the roster and save their photo again.** The two
> backends produce different descriptor sizes. The scanner detects the
> mismatch and shows a “Scanner Unavailable” message instead of producing bad
> matches.

---

## Using the app

### Dashboard

- Today’s date, total students, present today, and absent today are read
  directly from SQLite.
- The activity card lists today’s most recent check-ins.

### Students

- Search by name or student ID. Streamlit applies typed search text when you
  press **Enter** or leave the field.
- Cards show the enrolled photo and today’s status.
- **Add Student** opens a modal. Enter a full name and unique student ID, then
  upload a photo or take one with the camera. The face profile is computed when
  you save; the photo and descriptor are stored in the database.
- **Edit** updates the name, ID, and optionally the photo. Uploading a new photo
  replaces the face profile.
- **Delete** asks for confirmation and removes the student’s photo, face
  profile, and attendance history.
- The roster is paginated, six students per page.

### Attendance

1. Click **SCAN**.
2. Grant camera permission when the browser asks.
3. Ask one student to face the camera in even light and click **Take Photo**.
4. The app detects a face, matches it against enrolled profiles, and writes an
   attendance row for today.
5. Results:
   - **Present** — the first check-in, with the time.
   - **Already Present** — the student was already marked today; no duplicate
     row is written.
   - **Not Recognized** — no enrolled face is close enough.
   - **No Face Found**, **One Face at a Time**, or **Scanner Unavailable** —
     recoverable scan errors with a retry button.

If no students are enrolled, the scanner shows a prompt to add one first.

---

## Project structure

```text
Finals_Project_SE/
├── app.py                  # entry point, routing, CSS injection, DB bootstrap
├── db.py                   # SQLite schema, auth, roster, attendance queries
├── face_utils.py           # face backends, encoding cache, matching, errors
├── styles.css              # full custom theme and component overrides
├── requirements.txt
├── README.md
├── .streamlit/
│   └── config.toml         # cream/navy theme, minimal toolbar
├── assets/                 # optional; drop logo.png/.jpg/.svg here
├── components/
│   ├── __init__.py
│   ├── sidebar.py          # fixed navy navigation rail
│   ├── mascot.py           # original inline SVG camera mascot
│   └── cards.py            # HTML for headers, cards, alerts, student tiles
├── pages_/
│   ├── __init__.py
│   ├── login.py            # login composition and bcrypt validation
│   ├── dashboard.py        # metrics and activity
│   ├── students.py         # search, pagination, add/edit/delete dialogs
│   └── attendance.py       # scan → camera → result flow
└── data/                   # created at runtime
    └── attendance.db       # SQLite database (students, users, logs)
```

The `pages_` folder deliberately is not named `pages`: that keeps Streamlit’s
automatic multipage navigation out of the UI. Navigation is handled with real
keyed buttons in the custom sidebar and `st.session_state["page"]`.

---

## Configuration

| Variable | Purpose | Default |
| -------- | ------- | ------- |
| `ATTENDANCE_DB_PATH` | SQLite file location | `data/attendance.db` |
| `ATTENDANCE_ADMIN_USERNAME` | Seeded admin username | `admin` |
| `ATTENDANCE_ADMIN_PASSWORD` | Seeded admin password | `admin123` |

Design tokens live at the top of `styles.css` (cream `#F8F6EE`, navy
`#1B3A5C`, cards `#C5D1D8`, inputs/active pills `#B8CBDC`, slate `#5B7690`,
photo tiles `#243746`). Streamlit’s base theme is set in
`.streamlit/config.toml`.

Passwords are bcrypt-hashed with 12 rounds. Queries are parameterised, and
database connections are short-lived so Streamlit’s worker threads do not share
a connection.

---

## Notes on the face pipeline

- A capture must contain exactly one usable face. A small secondary Haar
  detection (less than 30% of the main face’s area) is treated as a false
  positive; larger second faces trigger “One Face at a Time”.
- The closest enrolled descriptor wins if its Euclidean distance is `<= 0.5`.
- Known descriptors are cached with `st.cache_resource`, keyed by the roster
  revision. Adding, editing, or deleting a student invalidates the cache.
- Attendance is protected by a unique `(student_id, date)` constraint. The
  `mark_present` helper returns the original time when a student is scanned
  twice, so repeat scans are idempotent.
- Deleting a student cascades to their attendance rows.

---

## Limitations

These are intentional boundaries of the implementation (and, in several cases,
of Streamlit itself):

- **Camera access needs `localhost` or HTTPS.** Browsers block webcams on
  plain HTTP hosts. The UI uses Streamlit’s `st.camera_input`; its live preview,
  permission prompt, and “Take Photo” control are browser/Streamlit widgets,
  not a fully custom viewfinder. The corner brackets are decorative overlays.
- **No liveness or anti-spoofing.** A printed photo can be enrolled or matched.
  Do not use this for security-sensitive attendance.
- **Accuracy depends on the backend and conditions.** The OpenCV HOG fallback
  is a demo-grade recogniser and is sensitive to pose, lighting, and image
  quality. `face_recognition` is noticeably better. Enrol clear, front-facing,
  single-face photos.
- **Switching backends requires re-saving photos.** Fallback descriptors are
  1,764-D; `face_recognition` descriptors are 128-D.
- **Search applies on Enter or blur.** Streamlit text inputs rerun the script
  when the value is committed, not on every keystroke. A custom component would
  be needed for live filtering.
- **Dialogs are Streamlit dialogs.** Their width, centering, close control, and
  scrolling are controlled by Streamlit. At very short viewports a dialog with
  a photo preview and an inline error can scroll.
- **No animation between pages.** Streamlit reruns the whole script; the
  sidebar uses persistent session state rather than client-side routing.
- **Inline feedback, not pop-up toasts.** Streamlit’s toast API is transient
  and visually generic, so success and error messages are rendered inline in
  the app’s own card style.
- **Single admin account.** There is no user management, password reset, or
  role-based access. Change the seeded credentials via environment variables
  or reset the database.
- **SQLite is single-node.** It is appropriate for a classroom laptop, not for
  many concurrent writers or a distributed deployment. Photos are stored as
  BLOBs, so the database grows with the roster.
- **No automated test suite is bundled.** The flows were exercised manually
  with Streamlit and a browser-driven camera. A production version should add
  unit tests around `db.py`, `face_utils.py`, and the attendance idempotency
  guarantee.

### Pixel-perfect fidelity

The layout is built to match the supplied mockup closely, but a few details
cannot be reproduced exactly with Streamlit: native widget internals (camera
permission card, file uploader chips, dialog chrome, scrollbars, and focus
rings) are rendered by Streamlit and the browser. Fonts are loaded from Google
Fonts, so the first render needs network access; otherwise the system sans
fallback is used. Absolute pixel positions also flex with the viewport, while
the mockup is a fixed canvas.

---

## Troubleshooting

**`ModuleNotFoundError: cv2` or scanner unavailable**  
Install the core requirements. OpenCV is the fallback backend and must be
present for the app to scan faces.

**OpenCV 5 error: `module 'cv2' has no attribute 'CascadeClassifier'`**  
OpenCV 5 removed the Python cascade/HOG APIs used by the fallback. Install the
pinned 4.x build:

```bash
python -m pip install "opencv-python-headless>=4.10,<5.0"
```

**dlib installation loops or fails**  
Use Python 3.11/3.12, install CMake and a C++ compiler, or use the conda
instructions above. The app still runs on the OpenCV fallback if you skip
`face_recognition`.

**Camera shows a permission card instead of video**  
Allow camera access in the browser’s site settings and reload. Make sure the
page is served from `localhost` or HTTPS. Close other apps that may hold the
webcam exclusively.

**Changes to student photos are not recognized immediately**  
Use the in-app edit dialog so the face cache is invalidated. If you edit SQLite
directly, restart Streamlit.

**Port 8501 is already in use**  
Run `python -m streamlit run app.py --server.port 8502`.
