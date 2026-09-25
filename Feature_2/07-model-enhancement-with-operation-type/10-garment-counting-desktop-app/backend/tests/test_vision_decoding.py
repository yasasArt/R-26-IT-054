from __future__ import annotations

from collections import deque

from app.vision.decoding import (
    GarmentCycleDecoder,
    ProbabilitySmoother,
    WorkstationGate,
    WorkstationLatch,
)
from app.vision.runtime import sample_clip


def test_workstation_gate_requires_consecutive_real_detections() -> None:
    gate = WorkstationGate(opening_frames=2, closing_frames=3)
    assert gate.update(True) is False
    assert gate.update(True) is True
    assert gate.update(False) is True
    assert gate.update(False) is True
    assert gate.update(False) is False


def test_workstation_gate_reset_rejects_stale_visibility() -> None:
    gate = WorkstationGate(opening_frames=2)
    gate.update(True)
    gate.update(True)
    gate.reset()
    assert gate.confirmed is False
    assert gate.update(True) is False


def test_workstation_latches_once_then_checks_only_at_intervals() -> None:
    workstation = WorkstationLatch(
        initial_detections=2,
        recheck_interval_seconds=3.0,
        failed_recheck_limit=3,
    )
    assert workstation.should_check(0.0) is True
    assert workstation.update(True, 0.0) is False
    assert workstation.update(True, 0.3) is True
    assert workstation.should_check(1.0) is False
    assert workstation.should_check(3.2) is False
    assert workstation.should_check(3.3) is True


def test_latched_workstation_survives_missed_periodic_checks() -> None:
    workstation = WorkstationLatch(
        initial_detections=1,
        recheck_interval_seconds=3.0,
        failed_recheck_limit=3,
    )
    assert workstation.update(True, 0.0) is True
    assert workstation.update(False, 3.0) is True
    assert workstation.failed_rechecks == 1
    assert workstation.update(False, 6.0) is True
    assert workstation.failed_rechecks == 2
    assert workstation.update(True, 9.0) is True
    assert workstation.failed_rechecks == 0
    assert workstation.update(False, 12.0) is True
    assert workstation.update(False, 15.0) is True
    assert workstation.update(False, 18.0) is False


def test_classifier_smoothing_marks_low_confidence_uncertain() -> None:
    smoother = ProbabilitySmoother(window_size=3, minimum_confidence=0.62)
    label, confidence = smoother.update({"IDLE_SETUP": 0.54, "SEWING": 0.46})
    assert label == "UNCERTAIN"
    assert confidence == 0.54


def test_smoothing_reset_discards_predictions_from_an_invalid_workstation() -> None:
    smoother = ProbabilitySmoother(window_size=3)
    smoother.update({"IDLE_SETUP": 0.01, "SEWING": 0.99})
    smoother.reset()
    label, _ = smoother.update({"IDLE_SETUP": 0.99, "SEWING": 0.01})
    assert label == "IDLE_SETUP"


def test_confirmed_sewing_to_idle_emits_one_first_garment_with_cycle_start() -> None:
    decoder = GarmentCycleDecoder(minimum_sewing_seconds=2.0, minimum_idle_seconds=0.6)
    assert decoder.update("SEWING", 10.0, 0.96) is None
    assert decoder.update("SEWING", 12.1, 0.96) is None
    assert decoder.phase == "SEWING_CONFIRMED"
    assert decoder.update("IDLE_SETUP", 15.0, 0.97) is None
    event = decoder.update("IDLE_SETUP", 15.7, 0.97)
    assert event is not None
    assert event.sewing_started_at == 10.0
    assert event.completed_at == 15.0
    assert event.completed_at - event.sewing_started_at == 5.0
    assert decoder.update("IDLE_SETUP", 16.8, 0.97) is None


def test_short_sewing_or_idle_predictions_never_create_a_count() -> None:
    decoder = GarmentCycleDecoder(minimum_sewing_seconds=2.0, minimum_idle_seconds=0.6)
    for label, timestamp in (
        ("SEWING", 0.0),
        ("SEWING", 1.3),
        ("IDLE_SETUP", 1.4),
        ("IDLE_SETUP", 3.0),
    ):
        assert decoder.update(label, timestamp, 0.94) is None


def test_mode_or_visibility_interruption_cancels_an_unfinished_cycle() -> None:
    decoder = GarmentCycleDecoder(minimum_sewing_seconds=1.0, minimum_idle_seconds=0.5)
    decoder.update("SEWING", 10.0, 0.95)
    decoder.update("SEWING", 11.1, 0.95)
    assert decoder.phase == "SEWING_CONFIRMED"
    decoder.reset_cycle()
    assert decoder.update("IDLE_SETUP", 12.0, 0.95) is None
    assert decoder.update("IDLE_SETUP", 13.0, 0.95) is None


def test_cooldown_blocks_duplicate_cycles_without_resetting_history() -> None:
    decoder = GarmentCycleDecoder(
        minimum_sewing_seconds=0.2, minimum_idle_seconds=0.2, cooldown_seconds=2.0
    )
    sequence = (
        ("SEWING", 0.0),
        ("SEWING", 0.3),
        ("IDLE_SETUP", 0.5),
        ("IDLE_SETUP", 0.8),
        ("SEWING", 1.0),
        ("SEWING", 1.3),
        ("IDLE_SETUP", 1.5),
        ("IDLE_SETUP", 1.8),
    )
    events = [event for label, moment in sequence if (event := decoder.update(label, moment, 0.9))]
    assert len(events) == 1
    assert decoder.last_completion == 0.5


def test_recovery_requires_stable_idle_before_another_sewing_cycle() -> None:
    decoder = GarmentCycleDecoder(
        minimum_sewing_seconds=0.2,
        minimum_idle_seconds=0.2,
        cooldown_seconds=0.1,
        minimum_rearm_idle_seconds=0.5,
    )
    decoder.require_idle_rearm()

    for label, moment in (
        ("SEWING", 1.0),
        ("SEWING", 1.5),
        ("IDLE_SETUP", 1.6),
        ("IDLE_SETUP", 1.9),
    ):
        assert decoder.update(label, moment, 0.95) is None
        assert decoder.needs_idle_rearm is True

    assert decoder.update("IDLE_SETUP", 2.2, 0.95) is None
    assert decoder.needs_idle_rearm is False
    assert decoder.update("SEWING", 2.3, 0.95) is None
    assert decoder.update("SEWING", 2.6, 0.95) is None
    assert decoder.update("IDLE_SETUP", 2.8, 0.95) is None
    assert decoder.update("IDLE_SETUP", 3.1, 0.95) is not None


def test_temporal_clips_require_eight_fresh_frames() -> None:
    frames = deque((float(index), index) for index in range(7))
    assert sample_clip(frames, 6.0) == []


def test_temporal_clips_evenly_sample_only_recent_frames() -> None:
    frames = deque((index / 10.0, index) for index in range(40))
    clip = sample_clip(frames, 3.9)
    assert len(clip) == 8
    assert clip[0] >= 24
    assert clip[-1] == 39
