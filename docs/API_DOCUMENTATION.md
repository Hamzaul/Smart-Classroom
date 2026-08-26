# API Documentation

Base URL: `http://localhost:5000/api`

All responses follow the shape:
```json
{ "success": true, "data": { ... } }
{ "success": false, "error": "message" }
```

## Health

### `GET /health`
Returns service status. No auth required.

**Response**
```json
{ "success": true, "data": { "status": "online", "service": "smart-classroom-backend" } }
```

---

## Students

### `GET /students`
List all enrolled students.

### `POST /students/register`
Enroll a new student from one or more reference photos.

**Body**
```json
{
  "name": "Aman Kumar",
  "roll_number": "21CS001",
  "images": ["data:image/jpeg;base64,...", "data:image/jpeg;base64,..."]
}
```
- `images`: 1+ base64-encoded photos, each containing exactly one clearly
  visible face. Multiple photos improve recognition robustness — the
  encoding is averaged across all provided images.

**Response (201)**
```json
{ "success": true, "data": { "student_id": "uuid", "name": "Aman Kumar", "roll_number": "21CS001" } }
```

**Errors (422)**: no face found, or multiple faces found, in a reference image.

### `DELETE /students/<student_id>`
Remove a student's enrollment (encoding + profile).

---

## Frame Processing (core pipeline)

### `POST /process-frame`
Runs the full CV pipeline on a single frame: detection → recognition →
eye tracking → head pose → sleep/yawn → attention scoring → attendance
marking → alert generation.

**Body**
```json
{ "image": "data:image/jpeg;base64,..." }
```

**Response**
```json
{
  "success": true,
  "data": {
    "timestamp": 1733600000.123,
    "frame_dimensions": { "width": 1280, "height": 720 },
    "students_detected": 2,
    "students": [
      {
        "student_id": "uuid",
        "name": "Aman Kumar",
        "roll_number": "21CS001",
        "is_known": true,
        "recognition_confidence": 0.93,
        "bbox": { "top": 40, "right": 220, "bottom": 200, "left": 60 },
        "attention_score": 92.4,
        "attention_level": "excellent",
        "sub_scores": {
          "eye_aspect_ratio": 70.0, "blink_rate": 100.0, "head_pose": 92.0,
          "face_presence": 100.0, "sleep_duration": 100.0,
          "yawn_count": 100.0, "emotion": 100.0
        },
        "is_sleeping": false,
        "is_yawning": false,
        "head_pose": { "yaw": 2.1, "pitch": 1.0, "roll": -0.4, "is_looking_away": false }
      }
    ]
  }
}
```

Recommended polling interval from the frontend: every 1–2 seconds
(higher frequency gives smoother tracking but costs more CPU on both
ends; the attention engine's internal smoothing already compensates for
some frame-rate variability).

---

## Attendance

### `GET /attendance/today`
Today's attendance summary and per-student records.

### `GET /attendance/range?start=YYYY-MM-DD&end=YYYY-MM-DD`
Attendance records across a date range (defaults to the last 7 days).

---

## Attention Analytics

### `GET /attention/history/<student_id>?date=YYYY-MM-DD`
Raw attention-score history for one student on one date (defaults to today).

### `GET /analytics/class-summary`
Aggregated class-wide snapshot: average attention, count of low-attention
students, sleeping count, yawning count — computed from the most recent
processed frame per student.

### `GET /analytics/daily?days=N` (default 7, max 31)
Real, Firestore-aggregated per-day history: average attention, low-attention
event count, and present count for each of the last N days — computed from
persisted `attention_logs` and `attendance` records, never fabricated.
```json
{
  "success": true,
  "data": {
    "days": [
      {"date": "2026-08-20", "label": "20 Aug", "avgAttention": 74.2,
       "lowAttentionCount": 3, "presentCount": 28, "hasData": true}
    ],
    "storage_available": true
  }
}
```
When Firebase is not configured, returns `"storage_available": false` and
`"days": []` — the frontend shows an explicit "Database unavailable" empty
state rather than a chart of zeros.

---

## Alerts

### `GET /alerts/recent?limit=50`
Most recent alerts (sleeping, yawning, low attention, unrecognized
person), newest first.

---

## Devices

### `GET /devices/esp32/status`
```json
{ "success": true, "data": { "online": true, "last_success": 1733600000.1, "last_error": null } }
```

---

## Error Handling

All endpoints validate their inputs and return `400` for malformed
requests, `422` for semantically invalid requests (e.g. no face in an
enrollment photo), and `500` with a logged stack trace for unexpected
failures. The Flask app also registers global `404` and `500` handlers
so unmatched routes and unhandled exceptions still return the standard
`{success, error}` JSON shape rather than an HTML error page.
