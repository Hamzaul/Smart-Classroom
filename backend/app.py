"""
backend/app.py

Application entrypoint.

Uses the Flask "application factory" pattern (`create_app`) so tests can
spin up isolated instances. This is also where dependency injection
happens: every service/module is constructed once here and handed to
the pieces that need it, rather than modules reaching for global
singletons (the one exception being config, which is safe to be global
since it's read-only after load).

Run with:
    python -m backend.app
or via a WSGI server in production:
    gunicorn --worker-class eventlet -w 1 "backend.app:create_app()"

IMPORTANT (eventlet): if using eventlet workers, `eventlet.monkey_patch()`
must run before ANY other import that touches sockets/threading (including
Flask, requests, firebase_admin). That's why it's the very first lines of
this file, guarded so it's a no-op when running under a non-eventlet server.
"""

from __future__ import annotations

import logging
import os
import sys

# --- eventlet monkey-patch MUST happen before other imports if eventlet is used ---
if os.environ.get("USE_EVENTLET", "false").lower() == "true":
    import eventlet

    eventlet.monkey_patch()

from flask import Flask
from flask_cors import CORS

# config_loader must be imported early so load_dotenv() runs before any
# module below reads os.environ.
from backend.config.config_loader import get_app_settings, get_attention_config

from backend.api.routes import api_bp
from backend.modules.attendance import AttendanceManager
from backend.services.backup_service import BackupService
from backend.services.esp32_service import ESP32Service
from backend.services.notification_service import NotificationService
from backend.services.report_service import ReportService
from backend.services.user_service import UserService
from backend.utils.log_buffer import get_log_handler

# NOTE: the CV/AI modules (FaceDetector, EyeTracker, HeadPoseEstimator,
# SleepYawnDetector, AttentionEngine, FaceRecognitionService) are
# deliberately NOT imported here at module level. face_recognition (dlib)
# and mediapipe are the most failure-prone dependencies in this project —
# a missing shared library, an ABI mismatch, or the protobuf conflict
# documented in requirements.txt can all make `import face_recognition` or
# `import mediapipe` raise before a single line of application code runs.
# A top-level `from backend.modules.face_detection import FaceDetector`
# here would let that propagate straight through `import backend.app`,
# which no try/except inside create_app() could ever catch. Instead, each
# module is imported lazily inside its own factory function below, so
# _init_module's try/except covers both the import AND the construction.


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    handlers = [logging.StreamHandler(sys.stdout), get_log_handler()]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,  # re-configuring is safe across repeated create_app() calls in tests
    )


def _init_module(module_status: dict, key: str, factory):
    """
    Initialize a single AI/CV module, catching any exception (import error,
    protobuf/mediapipe compatibility error, missing model file, etc.) so
    ONE broken module cannot take down the whole Flask process. Records
    the outcome in `module_status` for the /api/system/status endpoint
    (used by the Models & AI page) so failures are visible rather than
    silently reported as "Online".
    """
    try:
        instance = factory()
        module_status[key] = {"status": "online", "error": None}
        return instance
    except Exception as e:
        logging.getLogger("smart_classroom.app").exception(
            "Module '%s' failed to initialize", key
        )
        module_status[key] = {"status": "failed", "error": str(e)}
        return None


# ---------------------------------------------------------------------------
# Module factories — each reads its own tuning knobs from
# attention_weights.json (via get_attention_config()) where a section
# exists for it, and falls back to that module's own constructor default
# for any key the config doesn't specify. This is the fix for the gap
# where editing attention_weights.json's detection/recognition/
# head_pose_smoothing/monitoring sections previously had no effect at all,
# because nothing here read them.
# ---------------------------------------------------------------------------

def _make_face_detector():
    from backend.modules.face_detection import FaceDetector

    cfg = get_attention_config().detection
    kwargs: dict = {}
    if "min_detection_confidence" in cfg:
        kwargs["min_detection_confidence"] = cfg["min_detection_confidence"]
    if "model_selection" in cfg:
        kwargs["model_selection"] = cfg["model_selection"]
    if "min_face_width_px" in cfg:
        kwargs["min_face_width_px"] = cfg["min_face_width_px"]
    if "min_face_height_px" in cfg:
        kwargs["min_face_height_px"] = cfg["min_face_height_px"]
    return FaceDetector(**kwargs)


def _make_eye_tracker():
    from backend.modules.eye_tracking import EyeTracker

    ear_closed = get_attention_config().thresholds.get("ear_closed_threshold")
    kwargs: dict = {}
    if ear_closed is not None:
        kwargs["ear_closed_threshold"] = ear_closed
    return EyeTracker(**kwargs)


def _make_head_pose_estimator():
    from backend.modules.head_pose import HeadPoseEstimator

    t = get_attention_config().thresholds
    hp = get_attention_config().head_pose_smoothing
    kwargs: dict = {}
    if "head_pose_yaw_max_deg" in t:
        kwargs["yaw_threshold_deg"] = t["head_pose_yaw_max_deg"]
    if "head_pose_pitch_max_deg" in t:
        kwargs["pitch_threshold_deg"] = t["head_pose_pitch_max_deg"]
    for key in (
        "smoothing_alpha",
        "consecutive_frames_required",
        "max_reprojection_error_px",
        "min_pose_confidence",
    ):
        if key in hp:
            kwargs[key] = hp[key]
    return HeadPoseEstimator(**kwargs)


def _make_sleep_yawn_detector():
    from backend.modules.sleep_yawn_detection import SleepYawnDetector

    ear_closed = get_attention_config().thresholds.get("ear_closed_threshold")
    kwargs: dict = {}
    if ear_closed is not None:
        # Shared with EyeTracker above so both modules agree on what
        # "closed" means; previously each independently hardcoded its own
        # default and could silently drift apart if the JSON were tuned.
        kwargs["ear_closed_threshold"] = ear_closed
    return SleepYawnDetector(**kwargs)


def _make_attention_engine():
    from backend.modules.attention_engine import AttentionEngine
    return AttentionEngine()


def _make_recognition_service(firebase_service):
    from backend.modules.face_recognition_module import FaceRecognitionService

    cfg = get_attention_config().recognition
    kwargs: dict = {"storage_backend": firebase_service}
    if "match_tolerance" in cfg:
        kwargs["match_tolerance"] = float(cfg["match_tolerance"])
    return FaceRecognitionService(**kwargs)


def create_app(use_firebase: bool = True) -> Flask:
    settings = get_app_settings()
    _configure_logging(settings.log_level)
    logger = logging.getLogger("smart_classroom.app")

    # Validate attention config eagerly so a bad weights file fails fast at
    # startup rather than on the first processed frame.
    get_attention_config()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.flask_secret_key

    CORS(
        app,
        resources={r"/api/*": {"origins": settings.cors_allowed_origins}},
        supports_credentials=True,
    )

    # --- Firebase (optional at dev time; required for persistence) ---
    firebase_service = None
    if use_firebase:
        try:
            from backend.services.firebase_service import FirebaseService

            firebase_service = FirebaseService()
            logger.info("Firebase service connected")
        except Exception as e:
            logger.warning(
                "Firebase unavailable (%s) — running with in-memory storage only. "
                "Attendance/attention history will NOT persist across restarts.",
                e,
            )

    # --- ESP32 (optional; hardware may not be present in dev) ---
    esp32_service = None
    try:
        esp32_service = ESP32Service(
            mode=os.environ.get("ESP32_MODE", "wifi"),
            esp32_ip=settings.esp32_ip,
            serial_port=settings.esp32_serial_port,
        )
    except Exception as e:
        logger.warning("ESP32 service could not be initialized: %s", e)

    # --- Core AI/CV modules (dependency injection composition root) ---
    # Each is initialized independently, with its import deferred to inside
    # the factory (see module-level note above), so that a single failure —
    # a missing shared library, a MediaPipe/protobuf version mismatch, a
    # broken dlib build — degrades only that one capability instead of
    # crashing the entire backend at import time. See /api/system/status.
    module_status: dict = {}

    face_detector = _init_module(module_status, "face_detection", _make_face_detector)
    eye_tracker = _init_module(module_status, "eye_tracking", _make_eye_tracker)
    head_pose_estimator = _init_module(module_status, "head_pose", _make_head_pose_estimator)
    sleep_yawn_detector = _init_module(module_status, "sleep_yawn_detection", _make_sleep_yawn_detector)
    attention_engine = _init_module(module_status, "attention_engine", _make_attention_engine)
    recognition_service = _init_module(
        module_status,
        "face_recognition",
        lambda: _make_recognition_service(firebase_service),
    )

    if firebase_service is not None and recognition_service is not None:
        try:
            recognition_service.load_index_from_storage()
        except Exception:
            logger.exception("Could not preload face encodings from Firebase")

    attendance_manager = AttendanceManager(storage_backend=firebase_service)
    if firebase_service is not None:
        try:
            restored = attendance_manager.load_today_from_storage()
            if restored:
                logger.info("Rehydrated %d attendance record(s) from Firestore on startup", restored)
        except Exception:
            logger.exception("Could not rehydrate today's attendance from Firestore")
    notification_service = NotificationService(
        storage_backend=firebase_service, esp32_service=esp32_service
    )
    user_service = UserService()

    # The full frame-processing pipeline needs every CV module to be
    # healthy. If any failed to initialize, we deliberately do NOT build a
    # partially-working pipeline (that would silently degrade attention
    # scoring in confusing ways) — /api/process-frame instead returns a
    # clear 503 naming exactly which module is unavailable.
    #
    # ClassroomPipeline's own import is deferred and guarded too: it
    # transitively imports firebase_service.py (which imports firebase_admin
    # unconditionally at module level), so even with every CV module
    # healthy, a missing firebase_admin package could otherwise crash this
    # step. A failed import here degrades to "no live pipeline" rather than
    # taking down the whole app, consistent with every other module above.
    required = [face_detector, eye_tracker, head_pose_estimator, sleep_yawn_detector, attention_engine, recognition_service]
    pipeline = None
    if all(m is not None for m in required):
        try:
            from backend.modules.classroom_pipeline import ClassroomPipeline

            monitoring = get_attention_config().monitoring
            pipeline = ClassroomPipeline(
                face_detector=face_detector,
                eye_tracker=eye_tracker,
                head_pose_estimator=head_pose_estimator,
                sleep_yawn_detector=sleep_yawn_detector,
                attention_engine=attention_engine,
                recognition_service=recognition_service,
                attendance_manager=attendance_manager,
                notification_service=notification_service,
                firebase_service=firebase_service,
                low_attention_threshold=monitoring.get("low_attention_threshold", 40.0),
                stale_student_seconds=monitoring.get("stale_student_seconds", 8.0),
            )
            module_status["classroom_pipeline"] = {"status": "online", "error": None}
        except Exception as e:
            logger.exception("Classroom pipeline failed to initialize")
            module_status["classroom_pipeline"] = {"status": "failed", "error": str(e)}
    else:
        failed = [k for k, v in module_status.items() if v["status"] == "failed"]
        logger.warning(
            "Classroom pipeline NOT started — failed module(s): %s. "
            "Live camera processing is unavailable; the rest of the "
            "dashboard (attendance, alerts, students, reports) still works.",
            ", ".join(failed),
        )

    backup_service = BackupService(
        attendance_manager=attendance_manager,
        recognition_service=recognition_service or _NullRecognitionService(),
        notification_service=notification_service,
        firebase_service=firebase_service,
    )
    report_service = ReportService(
        attendance_manager=attendance_manager,
        firebase_service=firebase_service,
        pipeline=pipeline,
    )

    # Make everything available to the API blueprint via app.config,
    # avoiding global module-level singletons for testability.
    app.config["FIREBASE_SERVICE"] = firebase_service
    app.config["ESP32_SERVICE"] = esp32_service
    app.config["FACE_RECOGNITION_SERVICE"] = recognition_service
    app.config["ATTENDANCE_MANAGER"] = attendance_manager
    app.config["NOTIFICATION_SERVICE"] = notification_service
    app.config["CLASSROOM_PIPELINE"] = pipeline
    app.config["USER_SERVICE"] = user_service
    app.config["BACKUP_SERVICE"] = backup_service
    app.config["REPORT_SERVICE"] = report_service
    app.config["MODULE_STATUS"] = module_status
    app.config["LOG_HANDLER"] = get_log_handler()

    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def not_found(_e):
        return {"success": False, "error": "Endpoint not found"}, 404

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Unhandled server error")
        return {"success": False, "error": "Internal server error"}, 500

    healthy = [k for k, v in module_status.items() if v["status"] == "online"]
    failed = [k for k, v in module_status.items() if v["status"] == "failed"]
    logger.info(
        "Smart Classroom backend initialized (env=%s) — modules online: %s%s",
        settings.flask_env, healthy or "none",
        f", FAILED: {failed}" if failed else "",
    )
    return app


class _NullRecognitionService:
    """Fallback used only when FaceRecognitionService itself failed to
    initialize, so BackupService.list_enrolled() has something safe to
    call rather than requiring another None-check at every call site."""

    def list_enrolled(self):
        return []


if __name__ == "__main__":
    settings = get_app_settings()
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=settings.flask_port,
        debug=(settings.flask_env == "development"),
    )