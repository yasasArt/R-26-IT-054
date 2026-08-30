"""Decode stable classifier states into exactly one event per garment cycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime # type: ignore

from app.vision.probability_smoother import SmoothedPrediction, TemporalState


@dataclass(frozen=True, slots=True)
class ConfirmedGarmentCycle:
    """A valid cycle ready for Phase 10 persistence."""

    sewing_started_at: datetime
    completed_at: datetime
    sewing_duration_seconds: float
    confidence: float

    def event_key(self, session_id: int) -> str:
        """Build a stable key for the existing idempotent production service."""

        completed_milliseconds = int(self.completed_at.timestamp() * 1000)
        return f"vision:{session_id}:{completed_milliseconds}"


@dataclass(frozen=True, slots=True)
class DecoderSnapshot:
    stable_state: TemporalState
    candidate_state: TemporalState | None
    candidate_frames: int
    idle_rearmed: bool
    sewing_started_at: datetime | None
    last_confirmed_at: datetime | None


@dataclass(frozen=True, slots=True)
class DecoderResult:
    snapshot: DecoderSnapshot
    event: ConfirmedGarmentCycle | None = None
    blocked_reason: str | None = None


class GarmentCycleDecoder:

    def __init__(
        self,
        *,
        state_confirmation_frames: int = 3,
        minimum_sewing_duration_seconds: float = 1.0,
        minimum_idle_duration_seconds: float = 0.5,
        cooldown_seconds: float = 1.5,
    ) -> None:
        if state_confirmation_frames < 1:
            raise ValueError("state_confirmation_frames must be at least 1")
        if minimum_sewing_duration_seconds <= 0:
            raise ValueError("minimum_sewing_duration_seconds must be positive")
        if minimum_idle_duration_seconds < 0:
            raise ValueError("minimum_idle_duration_seconds cannot be negative")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")

        self.state_confirmation_frames = state_confirmation_frames
        self.minimum_sewing_duration_seconds = minimum_sewing_duration_seconds
        self.minimum_idle_duration_seconds = minimum_idle_duration_seconds
        self.cooldown_seconds = cooldown_seconds
        self.reset()

    def reset(self, *, preserve_cooldown: bool = False) -> None:
        """Clear temporal state and require a fresh stable idle observation."""

        last_confirmed = getattr(self, "last_confirmed_at", None)
        self.stable_state = TemporalState.UNCERTAIN
        self.candidate_state: TemporalState | None = None
        self.candidate_frames = 0
        self.candidate_started_at: datetime | None = None
        self.idle_started_at: datetime | None = None
        self.idle_rearmed = False
        self.sewing_started_at: datetime | None = None
        self.last_observed_at: datetime | None = None
        self.last_confirmed_at = last_confirmed if preserve_cooldown else None

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Observation timestamp must include a timezone")
        return value.astimezone(UTC)

    def _snapshot(self) -> DecoderSnapshot:
        return DecoderSnapshot(
            stable_state=self.stable_state,
            candidate_state=self.candidate_state,
            candidate_frames=self.candidate_frames,
            idle_rearmed=self.idle_rearmed,
            sewing_started_at=self.sewing_started_at,
            last_confirmed_at=self.last_confirmed_at,
        )

    def _invalidate_for_gate(self, reason: str) -> DecoderResult:
        """Drop an in-flight cycle so it cannot count after mode recovery."""

        last_observed = self.last_observed_at
        self.reset(preserve_cooldown=True)
        self.last_observed_at = last_observed
        return DecoderResult(snapshot=self._snapshot(), blocked_reason=reason)

    def _update_candidate(
        self,
        state: TemporalState,
        observed_at: datetime,
    ) -> datetime | None:
        if state != self.candidate_state:
            self.candidate_state = state
            self.candidate_frames = 1
            self.candidate_started_at = observed_at
        else:
            self.candidate_frames += 1

        if self.candidate_frames < self.state_confirmation_frames:
            return None
        if state == self.stable_state:
            return None

        transition_started_at = self.candidate_started_at
        self.stable_state = state
        return transition_started_at

    def _refresh_idle_rearm(self, observed_at: datetime) -> None:
        if (
            self.stable_state == TemporalState.IDLE_SETUP
            and self.idle_started_at is not None
            and self.sewing_started_at is None
        ):
            idle_seconds = (observed_at - self.idle_started_at).total_seconds()
            if idle_seconds >= self.minimum_idle_duration_seconds:
                self.idle_rearmed = True

    def _on_transition(
        self,
        state: TemporalState,
        transition_started_at: datetime,
        confidence: float,
    ) -> ConfirmedGarmentCycle | None:
        if state == TemporalState.IDLE_SETUP:
            self.idle_started_at = transition_started_at
            if self.sewing_started_at is None:
                return None

            sewing_started_at = self.sewing_started_at
            self.sewing_started_at = None
            was_rearmed = self.idle_rearmed
            self.idle_rearmed = False
            duration = (transition_started_at - sewing_started_at).total_seconds()
            cooldown_ok = (
                self.last_confirmed_at is None
                or (transition_started_at - self.last_confirmed_at).total_seconds()
                >= self.cooldown_seconds
            )
            if (
                was_rearmed
                and duration >= self.minimum_sewing_duration_seconds
                and cooldown_ok
            ):
                event = ConfirmedGarmentCycle(
                    sewing_started_at=sewing_started_at,
                    completed_at=transition_started_at,
                    sewing_duration_seconds=round(duration, 3),
                    confidence=round(confidence, 6),
                )
                self.last_confirmed_at = transition_started_at
                return event
            return None

        if state == TemporalState.SEWING:
            if self.idle_rearmed and self.sewing_started_at is None:
                self.sewing_started_at = transition_started_at
            return None

        # A stable uncertain period does not fabricate a transition or erase a
        # valid sewing start. The next confirmed IDLE_SETUP can still complete it.
        return None

    def update(
        self,
        prediction: SmoothedPrediction,
        observed_at: datetime,
        *,
        session_status: str,
        operator_mode: str,
    ) -> DecoderResult:
        """Process one smoothed prediction and possibly emit one cycle."""

        observed_at = self._aware_utc(observed_at)
        if self.last_observed_at is not None and observed_at < self.last_observed_at:
            raise ValueError("Observation timestamps must be monotonic")
        self.last_observed_at = observed_at

        if session_status != "ACTIVE":
            return self._invalidate_for_gate("Session is not active")
        if operator_mode != "NORMAL":
            return self._invalidate_for_gate(
                "Garment counting is blocked during rework or downtime"
            )

        transition_started_at = self._update_candidate(prediction.state, observed_at)
        event = None
        if transition_started_at is not None:
            event = self._on_transition(
                prediction.state,
                transition_started_at,
                prediction.confidence,
            )
        self._refresh_idle_rearm(observed_at)
        return DecoderResult(snapshot=self._snapshot(), event=event)
