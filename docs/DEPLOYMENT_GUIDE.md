# Deployment Guide

## Backend (Flask + eventlet, via Gunicorn)

1. Set `FLASK_ENV=production` and a strong random `FLASK_SECRET_KEY` in `.env`.
2. Set `USE_EVENTLET=true` if deploying behind an eventlet worker (recommended
   for handling concurrent `/process-frame` requests from multiple cameras).
3. Run with Gunicorn:
   ```bash
   pip install gunicorn eventlet
   gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 "backend.app:create_app()"
   ```
   Use exactly **one** eventlet worker unless you've verified your Firebase
   client and CV models are safe to share across forked workers — eventlet's
   cooperative concurrency handles many simultaneous requests within a
   single process already.
4. Put Nginx (or another reverse proxy) in front for TLS termination and
   to serve static files if you bundle the frontend build alongside.

### Common pitfall: `load_dotenv` ordering
All environment variable access goes through `backend/config/config_loader.py`,
which calls `load_dotenv()` at **import time**, before any other module reads
`os.environ`. Do not call `os.getenv(...)` directly elsewhere in the
codebase — import `get_app_settings()` from `config_loader` instead, or
you can reintroduce the exact class of startup bug (env vars read as
`None` because they hadn't been loaded yet) this project already fixed once.

## Frontend (static build)

```bash
cd frontend
npm run build
```
This produces `frontend/dist/` — deploy it to any static host (Vercel,
Netlify, Firebase Hosting, or Nginx serving static files). The frontend
calls the API at the relative path `/api/*` (see `src/api/client.js`),
so in production put a reverse proxy (Nginx, or your host's rewrite
rules) in front that serves the built static files **and** forwards
`/api/*` to the Flask backend on the same origin — this avoids needing
a separate CORS-enabled cross-origin setup in production. If you'd
rather deploy frontend and backend on different origins, add an env-based
base URL to `src/api/client.js` and set `CORS_ALLOWED_ORIGINS` accordingly.

## Firebase

- Firestore security rules should restrict write access to
  authenticated backend service-account requests only; the frontend
  never talks to Firestore directly in this architecture — everything
  goes through the Flask API.
- Enable daily Firestore backups (Firebase Console → Firestore →
  Backups) for the automatic-backup requirement.

## ESP32

The ESP32 is a LAN-local device (static IP on the classroom WiFi) — it
is not exposed to the internet. If the backend is deployed off-site
(cloud-hosted) rather than on a classroom-local server, the ESP32 will
be unreachable; either deploy the backend on local classroom
infrastructure, or route ESP32 commands through a lightweight local
relay service on the same LAN as the device.

## Environment Checklist Before Going Live

- [ ] `FLASK_SECRET_KEY` is a strong random value, not the `.env.example` default
- [ ] `FLASK_ENV=production` (disables Flask debug mode / stack-trace leakage)
- [ ] `CORS_ALLOWED_ORIGINS` restricted to your actual deployed frontend origin(s)
- [ ] Firebase credentials file is **not** committed to version control
- [ ] Firestore security rules reviewed
- [ ] `backend/config/attention_weights.json` weights reviewed/tuned against
      real classroom pilot data before relying on scores for decisions
