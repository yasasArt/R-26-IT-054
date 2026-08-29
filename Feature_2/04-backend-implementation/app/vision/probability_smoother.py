from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum # type: ignore


class TemporalState(StrEnum):
    """States exposed by the temporal vision pipeline."""

    IDLE_SETUP = "IDLE_SETUP"
    SEWING = "SEWING"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class SmoothedPrediction:
    """One normalized and temporally smoothed classifier observation."""

    state: TemporalState
    idle_probability: float
    sewing_probability: float
    confidence: float
    sample_count: int

    @property
    def probabilities(self) -> dict[str, float]:
        return {
            TemporalState.IDLE_SETUP.value: self.idle_probability, # type: ignore
            TemporalState.SEWING.value: self.sewing_probability, # type: ignore
        }


class ProbabilitySmoother:

    def __init__(
        self,
        *,
        window_size: int = 5,
        confidence_threshold: float = 0.70,
        minimum_margin: float = 0.15,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        if not 0.5 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.5 and 1.0")
        if not 0.0 <= minimum_margin <= 1.0:
            raise ValueError("minimum_margin must be between 0.0 and 1.0")

        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.minimum_margin = minimum_margin
        self._history: deque[tuple[float, float]] = deque(maxlen=window_size)

    @staticmethod
    def _normalize(
        probabilities: Mapping[str, float] | Sequence[float],
    ) -> tuple[float, float]:
        if isinstance(probabilities, Mapping):
            try:
                idle = float(probabilities[TemporalState.IDLE_SETUP.value]) # type: ignore
                sewing = float(probabilities[TemporalState.SEWING.value]) # type: ignore
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "Probability mapping must contain numeric IDLE_SETUP and SEWING values"
                ) from exc
        else:
            if len(probabilities) != 2:
                raise ValueError(
                    "Probability sequence must use [IDLE_SETUP, SEWING] order"
                )
            try:
                idle, sewing = (float(value) for value in probabilities)
            except (TypeError, ValueError) as exc:
                raise ValueError("Probabilities must be numeric") from exc

        if not all(math.isfinite(value) for value in (idle, sewing)):
            raise ValueError("Probabilities must be finite")
        if idle < 0.0 or sewing < 0.0:
            raise ValueError("Probabilities cannot be negative")
        total = idle + sewing
        if total <= 0.0:
            raise ValueError("At least one probability must be positive")
        return idle / total, sewing / total

    def update(
        self,
        probabilities: Mapping[str, float] | Sequence[float],
    ) -> SmoothedPrediction:
        """Add one model observation and return the current smoothed state."""

        self._history.append(self._normalize(probabilities))
        sample_count = len(self._history)
        idle = sum(item[0] for item in self._history) / sample_count
        sewing = sum(item[1] for item in self._history) / sample_count
        confidence = max(idle, sewing)
        margin = abs(idle - sewing)

        if confidence < self.confidence_threshold or margin < self.minimum_margin:
            state = TemporalState.UNCERTAIN
        elif idle > sewing:
            state = TemporalState.IDLE_SETUP
        else:
            state = TemporalState.SEWING

        return SmoothedPrediction(
            state=state,
            idle_probability=round(idle, 6),
            sewing_probability=round(sewing, 6),
            confidence=round(confidence, 6),
            sample_count=sample_count,
        )

    def reset(self) -> None:
        """Discard observations when a session or video source changes."""

        self._history.clear()

    @property
    def sample_count(self) -> int:
        return len(self._history)
