from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import face_recognition
import numpy as np

logger = logging.getLogger("smart_classroom.face_recognition")


class FaceRecognitionError(Exception):
    """Raised when enrollment or recognition cannot proceed."""


@dataclass
class StudentEncoding:
    student_id: str
    name: str
    roll_number: str
    encoding: np.ndarray  # shape (128,)


@dataclass
class RecognitionMatch:
    student_id: Optional[str]
    name: Optional[str]
    roll_number: Optional[str]
    # 0-1, higher = closer match. This is a *relative match strength*
    # derived from face-distance, NOT a calibrated probability — do not
    # present it to a teacher as "68% sure this is X". See match_score().
    match_score: float
    recognition_distance: Optional[float]  # raw face_distance; None if no encoding was found at all
    recognition_threshold: float           # the tolerance this match was judged against
    face_detection_confidence: float       # confidence from FaceDetector for this box
    bbox: Tuple[int, int, int, int]  # (top, right, bottom, left) - face_recognition convention
    is_known: bool


class FaceRecognitionService:
    """
    In-memory face recognition index, backed by an injectable persistence
    layer for loading/saving encodings (dependency injection: pass any
    object exposing `save_student_encoding` / `load_all_student_encodings`,
    e.g. FirebaseService).
    """

    def __init__(self, match_tolerance: float = 0.5, storage_backend=None):
        """
        Args:
            match_tolerance: max face-distance to count as a match (lower =
                stricter). face_recognition's own default is 0.6; 0.5 trades
                a few more false-negatives for fewer false-positives, which
                matters more for attendance integrity. Keep at 0.5 until
                real testing says otherwise — do not raise it just to make
                recognition "feel" better; attendance accuracy matters more
                than recall.
            storage_backend: optional object with `save_student_encoding(...)`
                and `load_all_student_encodings() -> List[StudentEncoding]`.
                If None, encodings only live in memory for this process.
        """
        self._tolerance = match_tolerance
        self._storage = storage_backend
        self._index: Dict[str, StudentEncoding] = {}

    # ------------------------------------------------------------------
    # Enrollment
    # ------------------------------------------------------------------
    def enroll_student(
        self,
        name: str,
        roll_number: str,
        reference_images_rgb: List[np.ndarray],
        student_id: Optional[str] = None,
    ) -> StudentEncoding:
        """
        Enroll a student from one or more reference photos (RGB numpy arrays).
        Averages encodings across all provided photos for robustness.
        3-5 reference images is the recommended minimum for pose variation.

        Raises FaceRecognitionError if:
          - no face (or multiple faces) is found in a reference image
          - the roll number is already enrolled under a different student_id
        since either silently corrupts attendance accuracy later.
        """
        if not reference_images_rgb:
            raise FaceRecognitionError("At least one reference image is required")

        sid = student_id or str(uuid.uuid4())

        # Guard against enrolling the same roll number twice under two
        # different student IDs (e.g. accidental double-enrollment).
        for existing in self._index.values():
            if existing.roll_number == roll_number and existing.student_id != sid:
                raise FaceRecognitionError(
                    f"Roll number '{roll_number}' is already enrolled as "
                    f"'{existing.name}' ({existing.student_id})"
                )

        encodings: List[np.ndarray] = []
        for idx, image in enumerate(reference_images_rgb):
            face_locations = face_recognition.face_locations(image)
            if len(face_locations) == 0:
                raise FaceRecognitionError(
                    f"No face found in reference image #{idx + 1} for '{name}'"
                )
            if len(face_locations) > 1:
                raise FaceRecognitionError(
                    f"Multiple faces found in reference image #{idx + 1} for "
                    f"'{name}' — please provide a photo with only this student"
                )
            image_encodings = face_recognition.face_encodings(image, face_locations)
            encodings.append(image_encodings[0])

        averaged_encoding = np.mean(np.stack(encodings, axis=0), axis=0)

        record = StudentEncoding(
            student_id=sid,
            name=name,
            roll_number=roll_number,
            encoding=averaged_encoding,
        )
        self._index[sid] = record

        if self._storage is not None:
            try:
                self._storage.save_student_encoding(record)
                logger.info("Persisted encoding for student %s (%s)", name, sid)
            except Exception:
                # Enrollment already succeeded in-memory (recognition works
                # immediately this session); a Firestore write failure
                # shouldn't roll that back or crash the request — it should
                # just mean the enrollment won't survive a backend restart.
                logger.exception(
                    "Failed to persist encoding for student %s (%s) — "
                    "enrollment is active for this session but not durable",
                    name, sid,
                )

        logger.info(
            "Enrolled student '%s' (roll=%s, id=%s) from %d reference image(s)",
            name,
            roll_number,
            sid,
            len(reference_images_rgb),
        )
        return record

    def load_index_from_storage(self) -> int:
        """Populate the in-memory index from the storage backend. Returns count loaded."""
        if self._storage is None:
            raise FaceRecognitionError("No storage backend configured")
        records = self._storage.load_all_student_encodings()
        self._index = {r.student_id: r for r in records}
        logger.info("Loaded %d student encodings from storage", len(self._index))
        return len(self._index)

    def remove_student(self, student_id: str) -> None:
        self._index.pop(student_id, None)
        if self._storage is not None and hasattr(self._storage, "delete_student_encoding"):
            self._storage.delete_student_encoding(student_id)

    @property
    def enrolled_count(self) -> int:
        return len(self._index)

    def list_enrolled(self) -> List[Dict[str, str]]:
        """
        Return enrolled students from the in-memory index — always available
        regardless of whether Firebase is configured, since enrollment
        updates this index synchronously (see enroll_student above).
        """
        return [
            {"student_id": r.student_id, "name": r.name, "roll_number": r.roll_number}
            for r in self._index.values()
        ]

    # ------------------------------------------------------------------
    # Recognition — pipeline entry point
    # ------------------------------------------------------------------
    def identify_face(
        self,
        face_crop_rgb: np.ndarray,
        bbox: Tuple[int, int, int, int],
        detection_confidence: float = 0.0,
    ) -> RecognitionMatch:
        """
        Identify a single face that FaceDetector has already located and
        cropped. This is the method the classroom pipeline should call —
        it does NOT run its own detection pass.

        Args:
            face_crop_rgb: an RGB crop containing exactly one face, as
                produced by DetectedFace.crop_for_recognition().
            bbox: the face's (x, y, width, height) box in the *original
                frame* (i.e. DetectedFace.bbox), carried through purely so
                the caller doesn't have to re-attach it — this method does
                not use it for anything but passthrough.
            detection_confidence: DetectedFace.confidence for this box,
                carried through into the result for diagnostics.

        Returns:
            A RecognitionMatch. If no encodable face is found in the crop
            (rare — the crop came from a real detection, but a low-quality
            crop can still fail dlib's landmark stage), or if no enrolled
            student is within tolerance, is_known=False is returned rather
            than the face silently disappearing from the result set.
        """
        x, y, w, h = bbox
        crop_h, crop_w = face_crop_rgb.shape[:2]
        # The crop is (approximately) just this one face, so hand
        # face_recognition an explicit full-crop location instead of
        # letting it re-run detection internally.
        full_crop_location = [(0, crop_w, crop_h, 0)]  # (top, right, bottom, left)

        try:
            encodings = face_recognition.face_encodings(face_crop_rgb, full_crop_location)
        except Exception:
            logger.exception("face_encodings raised on a detector-provided crop")
            encodings = []

        if not encodings:
            return RecognitionMatch(
                student_id=None,
                name=None,
                roll_number=None,
                match_score=0.0,
                recognition_distance=None,
                recognition_threshold=self._tolerance,
                face_detection_confidence=detection_confidence,
                bbox=(y, x + w, y + h, x),
                is_known=False,
            )

        encoding = encodings[0]
        known_ids = list(self._index.keys())
        known_encodings = [self._index[sid].encoding for sid in known_ids]

        if not known_encodings:
            return RecognitionMatch(
                student_id=None,
                name=None,
                roll_number=None,
                match_score=0.0,
                recognition_distance=None,
                recognition_threshold=self._tolerance,
                face_detection_confidence=detection_confidence,
                bbox=(y, x + w, y + h, x),
                is_known=False,
            )

        distances = face_recognition.face_distance(known_encodings, encoding)
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])
        score = self._match_score(best_distance)

        if best_distance <= self._tolerance:
            sid = known_ids[best_idx]
            record = self._index[sid]
            return RecognitionMatch(
                student_id=sid,
                name=record.name,
                roll_number=record.roll_number,
                match_score=score,
                recognition_distance=round(best_distance, 4),
                recognition_threshold=self._tolerance,
                face_detection_confidence=detection_confidence,
                bbox=(y, x + w, y + h, x),
                is_known=True,
            )

        return RecognitionMatch(
            student_id=None,
            name=None,
            roll_number=None,
            match_score=score,
            recognition_distance=round(best_distance, 4),
            recognition_threshold=self._tolerance,
            face_detection_confidence=detection_confidence,
            bbox=(y, x + w, y + h, x),
            is_known=False,
        )

    @staticmethod
    def _match_score(distance: float) -> float:
        """
        Map a face-distance to a 0-1 relative match strength. This is NOT a
        calibrated probability (face_recognition gives no such guarantee) —
        it should be surfaced to users as "match score", never as a percent
        confidence that a given identity is correct.
        """
        return round(max(0.0, 1.0 - distance), 4)

    # ------------------------------------------------------------------
    # Legacy / manual-testing helper — NOT used by the classroom pipeline
    # ------------------------------------------------------------------
    def identify_faces(self, frame_rgb: np.ndarray) -> List[RecognitionMatch]:
        """
        Standalone detect+identify over a whole frame, using face_recognition's
        own detector. Kept only for ad-hoc scripts/tests; the live pipeline
        must use identify_face() against FaceDetector's output instead, so
        there is exactly one detector deciding "how many faces are in this
        frame".
        """
        logger.warning(
            "identify_faces() runs its own detection pass — do not call this "
            "from the classroom pipeline; use identify_face() per DetectedFace."
        )
        face_locations = face_recognition.face_locations(frame_rgb)
        if not face_locations:
            return []

        face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)
        matches: List[RecognitionMatch] = []
        for bbox, encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = bbox
            crop_rgb = frame_rgb[top:bottom, left:right]
            x, y, w, h = left, top, right - left, bottom - top
            matches.append(self.identify_face(crop_rgb, (x, y, w, h), detection_confidence=0.0))
        return matches
