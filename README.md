# Smart Classroom — AI Engagement & Attention Tracking System

A full-stack, research-oriented system that uses computer vision and a
configurable weighted-scoring engine to measure student attention in
real time, automate attendance via face recognition, and surface
classroom-wide analytics on a live dashboard — with optional ESP32
hardware for physical alerts (LED/buzzer/LCD).

## Architecture

```
Camera (webcam) → React Dashboard → Flask REST API → Classroom Pipeline
                                                            │
        ┌───────────────┬───────────────┬─────────────────┼──────────────┐
        ▼               ▼               ▼                 ▼              ▼
  Face Detection   Face Recognition  Eye Tracking     Head Pose    Sleep/Yawn
  (MediaPipe)       (face_recognition) (MediaPipe Mesh) (solvePnP)  Detection
        │               │               │                 │              │
        └───────────────┴───────────────┴─────────────────┴──────────────┘
                                        ▼
                          Weighted Attention Engine
                        (config-driven, backend/config/attention_weights.json)
                                        │
                   ┌────────────────────┼────────────────────┐
                   ▼                    ▼                    ▼
            Attendance Manager   Notification Service   Firebase (Firestore)
                                        │
                                        ▼
                                 ESP32 (LED/Buzzer/LCD)
```

## Repository Structure

```
smart-classroom/
├── backend/               # Flask API + CV pipeline (Python)
│   ├── modules/           # face_detection, eye_tracking, head_pose,
│   │                      # sleep_yawn_detection, attention_engine,
│   │                      # face_recognition_module, attendance,
│   │                      # classroom_pipeline (orchestrator)
│   ├── services/          # firebase_service, notification_service, esp32_service
│   ├── api/                # routes.py (REST API blueprint)
│   ├── config/             # attention_weights.json, config_loader.py
│   ├── tests/               # pytest unit tests
│   ├── app.py               # application factory / entrypoint
│   └── requirements.txt
├── frontend/                # React 18 + Vite + Tailwind dashboard
│   └── src/
├── hardware/                 # ESP32 firmware + wiring docs
│   ├── esp32_firmware/
│   └── docs/
├── docs/                      # Installation, deployment, API docs
└── research_paper/            # IEEE-format paper + presentation deck
```

## Quick Start

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then fill in Firebase credentials, ESP32 IP, etc.
python -m app
```
Backend runs on `http://localhost:5000`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard runs on `http://localhost:5173`.

### Hardware (optional)
See `hardware/README.md` for flashing the ESP32 and wiring instructions.

## Documentation

- [`docs/INSTALLATION_GUIDE.md`](docs/INSTALLATION_GUIDE.md)
- [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)
- [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)
- [`hardware/README.md`](hardware/README.md) and [`hardware/docs/wiring_diagram.md`](hardware/docs/wiring_diagram.md)
- [`research_paper/`](research_paper/) — IEEE-format paper and presentation deck

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Attention Scoring

The attention score (0–100) is a weighted combination of six signals —
eye aspect ratio, blink rate, head pose, face presence, sleep duration,
and yawn count — with **all weights and thresholds defined in**
`backend/config/attention_weights.json`, not hardcoded in application
logic. See that file to retune the algorithm without touching code.

**Emotion is not one of these signals.** No genuine emotion-recognition
module is implemented in this project. An earlier version of the engine
included a constant "unknown" emotion sub-score (weight 0.1) in every
calculation, and the Live Classroom panel showed "Emotion Analysis: ON"
whenever the camera was on — both have been corrected (see Known
Limitations below).

## Known Limitations

- **Emotion recognition is not implemented.** It is not part of the
  attention score, and the UI shows "N/A" rather than "ON".
- **Authentication/authorization is not implemented.** `/api/users` is
  basic CRUD, not a login/session system. Do not deploy this publicly
  without adding one (see `docs/API_DOCUMENTATION.md`).
- **ESP32 hardware, ML dependencies (dlib, face-recognition, MediaPipe),
  and a live Firebase project were not available in the environment this
  repair was performed in.** Every code path that touches them was
  reviewed and, where possible, exercised against the real Flask app with
  the CV/Firebase modules stubbed to fail (proving the per-module
  degradation described in "Backend startup behavior" below actually
  works) — but end-to-end behavior with real hardware/credentials still
  needs a runtime pass. See the changelog for exactly what was and
  wasn't verified.
- `pytest` itself could not be installed in that same offline
  environment; the logic in the changed modules was instead re-verified
  with equivalent hand-written assertions run directly against the code
  (see changelog). Run the real suite (`pytest backend/tests/ -v`) after
  installing `requirements.txt`.

## Backend Startup Behavior

Each AI/CV module (face detection, eye tracking, head pose, sleep/yawn,
attention engine, face recognition) is initialized independently and
wrapped in its own try/except. If MediaPipe, dlib, or face-recognition
fail to import or initialize (a common source of platform-specific
breakage), that ONE module is marked `"failed"` in `/api/system/status`
with its real error message — the rest of the backend (attendance,
alerts, students list, reports, analytics) keeps working. The full
camera pipeline (`/api/process-frame`) requires all CV modules to be
healthy and returns a clear `503` naming what's missing otherwise.
Firebase behaves the same way: if it can't connect, `/api/system/status`
reports `"firebase_available": false` explicitly rather than silently
falling back to memory-only storage without telling you.

## Changelog — Repair Pass (2026-08-22)

The following were audited against the actual code (not assumed) and
fixed. Everything else in the codebase was left as-is because it was
already correct.

| Issue | File(s) | Fix | Verified how |
|---|---|---|---|
| `Camera` status in the sidebar used `liveStudents.length >= 0`, which is always `true` | `frontend/src/App.jsx`, `LiveFeedPanel.jsx` | Camera now reports real state (permission, stream active, last frame sent) up to `App`; status uses that | Code review (logic is unit-testable but needs a browser to fully exercise `getUserMedia`) — **REQUIRES RUNTIME VERIFICATION** in-browser |
| `buildDailyAnalyticsPlaceholder` fabricated 6 of 7 "historical" days as zero | `frontend/src/App.jsx`, `DailyAnalyticsPanel.jsx`, `backend/api/routes.py`, `backend/services/firebase_service.py` | Removed the placeholder. Added real `GET /api/analytics/daily`, aggregating persisted `attention_logs`/`attendance` from Firestore; returns `storage_available:false` + empty list (not fake data) when Firebase isn't configured | Booted the real Flask app (Firebase disabled) with the actual test client and confirmed the endpoint returns the honest empty state; full Firestore aggregation still needs a live project — **REQUIRES RUNTIME VERIFICATION** |
| An unimplemented "emotion" signal (always `"unknown"`) silently contributed 10% weight to every attention score; UI claimed "Emotion Analysis: ON" | `backend/config/attention_weights.json`, `backend/modules/attention_engine.py`, `frontend/src/components/LiveFeedPanel.jsx` | Removed emotion from the scoring engine and renormalized the remaining 6 weights to sum to 1.0; UI now shows "N/A" | Re-ran the engine's test scenarios (fully-attentive, sleeping) by hand against the live code — scores/levels unchanged in shape, weights confirmed to sum to 1.0, `emotion` key absent from both weights and sub-scores |
| `AttendanceManager` never reloaded today's Firestore records on startup, so a backend restart mid-class showed 0 present even though data was safely persisted | `backend/modules/attendance.py`, `backend/app.py`, `backend/tests/test_attendance.py` | Added `load_today_from_storage()`, called once at app boot when Firebase is configured; added 2 new tests | Manually executed the new + existing attendance tests' logic directly against the code (pytest wasn't installable offline) — all passed, including duplicate-prevention |
| Frame capture could send overlapping `/api/process-frame` requests if a response took longer than the 1.5s interval | `frontend/src/components/LiveFeedPanel.jsx` | Added an in-flight guard so a new frame is only sent once the previous one resolves | Code review — **REQUIRES RUNTIME VERIFICATION** in-browser |

**Confirmed already correct (no change made):** duplicate-attendance
prevention (deterministic per-student-per-day keying), alert
cooldown/deduplication, the `{success, data|error}` API response
envelope, per-module `/api/system/status` reporting, and Firebase
initialization failing loudly rather than being swallowed.

**Not attempted in this pass** (see spec for full detail): the dashboard
information-architecture redesign (sidebar grouping, glassmorphism/color
system reduction, Quick Actions), authentication implementation,
canonical `alert_id`/`resolved` fields on the Alert schema, and
structured `{code, message}` error bodies (current errors are
`{"success": false, "error": "<message>"}`, which is consistent but not
the exact shape in the original spec). These are real, scoped gaps —
not silently skipped — and are good next steps.

## License

Academic / final-year-project use. Adapt freely for coursework and
research with attribution.
