from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import mediapipe as mp
import numpy as np

logger = logging.getLogger("smart_classroom.face_detection")

# Faces smaller than this (in pixels, in the *source frame*) produce
# unreliable FaceMesh landmarks and unreliable encodings, and should never
# reach recognition / eye-tracking / attention. Configurable rather than
# hardcoded inline so it can be tuned during classroom testing without a
# code change; see FaceDetector.__init__.
_DEFAULT_MIN_FACE_WIDTH_PX = 40
_DEFAULT_MIN_FACE_HEIGHT_PX = 40


@dataclass
class DetectedFace:
    """A single detected face in pixel coordinates relative to the input frame."""

    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def crop(self, frame: np.ndarray, padding: float = 0.15) -> np.ndarray:
        """Return a padded crop of this face from the given frame.

        Generic crop kept for callers that don't care about the distinction
        below. New code should prefer crop_for_recognition() /
        crop_for_landmarks() so the padding choice is explicit and can be
        tuned independently per consumer.
        """
        h_frame, w_frame = frame.shape[:2]
        pad_x = int(self.width * padding)
        pad_y = int(self.height * padding)
        x1 = max(0, self.x - pad_x)
        y1 = max(0, self.y - pad_y)
        x2 = min(w_frame, self.x + self.width + pad_x)
        y2 = min(h_frame, self.y + self.height + pad_y)
        return frame[y1:y2, x1:x2]

    def crop_for_recognition(self, frame: np.ndarray) -> np.ndarray:
        """Tight crop for face_recognition encoding — a little padding helps
        the encoder see the full jaw/hairline without pulling in enough
        background to shift the encoding."""
        return self.crop(frame, padding=0.10)

    def crop_for_landmarks(self, frame: np.ndarray) -> np.ndarray:
        """Slightly looser crop for FaceMesh, which benefits from a bit more
        context around the eyes/mouth than the recognition encoder does."""
        return self.crop(frame, padding=0.25)


class FaceDetector:
    """
    Wraps mediapipe.solutions.face_detection.FaceDetection.

    Usage:
        detector = FaceDetector()
        faces = detector.detect(frame_bgr)
        detector.close()

    Or as a context manager:
        with FaceDetector() as detector:
            faces = detector.detect(frame_bgr)
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.6,
        model_selection: int = 1,
        min_face_width_px: int = _DEFAULT_MIN_FACE_WIDTH_PX,
        min_face_height_px: int = _DEFAULT_MIN_FACE_HEIGHT_PX,
    ):
        """
        Args:
            min_detection_confidence: Minimum confidence (0-1) for a detection
                to be returned. Lower catches more faces but more false
                positives. Keep at 0.6 unless real classroom testing (0.5 /
                0.6 / 0.7 comparison) says otherwise — do not lower this
                reactively because a single frame failed to detect a face.
            model_selection: 0 = short-range model (best for faces within
                ~2m, e.g. a laptop webcam), 1 = full-range model (better for
                a classroom-wide camera where students may be several
                meters away). Choosing between these needs real testing on
                the actual deployment camera, not a guess.
            min_face_width_px / min_face_height_px: faces smaller than this
                (in the source frame, pre-crop) are dropped before they ever
                reach recognition or landmark extraction, since tiny boxes
                produce unreliable encodings and meshes. Configurable, not
                hardcoded downstream.
        """
        self._mp_face_detection = mp.solutions.face_detection
        self._detector = self._mp_face_detection.FaceDetection(
            min_detection_confidence=min_detection_confidence,
            model_selection=model_selection,
        )
        self._min_face_width_px = min_face_width_px
        self._min_face_height_px = min_face_height_px
        logger.info(
            "FaceDetector initialized (model_selection=%d, min_conf=%.2f, "
            "min_face_px=%dx%d)",
            model_selection,
            min_detection_confidence,
            min_face_width_px,
            min_face_height_px,
        )

    def detect(self, frame_bgr: np.ndarray) -> List[DetectedFace]:
        """
        Detect all faces in a BGR frame.

        Args:
            frame_bgr: OpenCV-style BGR image (H, W, 3).

        Returns:
            List of DetectedFace, in pixel coordinates, sorted left-to-right
            (stable ordering helps when correlating with a seating chart).
            Faces below the configured minimum size are silently dropped —
            they never reach the rest of the pipeline.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            logger.warning("Received empty frame in FaceDetector.detect")
            return []

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._detector.process(rgb)

        faces: List[DetectedFace] = []
        if results.detections:
            for detection in results.detections:
                box = detection.location_data.relative_bounding_box
                x = int(box.xmin * w)
                y = int(box.ymin * h)
                bw = int(box.width * w)
                bh = int(box.height * h)

                # Explicit invariant: every box we return satisfies
                #   0 <= x, 0 <= y
                #   x + width  <= frame_width
                #   y + height <= frame_height
                # MediaPipe can return slightly out-of-frame boxes near
                # edges, so clamp both origin and extent independently
                # rather than assuming one clamp fixes the other.
                x = max(0, min(x, w))
                y = max(0, min(y, h))
                bw = max(0, min(bw, w - x))
                bh = max(0, min(bh, h - y))

                if bw <= 0 or bh <= 0:
                    continue
                if bw < self._min_face_width_px or bh < self._min_face_height_px:
                    logger.debug(
                        "Dropping sub-minimum face %dx%d (min %dx%d)",
                        bw, bh, self._min_face_width_px, self._min_face_height_px,
                    )
                    continue

                confidence = detection.score[0] if detection.score else 0.0
                faces.append(
                    DetectedFace(x=x, y=y, width=bw, height=bh, confidence=confidence)
                )

        faces.sort(key=lambda f: f.x)
        return faces

    def close(self) -> None:
        self._detector.close()

    def __enter__(self) -> "FaceDetector":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
