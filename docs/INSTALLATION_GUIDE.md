# Installation Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10–3.12 | `dlib`/`face_recognition` wheels are most reliable on these versions |
| Node.js | 18+ | for the Vite/React frontend |
| CMake + a C++ compiler | — | required to build `dlib` if no prebuilt wheel exists for your platform |
| Git | any | |
| Arduino IDE 2.x | — | only needed if flashing the ESP32 |

## 1. Clone and enter the project
```bash
git clone <your-repo-url> smart-classroom
cd smart-classroom
```

## 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

> **`dlib` install issues (common on Windows):** if `pip install dlib` fails
> to build, install a prebuilt wheel matching your Python version from
> https://github.com/z-mahmud22/Dlib_Windows_Python3.x, or install CMake +
> Visual Studio Build Tools (C++ workload) first, then retry.

### Firebase credentials
1. Firebase Console → your project → Project Settings → Service Accounts →
   "Generate new private key" → save as `backend/config/firebase_credentials.json`.
2. Copy `.env.example` to `.env` and set `FIREBASE_CREDENTIALS_PATH` and
   `FIREBASE_STORAGE_BUCKET`.

### Run the backend
```bash
python -m app
```
Visit `http://localhost:5000/api/health` — you should see
`{"success": true, "data": {"status": "online", ...}}`.

## 3. Frontend setup

```bash
cd ../frontend
npm install
npm run dev
```
Visit `http://localhost:5173`.

If the dashboard can't reach the backend, check:
- The backend is running on `http://localhost:5000` (the Vite dev server
  proxies `/api/*` requests there automatically — see `vite.config.js`;
  no separate frontend env var is needed in development)
- `CORS_ALLOWED_ORIGINS` in `backend/.env` includes `http://localhost:5173`
  (only matters for a non-proxied / production same-origin setup)

## 4. Hardware (optional)

See [`hardware/README.md`](../hardware/README.md) for the full ESP32
flashing and wiring process.

## 5. Verify everything end-to-end

1. Register a student: open the dashboard's Students page, add a student
   with 2–3 clear reference photos.
2. Go to Live Monitoring, allow camera access.
3. Confirm the student is recognized, an attendance record appears under
   Attendance → Today, and the Live Monitoring panel shows a live
   attention score.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ECONNREFUSED` from frontend | Backend not running on `localhost:5000`, or `vite.config.js` proxy target changed |
| CORS errors in browser console | `CORS_ALLOWED_ORIGINS` in backend `.env` doesn't include the frontend's origin |
| `FirebaseServiceError: credentials not found` | `FIREBASE_CREDENTIALS_PATH` wrong, or file not downloaded from Firebase Console |
| Face recognition never matches | Re-enroll with better-lit, front-facing reference photos; check `match_tolerance` in `FaceRecognitionService` |
| ESP32 alerts never fire | Confirm `ESP32_IP` in `.env` matches the static IP set in the firmware; test with `curl` per `hardware/README.md` |
