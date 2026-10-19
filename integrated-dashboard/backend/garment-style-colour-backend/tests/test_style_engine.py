"""Behaviour tests for the live style engine, using synthetic camera frames.

The fake classifiers deliberately behave like the real ThreadScan model's
failure modes: it answers confidently even when shown bare table, and it can
flip between classes on ambiguous frames. Every rule the engine adds is
checked against one of the problems measured on the project's own data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from style_engine import EngineConfig, StyleCaptureEngine  # noqa: E402

NAMES = ["SHIRT", "SHORT", "TROUSER", "T_SHIRT"]
FPS = 15.0
RNG = np.random.default_rng(7)
TABLE_TEXTURE = RNG.normal(0, 6, (480, 640, 3))
RED_TABLE = (45, 40, 185)  # BGR
SKIN = (140, 172, 224)  # BGR, inside the YCrCb skin range
BEIGE = (168, 201, 216)  # BGR, a skin-toned fabric


def scores(**values: float) -> np.ndarray:
    return np.array([values.get(name, 0.0) for name in NAMES], dtype=np.float32)


class Always:
    """Classifier that always gives the same answer (like the real model
    answering T_SHIRT/SHORT for an empty table)."""

    def __init__(self, **values: float):
        self.result = scores(**values)
        self.calls = 0

    def __call__(self, crop):
        self.calls += 1
        return self.result


class Alternating:
    def __init__(self):
        self.calls = 0

    def __call__(self, crop):
        self.calls += 1
        return scores(SHIRT=0.7, T_SHIRT=0.3) if self.calls % 2 else scores(SHIRT=0.3, T_SHIRT=0.7)


def table(brightness: float = 0.0) -> np.ndarray:
    frame = np.empty((480, 640, 3), dtype=np.float32)
    frame[:] = RED_TABLE
    frame += TABLE_TEXTURE + brightness + RNG.normal(0, 1.5, (480, 640, 3))
    return np.clip(frame, 0, 255).astype(np.uint8)


def with_garment(frame, x, y, w=240, h=200, colour=(30, 30, 30)):
    out = frame.copy()
    body = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.int32)
    cv2.fillPoly(out, [body], colour)
    # sleeves: makes it a T-shirt-like silhouette with real texture
    cv2.rectangle(out, (x - 50, y), (x, y + 70), colour, -1)
    cv2.rectangle(out, (x + w, y), (x + w + 50, y + 70), colour, -1)
    for row in range(y + 10, y + h, 25):
        cv2.line(out, (x + 10, row), (x + w - 10, row), tuple(int(c) + 25 for c in colour), 2)
    return out


def with_hand(frame, x, y):
    out = frame.copy()
    cv2.ellipse(out, (x, y), (45, 28), 20, 0, 360, SKIN, -1)
    cv2.rectangle(out, (x + 20, y - 15), (x + 160, y + 15), SKIN, -1)  # forearm
    return out


class Clock:
    def __init__(self):
        self.now = 0.0

    def tick(self):
        self.now += 1.0 / FPS
        return self.now


def run(engine, clock, frame_fn, seconds):
    results = []
    for index in range(int(seconds * FPS)):
        results.append(engine.process(frame_fn(index), clock.tick()))
    return results


def captures(results):
    return [result.capture for result in results if result.capture is not None]


def calibrated_engine(classifier, **config):
    engine = StyleCaptureEngine(classifier, NAMES, EngineConfig(**config))
    clock = Clock()
    results = run(engine, clock, lambda i: table(), 2.0)
    assert results[-1].state == "EMPTY"
    assert engine.calibrated
    return engine, clock


def test_calibration_waits_for_a_still_empty_zone():
    engine = StyleCaptureEngine(Always(SHORT=0.9), NAMES, EngineConfig())
    clock = Clock()
    # Somebody keeps moving in the zone: no background is learned.
    moving = run(engine, clock, lambda i: with_garment(table(), 100 + 12 * i, 120), 1.5)
    assert all(result.state == "CALIBRATING" for result in moving)
    still = run(engine, clock, lambda i: table(), 2.0)
    assert still[-1].state == "EMPTY" and engine.calibrated


def test_empty_table_is_never_captured_even_if_the_model_hallucinates():
    model = Always(SHORT=0.94)  # what the real model says about bare red table
    engine, clock = calibrated_engine(model)
    results = run(engine, clock, lambda i: table(brightness=8 * np.sin(i / 10)), 6.0)
    assert captures(results) == []
    assert model.calls == 0
    assert all(result.state == "EMPTY" for result in results)


def test_moving_garment_is_not_classified_until_it_settles():
    model = Always(T_SHIRT=0.9)
    engine, clock = calibrated_engine(model)
    moving = run(engine, clock, lambda i: with_garment(table(), 120 + 9 * i, 140), 1.2)
    assert captures(moving) == []
    assert model.calls == 0
    settled = run(engine, clock, lambda i: with_garment(table(), 240, 140), 2.0)
    found = captures(settled)
    assert len(found) == 1
    assert found[0].style == "T_SHIRT"
    assert found[0].agreement == 1.0
    # The crop is tight around the garment, not the whole folding zone.
    assert found[0].image.shape[1] < 420 and found[0].image.shape[0] < 280


def test_folding_the_same_garment_never_creates_a_second_record():
    model = Always(T_SHIRT=0.9)
    engine, clock = calibrated_engine(model)
    first = run(engine, clock, lambda i: with_garment(table(), 240, 140), 2.0)
    assert len(captures(first)) == 1

    # Folding: the outline shrinks step by step and pauses between folds.
    # The real model would call a folded garment SHORT - it must not matter.
    model.result = scores(SHORT=0.95)

    def folding(i):
        step = min(i // 20, 4)
        return with_garment(table(), 240 + 15 * step, 140 + 10 * step, w=240 - 40 * step, h=200 - 30 * step)

    during = run(engine, clock, folding, 8.0)
    assert captures(during) == []
    assert during[-1].state == "WAITING_REMOVAL"
    assert during[-1].style == "T_SHIRT"


def test_zone_unlocks_after_the_garment_is_removed():
    model = Always(T_SHIRT=0.9)
    engine, clock = calibrated_engine(model)
    assert len(captures(run(engine, clock, lambda i: with_garment(table(), 240, 140), 2.0))) == 1
    # A short gap (hand lifts the garment for a moment) does not unlock...
    run(engine, clock, lambda i: table(), 0.5)
    assert engine.locked
    # ...but a genuinely empty zone does, and the next garment is captured.
    run(engine, clock, lambda i: table(), 1.5)
    assert not engine.locked
    model.result = scores(SHIRT=0.88, T_SHIRT=0.1)
    second = captures(run(engine, clock, lambda i: with_garment(table(), 200, 160, colour=(150, 150, 150)), 2.0))
    assert [capture.style for capture in second] == ["SHIRT"]


def test_hand_covering_the_garment_blocks_classification():
    model = Always(SHIRT=0.9)
    engine, clock = calibrated_engine(model)
    results = run(engine, clock, lambda i: with_hand(with_garment(table(), 240, 140), 330, 230), 2.5)
    assert captures(results) == []
    assert model.calls == 0
    assert results[-1].state == "DETECTING"
    assert "Hand" in results[-1].detail
    # Once the hand is withdrawn the garment is captured.
    after = run(engine, clock, lambda i: with_garment(table(), 240, 140), 2.0)
    assert len(captures(after)) == 1


def test_skin_toned_garment_is_not_mistaken_for_a_hand():
    model = Always(SHORT=0.9)
    engine, clock = calibrated_engine(model)
    results = run(engine, clock, lambda i: with_garment(table(), 220, 140, colour=BEIGE), 2.0)
    assert [capture.style for capture in captures(results)] == ["SHORT"]


def test_disagreeing_frames_are_reported_uncertain_not_captured():
    engine, clock = calibrated_engine(Alternating())
    results = run(engine, clock, lambda i: with_garment(table(), 240, 140), 3.0)
    assert captures(results) == []
    assert results[-1].state == "UNCERTAIN"


def test_low_confidence_is_not_captured():
    engine, clock = calibrated_engine(Always(SHIRT=0.45, T_SHIRT=0.1))
    assert captures(run(engine, clock, lambda i: with_garment(table(), 240, 140), 3.0)) == []


def test_webcam_exposure_shift_does_not_create_a_garment():
    model = Always(T_SHIRT=0.9)
    engine, clock = calibrated_engine(model)
    results = run(engine, clock, lambda i: table(brightness=-18), 3.0)
    assert captures(results) == []
    assert model.calls == 0


def test_object_left_during_calibration_is_healed_when_removed():
    model = Always(SHORT=0.94)
    engine = StyleCaptureEngine(model, NAMES, EngineConfig())
    clock = Clock()
    # The background was learned while a garment was lying on the table.
    run(engine, clock, lambda i: with_garment(table(), 240, 140), 2.0)
    assert engine.calibrated
    # It is taken away: the bare table must not be "detected" as a garment.
    results = run(engine, clock, lambda i: table(), 4.0)
    assert captures(results) == []
    assert results[-1].state == "EMPTY"


def test_camera_change_resets_learning():
    engine, clock = calibrated_engine(Always(T_SHIRT=0.9))
    engine.reset()
    assert not engine.calibrated
    assert engine.process(table(), clock.tick()).state == "CALIBRATING"


@pytest.mark.parametrize("name", ["min_confidence", "vote_frames", "foreground_delta_e"])
def test_thresholds_can_be_overridden_from_the_environment(monkeypatch, name):
    default = getattr(EngineConfig(), name)
    monkeypatch.setenv(f"THREADSCAN_{name.upper()}", "7")
    value = getattr(EngineConfig.from_env(), name)
    assert value == 7 and type(value) is type(default)
