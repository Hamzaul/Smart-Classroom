from __future__ import annotations

import base64
import logging
from datetime import date, timedelta
from io import BytesIO

import numpy as np
from flask import Blueprint, current_app, jsonify, request, send_file
from PIL import Image

from backend.modules.attention_engine import FrameSignals
from backend.services.backup_service import BackupServiceError
from backend.services.report_service import ReportServiceError
from backend.services.user_service import UserServiceError
from backend.config.config_loader import (
    ConfigError, get_attention_config, save_attention_weights,
)

logger = logging.getLogger("smart_classroom.api")

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


def _json_safe(value):
    """Recursively convert NumPy values to standard Python JSON types."""
    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    return value


def _ok(data, status: int = 200):
    return jsonify({
        "success": True,
        "data": _json_safe(data),
    }), status


def _decode_base64_image(b64_string: str) -> np.ndarray:
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    image_bytes = base64.b64decode(b64_string)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    return np.array(image)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@api_bp.route("/health", methods=["GET"])
def health_check():
    return _ok({"status": "online", "service": "smart-classroom-backend"})


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
@api_bp.route("/students", methods=["GET"])
def list_students():
    recognition_service = current_app.config.get("FACE_RECOGNITION_SERVICE")
    if recognition_service is None:
        return _error(
            "Face recognition module is unavailable (failed to initialize — "
            "see /api/system/status for details)", 503,
        )
    try:
        return _ok(recognition_service.list_enrolled())
    except Exception as e:
        logger.exception("Failed to list students")
        return _error(f"Failed to list students: {e}", 500)


@api_bp.route("/students/register", methods=["POST"])
def register_student():
    """
    Body: { "name": str, "roll_number": str, "images": [base64_str, ...] }
    """
    body = request.get_json(silent=True)
    if not body:
        return _error("Request body must be valid JSON")

    name = body.get("name", "").strip()
    roll_number = body.get("roll_number", "").strip()
    images_b64 = body.get("images", [])

    if not name:
        return _error("Field 'name' is required")
    if not roll_number:
        return _error("Field 'roll_number' is required")
    if not images_b64 or not isinstance(images_b64, list):
        return _error("Field 'images' must be a non-empty list of base64 images")

    try:
        images_rgb = [_decode_base64_image(b64) for b64 in images_b64]
    except Exception as e:
        return _error(f"Could not decode one or more images: {e}")

    recognition_service = current_app.config.get("FACE_RECOGNITION_SERVICE")
    if recognition_service is None:
        return _error(
            "Face recognition module is unavailable (failed to initialize — "
            "see /api/system/status for details)", 503,
        )
    try:
        record = recognition_service.enroll_student(
            name=name, roll_number=roll_number, reference_images_rgb=images_rgb
        )
        return _ok(
            {
                "student_id": record.student_id,
                "name": record.name,
                "roll_number": record.roll_number,
            },
            status=201,
        )
    except Exception as e:
        logger.exception("Enrollment failed for %s", name)
        return _error(str(e), 422)


@api_bp.route("/students/<student_id>", methods=["DELETE"])
def delete_student(student_id: str):
    recognition_service = current_app.config.get("FACE_RECOGNITION_SERVICE")
    if recognition_service is None:
        return _error(
            "Face recognition module is unavailable (failed to initialize — "
            "see /api/system/status for details)", 503,
        )
    try:
        recognition_service.remove_student(student_id)
        return _ok({"deleted": student_id})
    except Exception as e:
        logger.exception("Failed to delete student %s", student_id)
        return _error(str(e), 500)


# ---------------------------------------------------------------------------
# Frame processing (core pipeline entrypoint — called per camera frame)
# ---------------------------------------------------------------------------
@api_bp.route("/process-frame", methods=["POST"])
def process_frame():
    """
    Body: { "image": base64_str }

    Runs the full pipeline: face detection -> recognition -> eye tracking ->
    head pose -> sleep/yawn -> attention scoring -> attendance marking ->
    alert generation. Returns per-student results for the live dashboard.
    """
    body = request.get_json(silent=True)
    if not body or "image" not in body:
        return _error("Field 'image' (base64) is required")

    try:
        frame_rgb = _decode_base64_image(body["image"])
    except Exception as e:
        return _error(f"Could not decode image: {e}")

    pipeline = current_app.config.get("CLASSROOM_PIPELINE")
    if pipeline is None:
        return _error(
            "AI processing pipeline is unavailable — one or more CV modules "
            "failed to initialize at startup. See /api/system/status for "
            "which module and why.", 503,
        )
    try:
        results = pipeline.process_frame(frame_rgb)
        return _ok(results)
    except Exception as e:
        logger.exception("Frame processing failed")
        return _error(f"Frame processing failed: {e}", 500)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
@api_bp.route("/attendance/today", methods=["GET"])
def attendance_today():
    try:
        attendance_manager = current_app.config["ATTENDANCE_MANAGER"]
        records = attendance_manager.get_today_records()
        summary = attendance_manager.get_today_summary()
        return _ok(
            {
                "summary": summary,
                "records": [
                    {
                        "student_id": r.student_id,
                        "name": r.name,
                        "roll_number": r.roll_number,
                        "status": r.status,
                        "first_seen": r.first_seen,
                        "last_seen": r.last_seen,
                    }
                    for r in records
                ],
            }
        )
    except Exception as e:
        logger.exception("Failed to fetch today's attendance")
        return _error(str(e), 500)


@api_bp.route("/attendance/range", methods=["GET"])
def attendance_range():
    """Query params: start=YYYY-MM-DD, end=YYYY-MM-DD (defaults to last 7 days)."""
    end_str = request.args.get("end", date.today().isoformat())
    start_str = request.args.get(
        "start", (date.today() - timedelta(days=7)).isoformat()
    )
    firebase = current_app.config.get("FIREBASE_SERVICE")
    if firebase is None:
        return _ok({
            "start": start_str, "end": end_str, "records": [],
            "storage_available": False,
            "note": "Firestore is not configured, so historical attendance "
                    "across a date range isn't available. Today's attendance "
                    "still works via /api/attendance/today.",
        })
    try:
        records = firebase.get_attendance_range(start_str, end_str)
        return _ok({"start": start_str, "end": end_str, "records": records, "storage_available": True})
    except Exception as e:
        logger.exception("Failed to fetch attendance range")
        return _error(str(e), 500)


# ---------------------------------------------------------------------------
# Attention analytics
# ---------------------------------------------------------------------------
@api_bp.route("/attention/history/<student_id>", methods=["GET"])
def attention_history(student_id: str):
    date_str = request.args.get("date", date.today().isoformat())
    firebase = current_app.config.get("FIREBASE_SERVICE")
    if firebase is None:
        return _ok({
            "student_id": student_id, "date": date_str, "history": [],
            "storage_available": False,
            "note": "Firestore is not configured, so per-student attention "
                    "history isn't retained across requests.",
        })
    try:
        history = firebase.get_attention_history(date_str, student_id)
        return _ok({"student_id": student_id, "date": date_str, "history": history, "storage_available": True})
    except Exception as e:
        logger.exception("Failed to fetch attention history for %s", student_id)
        return _error(str(e), 500)


@api_bp.route("/analytics/daily", methods=["GET"])
def analytics_daily():
    """
    Query params: days=N (default 7, max 31).

    Real, Firestore-backed daily history for the "Daily Analytics" chart —
    replaces the removed frontend `buildDailyAnalyticsPlaceholder`, which
    fabricated 6 of every 7 days as zero. When Firebase is not configured
    this returns storage_available: False and an EMPTY days list (never
    fake data); the frontend renders an explicit empty/offline state.
    """
    try:
        n_days = int(request.args.get("days", 7))
    except (TypeError, ValueError):
        return _error("'days' must be an integer")
    if n_days < 1 or n_days > 31:
        return _error("'days' must be between 1 and 31")

    firebase = current_app.config.get("FIREBASE_SERVICE")
    if firebase is None:
        return _ok({
            "days": [],
            "storage_available": False,
            "note": "Firestore is not configured, so historical daily "
                    "analytics can't be computed. Live, in-session data is "
                    "still available on the dashboard.",
        })

    try:
        days = []
        for i in range(n_days - 1, -1, -1):
            d = date.today() - timedelta(days=i)
            date_str = d.isoformat()
            summary = firebase.get_daily_summary(date_str)
            days.append({
                "date": date_str,
                "label": d.strftime("%d %b"),
                "avgAttention": summary["avg_attention"],
                "lowAttentionCount": summary["low_attention_count"],
                "presentCount": summary["present_count"],
                "hasData": summary["has_data"],
            })
        return _ok({"days": days, "storage_available": True})
    except Exception as e:
        logger.exception("Failed to compute daily analytics")
        return _error(str(e), 500)


@api_bp.route("/analytics/class-summary", methods=["GET"])
def class_summary():
    pipeline = current_app.config.get("CLASSROOM_PIPELINE")
    if pipeline is None:
        return _ok({
            "total_students": 0, "avg_attention": 0, "low_attention_count": 0,
            "sleeping_count": 0, "yawning_count": 0, "pipeline_available": False,
        })
    try:
        summary = pipeline.get_class_summary()
        return _ok({**summary, "pipeline_available": True})
    except Exception as e:
        logger.exception("Failed to compute class summary")
        return _error(str(e), 500)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
@api_bp.route("/alerts/recent", methods=["GET"])
def recent_alerts():
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        return _error("'limit' must be an integer")
    if limit < 1 or limit > 500:
        return _error("'limit' must be between 1 and 500")

    notifier = current_app.config.get("NOTIFICATION_SERVICE")
    if notifier is None:
        return _ok([])
    try:
        return _ok(notifier.get_recent_alerts(limit=limit))
    except Exception as e:
        logger.exception("Failed to fetch recent alerts")
        return _error(f"Failed to fetch recent alerts: {e}", 500)


# ---------------------------------------------------------------------------
# ESP32 / hardware status
# ---------------------------------------------------------------------------
@api_bp.route("/devices/esp32/status", methods=["GET"])
def esp32_status():
    esp32 = current_app.config.get("ESP32_SERVICE")
    if esp32 is None:
        return _ok({"online": False, "reason": "ESP32 service disabled"})
    status = esp32.get_status()
    return _ok(
        {
            "online": status.online,
            "last_success": status.last_success,
            "last_error": status.last_error,
        }
    )


# ---------------------------------------------------------------------------
# System / AI module status (backs the "Models & AI" page)
# ---------------------------------------------------------------------------
@api_bp.route("/system/status", methods=["GET"])
def system_status():
    module_status = current_app.config.get("MODULE_STATUS", {})
    pipeline = current_app.config.get("CLASSROOM_PIPELINE")
    firebase = current_app.config.get("FIREBASE_SERVICE")
    esp32 = current_app.config.get("ESP32_SERVICE")

    modules = [
        {"key": k, "status": v["status"], "error": v["error"]}
        for k, v in module_status.items()
    ]
    return _ok({
        "modules": modules,
        "pipeline_available": pipeline is not None,
        "firebase_available": firebase is not None,
        "esp32_configured": esp32 is not None,
    })


# ---------------------------------------------------------------------------
# Logs (backs the "Logs" page) — in-memory ring buffer, never exposes secrets
# ---------------------------------------------------------------------------
@api_bp.route("/logs", methods=["GET"])
def get_logs():
    handler = current_app.config.get("LOG_HANDLER")
    if handler is None:
        return _ok([])
    try:
        limit = int(request.args.get("limit", 200))
    except (TypeError, ValueError):
        return _error("'limit' must be an integer")
    level = request.args.get("level")
    return _ok(handler.get_recent(limit=limit, level=level))


# ---------------------------------------------------------------------------
# Users (admin/instructor accounts — backs the "Users" page)
# ---------------------------------------------------------------------------
@api_bp.route("/users", methods=["GET"])
def list_users():
    user_service = current_app.config["USER_SERVICE"]
    return _ok(user_service.list_users())


@api_bp.route("/users", methods=["POST"])
def create_user():
    body = request.get_json(silent=True)
    if not body:
        return _error("Request body must be valid JSON")
    user_service = current_app.config["USER_SERVICE"]
    try:
        user = user_service.create_user(
            name=body.get("name", ""), email=body.get("email", ""), role=body.get("role", "")
        )
        return _ok(
            {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role},
            status=201,
        )
    except UserServiceError as e:
        return _error(str(e), 422)


@api_bp.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id: str):
    user_service = current_app.config["USER_SERVICE"]
    try:
        user_service.delete_user(user_id)
        return _ok({"deleted": user_id})
    except UserServiceError as e:
        return _error(str(e), 422)


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------
@api_bp.route("/backup/create", methods=["POST"])
def create_backup():
    backup_service = current_app.config["BACKUP_SERVICE"]
    try:
        result = backup_service.create_backup()
        return _ok(
            {k: v for k, v in result.items() if k in ("filename", "backup_id", "created_at", "data_source")},
            status=201,
        )
    except Exception as e:
        logger.exception("Backup creation failed")
        return _error(f"Backup creation failed: {e}", 500)


@api_bp.route("/backup/list", methods=["GET"])
def list_backups():
    backup_service = current_app.config["BACKUP_SERVICE"]
    try:
        return _ok(backup_service.list_backups())
    except Exception as e:
        logger.exception("Failed to list backups")
        return _error(str(e), 500)


@api_bp.route("/backup/restore", methods=["POST"])
def restore_backup():
    body = request.get_json(silent=True)
    if not body or not body.get("filename"):
        return _error("Field 'filename' is required")
    backup_service = current_app.config["BACKUP_SERVICE"]
    try:
        result = backup_service.restore_backup(body["filename"])
        return _ok(result)
    except BackupServiceError as e:
        return _error(str(e), 404)
    except Exception as e:
        logger.exception("Restore failed")
        return _error(f"Restore failed: {e}", 500)


# ---------------------------------------------------------------------------
# Reports (PDF generation via reportlab)
# ---------------------------------------------------------------------------
@api_bp.route("/reports/generate", methods=["GET"])
def generate_report():
    start = request.args.get("start")
    end = request.args.get("end")
    report_service = current_app.config["REPORT_SERVICE"]
    try:
        result = report_service.generate_attendance_report(start_date=start, end_date=end)
        return send_file(
            result["path"], as_attachment=True, download_name=result["filename"],
            mimetype="application/pdf",
        )
    except ReportServiceError as e:
        return _error(str(e), 400)
    except Exception as e:
        logger.exception("Report generation failed")
        return _error(f"Report generation failed: {e}", 500)


# ---------------------------------------------------------------------------
# Settings — attention scoring weights (backs the "Settings" page)
# ---------------------------------------------------------------------------
@api_bp.route("/settings/attention-weights", methods=["GET"])
def get_attention_weights():
    try:
        config = get_attention_config()
        return _ok({"weights": config.weights, "thresholds": config.thresholds})
    except ConfigError as e:
        return _error(str(e), 500)


@api_bp.route("/settings/attention-weights", methods=["PUT"])
def update_attention_weights():
    body = request.get_json(silent=True)
    if not body or "weights" not in body:
        return _error("Field 'weights' (object) is required")
    try:
        updated = save_attention_weights(body["weights"])
        return _ok({"weights": updated.weights})
    except ConfigError as e:
        return _error(str(e), 422)
