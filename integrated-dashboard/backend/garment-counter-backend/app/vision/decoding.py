from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompletedGarment:
    sewing_started_at: float
    completed_at: float
    confidence: float


class WorkstationGate:
    """Require consecutive observations before opening or closing the view gate."""

    def __init__(self, opening_frames: int = 2, closing_frames: int = 3) -> None:
        self.opening_frames = max(1, opening_frames)
        self.closing_frames = max(1, closing_frames)
        self.confirmed = False
        self._visible_frames = 0
        self._missing_frames = 0

    def update(self, visible: bool) -> bool:
        if visible:
            self._visible_frames += 1
            self._missing_frames = 0
            if self._visible_frames >= self.opening_frames:
                self.confirmed = True
        else:
            self._visible_frames = 0
            self._missing_frames += 1
            if self._missing_frames >= self.closing_frames:
                self.confirmed = False
        return self.confirmed

    def reset(self) -> None:
        self.confirmed = False
        self._visible_frames = 0
        self._missing_frames = 0


class WorkstationLatch:
    """Latch an initial workstation and verify it periodically afterwards."""

    def __init__(
        self,
        initial_detections: int = 2,
        recheck_interval_seconds: float = 3.0,
        failed_recheck_limit: int = 3,
    ) -> None:
        self.initial_detections = max(1, initial_detections)
        self.recheck_interval_seconds = max(0.1, recheck_interval_seconds)
        self.failed_recheck_limit = max(1, failed_recheck_limit)
        self.reset()

    @property
    def confirmed(self) -> bool:
        return self.latched

    @property
    def failed_rechecks(self) -> int:
        return self._failed_rechecks

    def should_check(self, timestamp: float) -> bool:
        return not self.latched or timestamp >= self._next_recheck_at

    def update(self, visible: bool, timestamp: float) -> bool:
        if not self.latched:
            self._initial_hits = self._initial_hits + 1 if visible else 0
            if self._initial_hits >= self.initial_detections:
                self.latched = True
                self._failed_rechecks = 0
                self._next_recheck_at = timestamp + self.recheck_interval_seconds
            return self.latched

        self._next_recheck_at = timestamp + self.recheck_interval_seconds
        if visible:
            self._failed_rechecks = 0
            return True

        self._failed_rechecks += 1
        if self._failed_rechecks >= self.failed_recheck_limit:
            self.latched = False
            self._initial_hits = 0
            self._failed_rechecks = 0
        return self.latched

    def reset(self) -> None:
        self.latched = False
        self._initial_hits = 0
        self._failed_rechecks = 0
        self._next_recheck_at = 0.0


class ProbabilitySmoother:
    def __init__(
        self,
        labels: tuple[str, ...] = ("IDLE_SETUP", "SEWING"),
        window_size: int = 5,
        minimum_confidence: float = 0.55,
    ) -> None:
        self.labels = labels
        self.minimum_confidence = minimum_confidence
        self._window: deque[dict[str, float]] = deque(maxlen=max(1, window_size))

    def update(self, probabilities: dict[str, float]) -> tuple[str, float]:
        self._window.append(probabilities)
        averaged = {
            label: sum(item.get(label, 0.0) for item in self._window) / len(self._window)
            for label in self.labels
        }
        label = max(averaged, key=lambda item: averaged[item])
        confidence = averaged[label]
        return (label if confidence >= self.minimum_confidence else "UNCERTAIN", confidence)

    def reset(self) -> None:
        self._window.clear()


class GarmentCycleDecoder:
    """Emit exactly one garment for a confirmed SEWING -> IDLE_SETUP cycle."""

    def __init__(
        self,
        minimum_sewing_seconds: float = 2.0,
        minimum_idle_seconds: float = 0.6,
        cooldown_seconds: float = 5.0,
        minimum_rearm_idle_seconds: float = 1.2,
    ) -> None:
        self.minimum_sewing_seconds = minimum_sewing_seconds
        self.minimum_idle_seconds = minimum_idle_seconds
        self.cooldown_seconds = cooldown_seconds
        self.minimum_rearm_idle_seconds = minimum_rearm_idle_seconds
        self.last_completion: float | None = None
        self._needs_idle_rearm = False
        self._rearm_idle_started: float | None = None
        self.reset_cycle()

    def reset_cycle(self) -> None:
        self.phase = "WAITING_FOR_SEWING"
        self._label: str | None = None
        self._label_started: float | None = None
        self._sewing_started: float | None = None

    @property
    def needs_idle_rearm(self) -> bool:
        return self._needs_idle_rearm

    def require_idle_rearm(self) -> None:
        self.reset_cycle()
        self._needs_idle_rearm = True
        self._rearm_idle_started = None

    def update(self, label: str, timestamp: float, confidence: float) -> CompletedGarment | None:
        if self._needs_idle_rearm:
            if label != "IDLE_SETUP":
                self._rearm_idle_started = None
                return None

            if self._rearm_idle_started is None:
                self._rearm_idle_started = timestamp
                return None

            if timestamp - self._rearm_idle_started < self.minimum_rearm_idle_seconds:
                return None

            self._needs_idle_rearm = False
            self._rearm_idle_started = None
            self._label = "IDLE_SETUP"
            self._label_started = timestamp
            return None

        if label == "UNCERTAIN":
            return None

        if label != self._label:
            self._label = label
            self._label_started = timestamp
            if label == "SEWING" and self.phase == "WAITING_FOR_SEWING":
                self._sewing_started = timestamp

        assert self._label_started is not None
        duration = max(0.0, timestamp - self._label_started)

        if self.phase == "WAITING_FOR_SEWING":
            if label == "SEWING" and duration >= self.minimum_sewing_seconds:
                self.phase = "SEWING_CONFIRMED"
            return None

        if self.phase != "SEWING_CONFIRMED" or label != "IDLE_SETUP":
            return None

        if duration < self.minimum_idle_seconds:
            return None

        completed_at = self._label_started
        if (
            self.last_completion is not None
            and completed_at - self.last_completion < self.cooldown_seconds
        ):
            self.reset_cycle()
            return None

        sewing_started = self._sewing_started if self._sewing_started is not None else completed_at
        garment = CompletedGarment(sewing_started, completed_at, confidence)
        self.last_completion = completed_at
        self.reset_cycle()
        return garment
