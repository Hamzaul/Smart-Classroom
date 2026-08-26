"""
backend/tests/test_attention_engine.py

Unit tests for the weighted Attention Scoring Engine.
Run with: pytest backend/tests/test_attention_engine.py -v
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from backend.modules.attention_engine import AttentionEngine, FrameSignals


@pytest.fixture
def engine():
    return AttentionEngine()


def test_fully_attentive_student_scores_high(engine):
    signals = FrameSignals(
        student_id="s1",
        face_present=True,
        eye_aspect_ratio=0.32,
        blink_rate_per_min=15,
        head_yaw_deg=0,
        head_pitch_deg=0,
        is_sleeping=False,
        sleep_duration_seconds=0,
        yawn_count_last_minute=0,
        emotion_label="focused",
    )
    result = engine.compute_score(signals)
    assert result.score >= 80
    assert result.level in ("excellent", "high")


def test_sleeping_student_scores_low(engine):
    signals = FrameSignals(
        student_id="s2",
        face_present=True,
        eye_aspect_ratio=0.10,
        blink_rate_per_min=1,
        head_yaw_deg=5,
        head_pitch_deg=35,
        is_sleeping=True,
        sleep_duration_seconds=10,
        yawn_count_last_minute=5,
        emotion_label="sleepy",
    )
    result = engine.compute_score(signals)
    assert result.score < 40
    assert result.level in ("low", "very_low")


def test_absent_student_score_decays_over_time(engine):
    s1 = FrameSignals(student_id="s3", face_present=False, timestamp=100.0)
    r1 = engine.compute_score(s1)

    s2 = FrameSignals(student_id="s3", face_present=False, timestamp=105.0)
    r2 = engine.compute_score(s2)

    assert r2.score <= r1.score


def test_score_is_always_within_bounds(engine):
    extreme = FrameSignals(
        student_id="s4",
        face_present=True,
        eye_aspect_ratio=0.0,
        blink_rate_per_min=100,
        head_yaw_deg=180,
        head_pitch_deg=180,
        is_sleeping=True,
        sleep_duration_seconds=999,
        yawn_count_last_minute=999,
        emotion_label="unknown",
    )
    result = engine.compute_score(extreme)
    assert 0.0 <= result.score <= 100.0


def test_smoothing_reduces_frame_to_frame_jitter(engine):
    """A single noisy frame shouldn't swing the smoothed score all the way
    to the raw value if prior frames were consistently high."""
    high_signals = FrameSignals(
        student_id="s5",
        face_present=True,
        eye_aspect_ratio=0.32,
        blink_rate_per_min=15,
        head_yaw_deg=0,
        head_pitch_deg=0,
        is_sleeping=False,
        sleep_duration_seconds=0,
        yawn_count_last_minute=0,
        emotion_label="focused",
    )
    for _ in range(10):
        engine.compute_score(high_signals)

    noisy_signals = FrameSignals(
        student_id="s5",
        face_present=True,
        eye_aspect_ratio=0.10,
        blink_rate_per_min=1,
        head_yaw_deg=40,
        head_pitch_deg=40,
        is_sleeping=False,
        sleep_duration_seconds=0,
        yawn_count_last_minute=0,
        emotion_label="focused",
    )
    result = engine.compute_score(noisy_signals)
    # Smoothed score should not have collapsed all the way to a "very low"
    # value from a single bad frame after 10 consistently good frames.
    assert result.score > 30


def test_attention_level_boundaries_match_config(engine):
    assert engine._config.attention_level_for_score(90) == "excellent"
    assert engine._config.attention_level_for_score(70) == "high"
    assert engine._config.attention_level_for_score(50) == "medium"
    assert engine._config.attention_level_for_score(30) == "low"
    assert engine._config.attention_level_for_score(5) == "very_low"


def test_reset_student_clears_history(engine):
    signals = FrameSignals(student_id="s6", face_present=True, eye_aspect_ratio=0.3)
    engine.compute_score(signals)
    assert engine.get_rolling_average("s6") > 0
    engine.reset_student("s6")
    assert engine.get_rolling_average("s6") == 0.0
