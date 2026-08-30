from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta # type: ignore
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from app.config import Settings
from app.db.connection import connect_database
from app.errors import ConflictError, ResourceNotFoundError
from app.repositories.session_repository import SessionRepository
from app.schemas.piece_event import EventSource
from app.schemas.vision import (
    VisionRuntimeState,
    VisionRuntimeStatus,
    VisionSourceType,
    WorkstationState,
)
from app.services.production_service import ProductionService
from app.vision.camera_manager import CameraManager, CapturedFrame
from app.vision.classifier import prepare_clip, require_torch, torch
from app.vision.cycle_decoder import GarmentCycleDecoder
from app.vision.model_registry import ModelRegistry
from app.vision.probability_smoother import ProbabilitySmoother, TemporalState
from app.vision.stream import FramePublisher
from app.vision.workstation_detector import WorkstationLatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VisionSource:
    source_type: VisionSourceType
    camera_index: int | None = None
    video_path: Path | None = None

    def __post_init__(self) -> None:
        if self.source_type == VisionSourceType.CAMERA:
            if self.video_path is not None:
                raise ValueError("A camera source cannot include a video path")
            return  # A missing index is resolved from the persisted session snapshot.
        if self.video_path is None:
            raise ValueError("A video source requires a video path")
        if self.camera_index is not None:
            raise ValueError("A video source cannot include a camera index")

    @property
    def label(self) -> str:
        if self.source_type == VisionSourceType.CAMERA:
            return f"camera:{self.camera_index}"
        assert self.video_path is not None
        return f"video:{self.video_path.name}"


class TemporalClipBuffer:
    """Retain source-time frames and sample an evenly spaced temporal clip."""

    def __init__(
        self,
        *,
        frame_count: int = 8,
        clip_seconds: float = 1.5,
        inference_interval_seconds: float = 0.3,
    ) -> None:
        if frame_count < 2:
            raise ValueError("frame_count must be at least 2")
        if clip_seconds <= 0 or inference_interval_seconds <= 0:
            raise ValueError("Clip and inference intervals must be positive")
        self.frame_count = frame_count
        self.clip_seconds = clip_seconds
        self.inference_interval_seconds = inference_interval_seconds
        self._frames: deque[tuple[datetime, np.ndarray]] = deque()
        self._last_inferred_at: datetime | None = None

    def clear(self) -> None:
        self._frames.clear()
        self._last_inferred_at = None

    def add(self, frame: np.ndarray, observed_at: datetime) -> None:
        if self._frames and observed_at < self._frames[-1][0]:
            raise ValueError("Clip timestamps must be monotonic")
        self._frames.append((observed_at, np.asarray(frame).copy()))
        cutoff = observed_at - timedelta(seconds=self.clip_seconds)
        while len(self._frames) > 1 and self._frames[1][0] <= cutoff:
            self._frames.popleft()

    def ready(self, observed_at: datetime) -> bool:
        if len(self._frames) < self.frame_count:
            return False
        if (observed_at - self._frames[0][0]).total_seconds() < self.clip_seconds:
            return False
        return (
            self._last_inferred_at is None
            or (observed_at - self._last_inferred_at).total_seconds()
            >= self.inference_interval_seconds
        )

    def sample(self, observed_at: datetime) -> list[np.ndarray]:
        if not self.ready(observed_at):
            raise RuntimeError("Temporal clip is not ready")
        available = list(self._frames)
        start = observed_at - timedelta(seconds=self.clip_seconds)
        step = self.clip_seconds / (self.frame_count - 1)
        targets = [
            start + timedelta(seconds=step * index) for index in range(self.frame_count)
        ]
        sampled = [
            min(available, key=lambda item: abs((item[0] - target).total_seconds()))[1]
            for target in targets
        ]
        self._last_inferred_at = observed_at
        return sampled


CaptureBuilder = Callable[[VisionSource], CameraManager]
ClassifierPredictor = Callable[[Sequence[np.ndarray]], Sequence[float]]
DetectorPredictor = Callable[[np.ndarray], bool]


class VisionRuntime:
    """Own one live inference worker for the single active production session."""

    ACTIVE_STATES: ClassVar[frozenset[VisionRuntimeState]] = frozenset(
        {
            VisionRuntimeState.STARTING,
            VisionRuntimeState.WAITING_FOR_PREVIEW,
            VisionRuntimeState.RUNNING,
        }
    ) # type: ignore

    def __init__(
        self,
        settings: Settings,
        model_registry: ModelRegistry,
        *,
        capture_builder: CaptureBuilder | None = None,
        classifier_predictor: ClassifierPredictor | None = None,
        detector_predictor: DetectorPredictor | None = None,
        frame_publisher: FramePublisher | None = None,
    ) -> None:
        self.settings = settings
        self.model_registry = model_registry
        self.publisher = frame_publisher or FramePublisher(
            jpeg_quality=settings.vision_preview_jpeg_quality
        )
        self._capture_builder = capture_builder or self._default_capture_builder
        self._classifier_predictor = (
            classifier_predictor or self._default_classifier_predictor
        )
        self._detector_predictor = (
            detector_predictor or self._default_detector_predictor
        )
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: CameraManager | None = None
        self._status = VisionRuntimeStatus(state=VisionRuntimeState.STOPPED)

    @property
    def status(self) -> VisionRuntimeStatus:
        with self._lock:
            return self._status.model_copy(
                update={
                    "preview_ready": self.publisher.preview_ready,
                    "preview_subscribers": self.publisher.subscriber_count,
                },
                deep=True,
            )

    def _update_status(self, **changes: Any) -> None:
        with self._lock:
            self._status = self._status.model_copy(update=changes)

    def _default_capture_builder(self, source: VisionSource) -> CameraManager:
        return CameraManager(
            source_type=source.source_type,
            camera_index=source.camera_index,
            video_path=source.video_path,
        )

    def _default_detector_predictor(self, frame: np.ndarray) -> bool:
        detector = self.model_registry.workstation_detector
        if detector is None:
            raise RuntimeError("Workstation detector is not loaded")
        return bool(detector.predict(frame))

    def _default_classifier_predictor(
        self,
        frames: Sequence[np.ndarray],
    ) -> Sequence[float]:
        require_torch()
        classifier = self.model_registry.classifier
        if classifier is None or torch is None:
            raise RuntimeError("Garment classifier is not loaded")
        rgb_frames = [np.asarray(frame)[..., ::-1].copy() for frame in frames]
        clip = prepare_clip(rgb_frames, device=self.model_registry.device)
        with torch.inference_mode():
            logits = classifier(clip)
            probabilities = torch.softmax(logits, dim=1)[0].detach().cpu().tolist()
        return [float(value) for value in probabilities]

    def _require_startable_session(self, session_id: int, source: VisionSource) -> dict:
        assert self.settings.database_path is not None
        connection = connect_database(self.settings.database_path)
        try:
            session = SessionRepository(connection).find_by_id(session_id)
        finally:
            connection.close()
        if session is None:
            raise ResourceNotFoundError(f"Session {session_id} was not found")
        if session["status"] != "ACTIVE":
            raise ConflictError("Vision can only start for an active session")
        if session["operator_mode"] != "NORMAL":
            raise ConflictError("Vision cannot start during rework or downtime")
        if (
            source.source_type == VisionSourceType.VIDEO
            and session["session_mode"] != "VALIDATION"
        ):
            raise ConflictError("Recorded videos can only run in VALIDATION sessions")
        if source.source_type == VisionSourceType.CAMERA:
            snapshot_index = session["camera_index_snapshot"]
            if snapshot_index is None:
                raise ConflictError("The session has no verified camera snapshot")
            if source.camera_index is not None and source.camera_index != int(
                snapshot_index
            ):
                raise ConflictError(
                    "Camera index must match the verified session camera"
                )
        return session

    def start(self, session_id: int, source: VisionSource) -> VisionRuntimeStatus:
        """Validate synchronously, then start capture and inference in one worker."""

        with self._lock:
            if self._status.state in self.ACTIVE_STATES:
                raise ConflictError("Vision runtime is already running")
        if not self.model_registry.status.ready:
            raise ConflictError("Vision models are not ready")

        session = self._require_startable_session(session_id, source)
        if (
            source.source_type == VisionSourceType.CAMERA
            and source.camera_index is None
        ):
            source = VisionSource(
                source_type=VisionSourceType.CAMERA,
                camera_index=int(session["camera_index_snapshot"]),
            )

        self.publisher.reset()
        self._stop_event.clear()
        now = datetime.now(UTC)
        with self._lock:
            self._status = VisionRuntimeStatus(
                state=VisionRuntimeState.STARTING,
                session_id=session_id,
                source_type=source.source_type, # type: ignore
                source_label=source.label,
                started_at=now,
                confirmed_pieces=int(session["total_pieces"]),
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(session_id, source),
                name=f"vision-session-{session_id}",
                daemon=True,
            )
            self._thread.start()
        return self.status

    def _new_pipeline(
        self,
    ) -> tuple[
        WorkstationLatch,
        TemporalClipBuffer,
        ProbabilitySmoother,
        GarmentCycleDecoder,
    ]:
        latch = WorkstationLatch(
            confirmations_required=self.settings.workstation_initial_confirmations,
            initial_check_interval_seconds=(
                self.settings.workstation_initial_check_interval_seconds
            ),
            recheck_interval_seconds=self.settings.workstation_recheck_interval_seconds,
            allowed_failed_rechecks=(self.settings.workstation_allowed_failed_rechecks),
        )
        clips = TemporalClipBuffer(
            frame_count=8,
            clip_seconds=self.settings.vision_clip_seconds,
            inference_interval_seconds=self.settings.vision_inference_interval_seconds,
        )
        smoother = ProbabilitySmoother(
            window_size=self.settings.vision_probability_window,
            confidence_threshold=self.settings.vision_confidence_threshold,
            minimum_margin=self.settings.vision_minimum_probability_margin,
        )
        decoder = GarmentCycleDecoder(
            state_confirmation_frames=self.settings.vision_state_confirmation_frames,
            minimum_sewing_duration_seconds=(
                self.settings.vision_minimum_sewing_seconds
            ),
            minimum_idle_duration_seconds=self.settings.vision_minimum_idle_seconds,
            cooldown_seconds=self.settings.vision_cooldown_seconds,
        )
        return latch, clips, smoother, decoder

    def _persist_event(
        self,
        service: ProductionService,
        session_id: int,
        event: Any,
    ) -> int:
        service.mark_first_sewing_started(session_id, event.sewing_started_at)
        confirmation = service.confirm_piece(
            session_id,
            event_key=event.event_key(session_id),
            completed_at=event.completed_at,
            confidence=event.confidence,
            event_source=EventSource.VISION,
        )
        return confirmation.summary.total_pieces

    def _pace_video(
        self,
        frame: CapturedFrame,
        *,
        wall_started: float,
        source_started: float,
    ) -> bool:
        if not self.settings.vision_video_realtime_playback:
            return False
        target = wall_started + (frame.source_position_seconds - source_started)
        delay = target - time.monotonic()
        return delay > 0 and self._stop_event.wait(delay)

    def _process_frame(
        self,
        frame: CapturedFrame,
        session: dict,
        latch: WorkstationLatch,
        clips: TemporalClipBuffer,
        smoother: ProbabilitySmoother,
        decoder: GarmentCycleDecoder,
        service: ProductionService,
    ) -> None:
        if session["operator_mode"] != "NORMAL":
            decoder.reset(preserve_cooldown=True)
            smoother.reset()
            clips.clear()
            self._update_status(
                stable_state=TemporalState.UNCERTAIN,
                idle_rearmed=False,
            )
            return

        if latch.should_check(frame.observed_at):
            update = latch.observe(
                self._detector_predictor(frame.image), frame.observed_at
            )
            self._update_status(
                workstation_state=WorkstationState(update.state),
                workstation_available=update.available,
                workstation_failed_rechecks=update.failed_rechecks,
            )
            if update.paused or update.reacquired:
                decoder.reset(preserve_cooldown=True)
                smoother.reset()
                clips.clear()
                self._update_status(
                    stable_state=TemporalState.UNCERTAIN,
                    idle_rearmed=False,
                    last_probabilities=None,
                )

        if not latch.available:
            return

        clips.add(frame.image, frame.observed_at)
        if not clips.ready(frame.observed_at):
            return

        probabilities = self._classifier_predictor(clips.sample(frame.observed_at))
        smoothed = smoother.update(probabilities)
        result = decoder.update(
            smoothed,
            frame.observed_at,
            session_status=session["status"],
            operator_mode=session["operator_mode"],
        )
        current = self.status
        self._update_status(
            inference_count=current.inference_count + 1,
            last_probabilities=smoothed.probabilities,
            stable_state=result.snapshot.stable_state,
            idle_rearmed=result.snapshot.idle_rearmed,
        )
        if result.event is not None:
            try:
                total = self._persist_event(service, int(session["id"]), result.event)
            except ConflictError:
                decoder.reset(preserve_cooldown=True)
                smoother.reset()
                clips.clear()
                return
            self._update_status(confirmed_pieces=total)

    def _run(self, session_id: int, source: VisionSource) -> None:
        capture: CameraManager | None = None
        connection = None
        final_state = VisionRuntimeState.COMPLETED
        stop_reason = "END_OF_STREAM"
        try:
            assert self.settings.database_path is not None
            connection = connect_database(self.settings.database_path)
            sessions = SessionRepository(connection)
            service = ProductionService(
                connection,
                minimum_piece_gap_seconds=self.settings.minimum_piece_gap_seconds,
            )
            latch, clips, smoother, decoder = self._new_pipeline()
            capture = self._capture_builder(source)
            with self._lock:
                self._capture = capture
            capture.open()
            frame = capture.read()
            if frame is None:
                raise RuntimeError("Capture source contains no decodable frames")

            self.publisher.publish(frame.image)
            self._update_status(preview_ready=True)
            if source.source_type == VisionSourceType.VIDEO:
                self._update_status(state=VisionRuntimeState.WAITING_FOR_PREVIEW)
                attached = self.publisher.wait_for_subscriber(
                    self.settings.vision_preview_wait_seconds
                )
                if not attached:
                    if self._stop_event.is_set():
                        final_state = VisionRuntimeState.STOPPED
                        stop_reason = "STOP_REQUESTED"
                        return
                    raise RuntimeError(
                        "Preview stream was not attached before the timeout"
                    )

            self._update_status(state=VisionRuntimeState.RUNNING)
            wall_started = time.monotonic()
            source_started = frame.source_position_seconds
            first_frame = True

            while frame is not None and not self._stop_event.is_set():
                session = sessions.find_by_id(session_id)
                if session is None or session["status"] != "ACTIVE":
                    stop_reason = "SESSION_ENDED"
                    break

                if not first_frame:
                    if (
                        source.source_type == VisionSourceType.VIDEO
                        and self._pace_video(
                            frame,
                            wall_started=wall_started,
                            source_started=source_started,
                        )
                    ):
                        final_state = VisionRuntimeState.STOPPED
                        stop_reason = "STOP_REQUESTED"
                        break
                    self.publisher.publish(frame.image)
                first_frame = False

                current = self.status
                self._update_status(processed_frames=current.processed_frames + 1)
                self._process_frame(
                    frame,
                    session,
                    latch,
                    clips,
                    smoother,
                    decoder,
                    service,
                )
                frame = capture.read()

            if self._stop_event.is_set():
                final_state = VisionRuntimeState.STOPPED
                stop_reason = "STOP_REQUESTED"
        except Exception as exc:
            logger.exception("Vision runtime failed")
            final_state = VisionRuntimeState.ERROR
            stop_reason = "RUNTIME_ERROR"
            self._update_status(last_error=str(exc))
        finally:
            if capture is not None:
                capture.close()
            if connection is not None:
                connection.close()
            self.publisher.close()
            with self._lock:
                self._capture = None
                self._status = self._status.model_copy(
                    update={
                        "state": final_state,
                        "stopped_at": datetime.now(UTC),
                        "stop_reason": stop_reason,
                    }
                )

    def stop(self, *, wait: bool = True, timeout: float = 5.0) -> VisionRuntimeStatus:
        """Signal the worker, release capture and optionally wait for shutdown."""

        self._stop_event.set()
        self.publisher.close()
        with self._lock:
            capture = self._capture
            thread = self._thread
        if capture is not None:
            capture.close()
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                self._update_status(
                    state=VisionRuntimeState.ERROR,
                    last_error="Vision worker did not stop within the timeout",
                    stop_reason="STOP_TIMEOUT",
                )
        return self.status

    def wait(self, timeout: float = 10.0) -> VisionRuntimeStatus:
        """Join the current worker; intended for shutdown and deterministic tests."""

        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.status
