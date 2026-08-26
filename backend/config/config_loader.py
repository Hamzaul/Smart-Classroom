 
from __future__ import annotations
 
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
 
from dotenv import load_dotenv
 
# ---------------------------------------------------------------------------
# Load environment variables FIRST, before anything else in the package
# touches os.environ. This file must be imported before any module that
# needs FIREBASE_*, FLASK_*, or other env-derived settings.
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
_ENV_PATH = _BASE_DIR / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)
 
logger = logging.getLogger("smart_classroom.config")
 
_ATTENTION_CONFIG_PATH = Path(__file__).resolve().parent / "attention_weights.json"
 
 
class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
 
 
@dataclass(frozen=True)
class AttentionLevelRange:
    min: int
    max: int
 
 
class AttentionConfig:
    """
    Typed, validated wrapper around attention_weights.json.
 
    Loaded once per process (module-level singleton via `get_attention_config`)
    and cached. Call `AttentionConfig.reload()` explicitly if the JSON file
    changes at runtime (e.g. via an admin settings endpoint).
    """
 
    def __init__(self, raw: Dict[str, Any]):
        self._raw = raw
        self._validate()
 
    def _validate(self) -> None:
        required_top_level = {
            "weights",
            "thresholds",
            "emotion_scores",
            "attention_levels",
            "history",
        }
        missing = required_top_level - self._raw.keys()
        if missing:
            raise ConfigError(f"attention_weights.json missing keys: {missing}")
 
        weight_sum = sum(self._raw["weights"].values())
        if not (0.98 <= weight_sum <= 1.02):
            raise ConfigError(
                f"Attention weights must sum to ~1.0, got {weight_sum:.4f}"
            )
 
        # Optional sections (detection / recognition / head_pose_smoothing /
        # monitoring) are NOT required — every consumer of these has a safe
        # hardcoded default in its own constructor. But if a section IS
        # present, it must be an object, not a scalar/string/etc., so a
        # malformed edit fails loudly here at startup instead of surfacing
        # as a confusing TypeError deep inside FaceDetector/HeadPoseEstimator
        # construction later. Value-range validation (e.g. match_tolerance
        # in [0,1]) is intentionally deferred to a later pass.
        detection = self._raw.get("detection", {})
        recognition = self._raw.get("recognition", {})
        pose = self._raw.get("head_pose_smoothing", {})
        monitoring = self._raw.get("monitoring", {})
 
        if not isinstance(detection, dict):
            raise ConfigError("'detection' must be an object")
        if not isinstance(recognition, dict):
            raise ConfigError("'recognition' must be an object")
        if not isinstance(pose, dict):
            raise ConfigError("'head_pose_smoothing' must be an object")
        if not isinstance(monitoring, dict):
            raise ConfigError("'monitoring' must be an object")
 
    @property
    def weights(self) -> Dict[str, float]:
        return dict(self._raw["weights"])
 
    @property
    def thresholds(self) -> Dict[str, float]:
        return dict(self._raw["thresholds"])
 
    @property
    def emotion_scores(self) -> Dict[str, float]:
        return dict(self._raw["emotion_scores"])
 
    @property
    def history(self) -> Dict[str, float]:
        return dict(self._raw["history"])
 
    @property
    def detection(self) -> Dict[str, Any]:
        """Optional. FaceDetector tuning: min_detection_confidence,
        model_selection, min_face_width_px, min_face_height_px. Missing
        keys fall back to FaceDetector's own constructor defaults."""
        return dict(self._raw.get("detection", {}))
 
    @property
    def recognition(self) -> Dict[str, Any]:
        """Optional. FaceRecognitionService tuning: match_tolerance.
        Missing keys fall back to the service's own constructor default."""
        return dict(self._raw.get("recognition", {}))
 
    @property
    def head_pose_smoothing(self) -> Dict[str, Any]:
        """Optional. HeadPoseEstimator tuning: smoothing_alpha,
        consecutive_frames_required, max_reprojection_error_px,
        min_pose_confidence. Missing keys fall back to the estimator's
        own constructor defaults."""
        return dict(self._raw.get("head_pose_smoothing", {}))
 
    @property
    def monitoring(self) -> Dict[str, Any]:
        """Optional. Cross-cutting runtime knobs: frame_interval_ms
        (frontend), stale_student_seconds and low_attention_threshold
        (ClassroomPipeline), alert_cooldown_seconds (NotificationService).
        Missing keys fall back to each consumer's own default."""
        return dict(self._raw.get("monitoring", {}))
 
    def attention_level_for_score(self, score: float) -> str:
        """Map a 0-100 attention score to a level label using config ranges."""
        levels = self._raw["attention_levels"]
        clamped = max(0.0, min(100.0, score))
        for level_name, bounds in levels.items():
            if bounds["min"] <= clamped <= bounds["max"]:
                return level_name
        # Fallback: should be unreachable if ranges cover 0-100 contiguously.
        logger.warning("Score %.2f did not match any configured level range", score)
        return "unknown"
 
    def emotion_score(self, emotion_label: str) -> float:
        return self._raw["emotion_scores"].get(
            emotion_label.lower(), self._raw["emotion_scores"].get("unknown", 50)
        )
 
 
_attention_config_singleton: AttentionConfig | None = None
 
 
def get_attention_config() -> AttentionConfig:
    global _attention_config_singleton
    if _attention_config_singleton is None:
        if not _ATTENTION_CONFIG_PATH.exists():
            raise ConfigError(
                f"Attention config not found at {_ATTENTION_CONFIG_PATH}"
            )
        with open(_ATTENTION_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _attention_config_singleton = AttentionConfig(raw)
        logger.info("Loaded attention configuration from %s", _ATTENTION_CONFIG_PATH)
    return _attention_config_singleton
 
 
def reload_attention_config() -> AttentionConfig:
    """Force a reload from disk. Use after editing attention_weights.json at runtime."""
    global _attention_config_singleton
    _attention_config_singleton = None
    return get_attention_config()
 
 
def save_attention_weights(new_weights: Dict[str, float]) -> AttentionConfig:
    """
    Update just the `weights` section of attention_weights.json on disk and
    reload the in-memory singleton, so a change made via the Settings page
    takes effect immediately without a backend restart.
 
    Validates that every key already present in the config is provided and
    that the values sum to ~1.0 — the same invariant AttentionConfig itself
    enforces on load — so a bad write can't leave the file in a state that
    fails to load on the next restart.
    """
    if not _ATTENTION_CONFIG_PATH.exists():
        raise ConfigError(f"Attention config not found at {_ATTENTION_CONFIG_PATH}")
 
    with open(_ATTENTION_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
 
    existing_keys = set(raw["weights"].keys())
    new_keys = set(new_weights.keys())
    if existing_keys != new_keys:
        raise ConfigError(
            f"Weight keys must exactly match the existing set: {sorted(existing_keys)}"
        )
    for k, v in new_weights.items():
        if not isinstance(v, (int, float)) or v < 0:
            raise ConfigError(f"Weight '{k}' must be a non-negative number")
 
    total = sum(new_weights.values())
    if not (0.98 <= total <= 1.02):
        raise ConfigError(f"Weights must sum to ~1.0, got {total:.4f}")
 
    raw["weights"] = {k: float(v) for k, v in new_weights.items()}
    with open(_ATTENTION_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
 
    logger.info("Attention weights updated via Settings: %s", raw["weights"])
    return reload_attention_config()
 
 
# ---------------------------------------------------------------------------
# Environment-derived app settings (single source of truth for os.environ)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AppSettings:
    flask_env: str
    flask_secret_key: str
    flask_port: int
    firebase_credentials_path: str
    firebase_storage_bucket: str
    esp32_ip: str
    esp32_serial_port: str
    cors_allowed_origins: list[str]
    log_level: str
 
 
def get_app_settings() -> AppSettings:
    def _require(key: str, default: str | None = None) -> str:
        val = os.environ.get(key, default)
        if val is None:
            raise ConfigError(f"Required environment variable '{key}' is not set")
        return val
 
    cors_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    return AppSettings(
        flask_env=os.environ.get("FLASK_ENV", "development"),
        flask_secret_key=_require("FLASK_SECRET_KEY", "dev-insecure-change-me"),
        flask_port=int(os.environ.get("FLASK_PORT", "5000")),
        firebase_credentials_path=_require(
            "FIREBASE_CREDENTIALS_PATH", "config/firebase_credentials.json"
        ),
        firebase_storage_bucket=os.environ.get("FIREBASE_STORAGE_BUCKET", ""),
        esp32_ip=os.environ.get("ESP32_IP", "192.168.1.50"),
        esp32_serial_port=os.environ.get("ESP32_SERIAL_PORT", "/dev/ttyUSB0"),
        cors_allowed_origins=[o.strip() for o in cors_raw.split(",") if o.strip()],
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
 