from __future__ import annotations

import sys
import threading
import time
from collections import deque
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

from fastapi import HTTPException

from app.config import Settings
from app.database import connect, transaction
from app.production import persist_piece_event
from app.schemas import PieceCreate
from app.time_utils import format_utc, utc_now
from app.vision.decoding import GarmentCycleDecoder, ProbabilitySmoother, WorkstationLatch
from app.vision.registry import VisionModelRegistry

PREDICTION_INTERVAL_SECONDS = 0.3
CLIP_DURATION_SECONDS = 1.5
CLIP_FRAME_COUNT = 8
WORKSTATION_RECHECK_INTERVAL_SECONDS = 3.0
WORKSTATION_FAILED_RECHECK_LIMIT = 3
MAX_CAMERA_INDEX = 5
CAMERA_FRAME_TIMEOUT_SECONDS = 3.0
CAMERA_FRAME_RETRY_SECONDS = 0.08


def get_opencv() -> Any:
    try:
        import cv2
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "OpenCV is not installed. Install the Phase 3 backend vision dependencies."
        ) from error
    return cv2


def open_camera_capture(cv2: Any, camera_index: int) -> Any:
    """Use macOS's native AVFoundation capture path when it is available."""

    if sys.platform == "darwin" and hasattr(cv2, "CAP_AVFOUNDATION"):
        capture = cv2.VideoCapture(camera_index, cv2.CAP_AVFOUNDATION)
        if capture.isOpened():
            return capture
        capture.release()

    return cv2.VideoCapture(camera_index)


def read_usable_camera_frame(
    capture: Any,
    timeout_seconds: float = CAMERA_FRAME_TIMEOUT_SECONDS,
) -> Any | None:
    """Allow camera ownership/warm-up to settle before rejecting empty frames."""

    deadline = time.monotonic() + max(0.0, timeout_seconds)

    while True:
        success, frame = capture.read()
        if success and frame is not None and getattr(frame, "size", 1) > 0:
            return frame

        if time.monotonic() >= deadline:
            return None

        time.sleep(CAMERA_FRAME_RETRY_SECONDS)


def sample_clip(frames: deque[tuple[float, Any]], timestamp: float) -> list[Any]:
    recent = [frame for recorded_at, frame in frames if timestamp - recorded_at <= CLIP_DURATION_SECONDS]
    if len(recent) < CLIP_FRAME_COUNT:
        return []
    last_index = len(recent) - 1
    indexes = [round(index * last_index / (CLIP_FRAME_COUNT - 1)) for index in range(CLIP_FRAME_COUNT)]
    return [recent[index] for index in indexes]


class VisionRuntime:
    def __init__(self, settings: Settings, registry: VisionModelRegistry) -> None:
        self.settings = settings
        self.registry = registry
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._preview_connected = threading.Event()
        self._thread: threading.Thread | None = None
        self._session_id: int | None = None
        self._latest_jpeg: bytes | None = None
        self._camera_preflight: dict[str, dict[str, Any]] = {}
        self._status = self._initial_status()

    @staticmethod
    def _initial_status() -> dict[str, Any]:
        return {
            "running": False,
            "phase": "STOPPED",
            "session_id": None,
            "source_type": None,
            "source_label": None,
            "test_workflow": False,
            "sewing_state": "UNCERTAIN",
            "classification_confidence": 0.0,
            "workstation_visible": False,
            "workstation_confirmed": False,
            "workstation_confidence": 0.0,
            "workstation_bbox": None,
            "workstation_message": "Start camera monitoring to verify the sewing workstation.",
            "counting_permitted": False,
            "counting_message": "Live monitoring has not started.",
            "processing_fps": 0.0,
            "buffered_frames": 0,
            "frames_processed": 0,
            "preview_ready": False,
            "last_event": None,
            "last_error": None,
            "updated_at": format_utc(utc_now()),
        }

    def status(self, session_id: int | None = None) -> dict[str, Any]:
        with self._lock:
            if session_id is not None and session_id != self._session_id:
                result = self._initial_status()
                result["session_id"] = session_id
            else:
                result = dict(self._status)
        result["models"] = self.registry.snapshot()
        return result

    def preflight(self, camera_id: str | None) -> dict[str, Any] | None:
        if not camera_id:
            return None
        with self._lock:
            result = self._camera_preflight.get(camera_id)
            return dict(result) if result else None

    def scan_cameras(self, expected_count: int | None = None) -> list[dict[str, Any]]:
        self._assert_not_running("Camera discovery is unavailable while live monitoring is active.")
        cv2 = get_opencv()
        discovered: list[dict[str, Any]] = []
        scan_limit = min(MAX_CAMERA_INDEX, max(1, expected_count or MAX_CAMERA_INDEX))
        for camera_index in range(scan_limit):
            capture = open_camera_capture(cv2, camera_index)
            try:
                if not capture.isOpened():
                    continue
                frame = read_usable_camera_frame(capture, timeout_seconds=1.25)
                if frame is None:
                    continue
                height, width = frame.shape[:2]
                discovered.append(
                    {
                        "camera_id": str(camera_index),
                        "label": f"Sewing camera {camera_index + 1} · {width} × {height}",
                        "width": int(width),
                        "height": int(height),
                    }
                )
            finally:
                capture.release()
        return discovered

    def test_camera(self, camera_id: str) -> dict[str, Any]:
        self._assert_not_running("Camera testing is unavailable while live monitoring is active.")
        camera_index = self._camera_index(camera_id)
        cv2 = get_opencv()
        frame: Any | None = None

        for attempt in range(2):
            capture = open_camera_capture(cv2, camera_index)
            try:
                if not capture.isOpened():
                    if attempt == 0:
                        time.sleep(0.35)
                        continue
                    raise RuntimeError(
                        "The selected sewing camera could not be opened. Close other camera "
                        "applications and check macOS camera permissions."
                    )

                frame = read_usable_camera_frame(capture)
                if frame is not None:
                    break
            finally:
                capture.release()

            if attempt == 0:
                time.sleep(0.35)

        if frame is None:
            raise RuntimeError(
                "The camera opened but did not deliver an image. Close FaceTime, Zoom, browser "
                "camera tabs, or Continuity Camera, then check macOS camera permissions and try again."
            )

        height, width = frame.shape[:2]
        detection: dict[str, Any] | None = None
        if self.registry.detector is not None:
            detection = self.registry.detector.detect(frame).to_dict()

        result = {
            "camera_id": camera_id,
            "camera_ready": True,
            "width": int(width),
            "height": int(height),
            "workstation_checked": detection is not None,
            "workstation_visible": bool(detection and detection["visible"]),
            "detection": detection,
            "tested_at": format_utc(utc_now()),
        }
        with self._lock:
            self._camera_preflight[camera_id] = result
        return result

    def start(self, session_id: int, source_type: str, video_path: str | None = None) -> dict[str, Any]:
        self._assert_not_running("Live monitoring is already active for a workstation session.")
        if not self.registry.ready or self.registry.detector is None or self.registry.classifier is None:
            raise RuntimeError("Both trained AI models must finish loading before live monitoring can start.")

        connection = connect(self.settings.database_path)
        try:
            session = connection.execute(
                "SELECT * FROM production_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            configuration = connection.execute(
                "SELECT * FROM device_configuration WHERE id = 1"
            ).fetchone()
            if session is None or session["status"] != "ACTIVE":
                raise RuntimeError("Live monitoring requires an active workstation session.")
            if configuration is None or not configuration["camera_tested"]:
                raise RuntimeError("Select and successfully test the sewing camera first.")
            if not configuration["iot_connected"] or not configuration["iot_notifications_active"]:
                raise RuntimeError("Connect the operator controller before starting live monitoring.")
            session_mode = str(session["session_mode"])
            camera_id = str(session["camera_id"])
        finally:
            connection.close()

        if source_type == "camera":
            source: int | str = self._camera_index(camera_id)
            source_label = f"Live sewing camera {source + 1}"
        elif source_type == "video":
            if not video_path:
                raise RuntimeError("Choose a recorded workstation video before starting the test workflow.")
            candidate = Path(video_path).expanduser().resolve()
            if not candidate.is_file():
                raise RuntimeError("The selected workstation test video could not be found.")
            source = str(candidate)
            source_label = candidate.name
        else:
            raise RuntimeError("Choose either the live sewing camera or a workstation test video.")

        cv2 = get_opencv()
        capture = open_camera_capture(cv2, source) if isinstance(source, int) else cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("The selected camera or workstation test video could not be opened.")

        self._stop.clear()
        self._preview_connected.clear()
        test_workflow = False
        with self._lock:
            self._session_id = session_id
            self._latest_jpeg = None
            self._status = {
                **self._initial_status(),
                "running": True,
                "phase": "STARTING",
                "session_id": session_id,
                "source_type": source_type,
                "source_label": source_label,
                "test_workflow": test_workflow,
                "counting_message": (
                    "Opening the recorded production test workflow — production counts will not change."
                    if test_workflow
                    else "Checking the workstation and collecting fresh camera frames…"
                ),
            }
        self._thread = threading.Thread(
            target=self._run,
            args=(capture, cv2, session_id, session_mode, source_type, test_workflow),
            name=f"garment-vision-session-{session_id}",
            daemon=True,
        )
        self._thread.start()
        return self.status(session_id)

    def stop(self, session_id: int | None = None) -> dict[str, Any]:
        if session_id is not None and self._session_id not in {None, session_id}:
            raise RuntimeError("The selected session does not own the running camera pipeline.")

        self._stop.set()
        self._preview_connected.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        with self._lock:
            self._status.update(
                running=False,
                phase="STOPPED",
                counting_permitted=False,
                counting_message="Live monitoring has stopped.",
                updated_at=format_utc(utc_now()),
            )
        return self.status(session_id)

    def stream(self, session_id: int) -> Iterator[bytes]:
        with self._lock:
            owns_running_video = (
                self._session_id == session_id
                and self._status["running"]
                and self._status["source_type"] == "video"
            )
        if owns_running_video:
            # A recorded workflow must not advance before its synchronized
            # preview has actually been requested by the desktop renderer.
            self._preview_connected.set()

        while not self._stop.is_set() and self._session_id == session_id:
            with self._lock:
                jpeg = self._latest_jpeg
            if jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(
                    len(jpeg)
                ).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            time.sleep(0.09)

    def _run(
        self,
        capture: Any,
        cv2: Any,
        session_id: int,
        session_mode: str,
        source_type: str,
        test_workflow: bool,
    ) -> None:
        workstation = WorkstationLatch(
            initial_detections=2,
            recheck_interval_seconds=WORKSTATION_RECHECK_INTERVAL_SECONDS,
            failed_recheck_limit=WORKSTATION_FAILED_RECHECK_LIMIT,
        )
        smoother = ProbabilitySmoother()
        decoder = GarmentCycleDecoder()
        frames: deque[tuple[float, Any]] = deque(maxlen=100)
        started_at = time.monotonic()
        started_utc = utc_now()
        last_prediction = 0.0
        processed = 0
        misses = 0
        source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
        source_fps = min(60.0, max(5.0, source_fps))

        try:
            if source_type == "video":
                self._update_status(
                    phase="STARTING",
                    counting_permitted=False,
                    counting_message="Preparing the synchronized workflow-video preview…",
                )
                while not self._stop.is_set() and not self._preview_connected.wait(0.1):
                    pass
                if self._stop.is_set():
                    return

            while not self._stop.is_set():
                tick = time.monotonic()
                success, frame = capture.read()
                if not success or frame is None:
                    if source_type == "video":
                        self._update_status(
                            phase="VIDEO_COMPLETE",
                            counting_permitted=False,
                            counting_message=(
                                "The production test workflow has finished. No production counts were changed."
                                if test_workflow
                                else "The validation video has finished."
                            ),
                        )
                        break
                    misses += 1
                    if misses >= 8:
                        self._reset_tracking(workstation, smoother, decoder, frames, session_id)
                        raise RuntimeError("The live sewing camera stopped delivering fresh images.")
                    self._stop.wait(0.08)
                    continue

                misses = 0
                now = time.monotonic()
                processed += 1
                frames.append((now, frame.copy()))

                if source_type == "video" and processed == 1:
                    # Publish the selected video's first usable frame before
                    # detector/classifier inference. This gives the operator
                    # immediate visual confirmation and guarantees that model
                    # processing never runs invisibly ahead of the preview.
                    encoded, jpeg = cv2.imencode(
                        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82]
                    )
                    if encoded:
                        with self._lock:
                            self._latest_jpeg = jpeg.tobytes()
                            self._status.update(
                                preview_ready=True,
                                updated_at=format_utc(utc_now()),
                            )

                if now - last_prediction >= PREDICTION_INTERVAL_SECONDS:
                    last_prediction = now
                    self._process_observation(
                        frame,
                        now,
                        started_at,
                        started_utc,
                        session_id,
                        session_mode,
                        test_workflow,
                        frames,
                        workstation,
                        smoother,
                        decoder,
                    )

                with self._lock:
                    status = dict(self._status)
                status["processing_fps"] = round(processed / max(0.01, now - started_at), 1)
                status["frames_processed"] = processed
                status["buffered_frames"] = len(frames)
                annotated = self._annotate(frame, status, cv2)
                encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
                with self._lock:
                    self._status.update(
                        processing_fps=status["processing_fps"],
                        frames_processed=processed,
                        buffered_frames=len(frames),
                        updated_at=format_utc(utc_now()),
                    )
                    if encoded:
                        self._latest_jpeg = jpeg.tobytes()
                        self._status["preview_ready"] = True

                if source_type == "video":
                    self._stop.wait(max(0.0, 1.0 / source_fps - (time.monotonic() - tick)))

        except Exception as error:
            self._update_status(
                phase="ERROR",
                last_error=str(error).splitlines()[0][:240],
                counting_permitted=False,
                counting_message="Live monitoring stopped because the camera pipeline needs attention.",
            )
        finally:
            capture.release()
            with self._lock:
                self._status["running"] = False
                if self._status["phase"] not in {"ERROR", "VIDEO_COMPLETE"}:
                    self._status["phase"] = "STOPPED"
                self._status["updated_at"] = format_utc(utc_now())
            self._stop.set()
            self._preview_connected.set()

    def _process_observation(
        self,
        frame: Any,
        now: float,
        anchor_monotonic: float,
        anchor_utc: Any,
        session_id: int,
        session_mode: str,
        test_workflow: bool,
        frames: deque[tuple[float, Any]],
        workstation: WorkstationLatch,
        smoother: ProbabilitySmoother,
        decoder: GarmentCycleDecoder,
    ) -> None:
        detector = self.registry.detector
        classifier = self.registry.classifier
        if detector is None or classifier is None:
            raise RuntimeError("A trained inference model became unavailable.")

        session_state = self._session_guard(session_id)

        if not session_state["permitted"]:
            self._reset_tracking(workstation, smoother, decoder, frames, session_id)
            self._update_status(
                phase="PAUSED",
                sewing_state="UNCERTAIN",
                workstation_confirmed=False,
                counting_permitted=False,
                counting_message=session_state["message"],
            )
            return

        if workstation.should_check(now):
            was_confirmed = workstation.confirmed
            detection = detector.detect(frame)
            confirmed = workstation.update(detection.visible, now)

            if detection.visible:
                self._update_status(
                    phase="MONITORING",
                    workstation_visible=True,
                    workstation_confirmed=confirmed,
                    workstation_confidence=round(detection.confidence, 4),
                    workstation_bbox=list(detection.bbox) if detection.bbox else None,
                    workstation_message=(
                        "The sewing workstation is latched and periodically verified."
                        if confirmed
                        else "Confirming the initial sewing workstation view…"
                    ),
                )
            elif was_confirmed and confirmed:
                self._update_status(
                    phase="MONITORING",
                    workstation_visible=True,
                    workstation_confirmed=True,
                    workstation_message=(
                        f"Periodic workstation check missed "
                        f"({workstation.failed_rechecks}/{workstation.failed_recheck_limit}). "
                        "Classification continues using the latched workstation."
                    ),
                )
            elif was_confirmed and not confirmed:
                self._reset_tracking(workstation, smoother, decoder, frames, session_id)
                decoder.require_idle_rearm()
                self._update_status(
                    sewing_state="INVALID_VIEW",
                    classification_confidence=0.0,
                    workstation_visible=False,
                    workstation_confirmed=False,
                    counting_permitted=False,
                    workstation_message="The workstation failed several scheduled verification checks.",
                    counting_message="Workstation verification expired. Detect the workstation again to resume.",
                )
                return
            else:
                self._update_status(
                    sewing_state="UNCERTAIN",
                    workstation_visible=False,
                    workstation_confirmed=False,
                    counting_permitted=False,
                    workstation_message="A sewing workstation must be detected before classification starts.",
                    counting_message="Detecting the initial sewing workstation…",
                )
                return

        if not workstation.confirmed:
            return

        clip = sample_clip(frames, now)
        if not clip:
            self._update_status(
                sewing_state="UNCERTAIN",
                counting_permitted=False,
                counting_message="Collecting eight fresh workstation frames…",
            )
            return

        prediction = classifier.predict(clip)
        stable_label, confidence = smoother.update(prediction["probabilities"])
        previous_phase = decoder.phase
        was_rearming = decoder.needs_idle_rearm
        garment = decoder.update(stable_label, now, confidence)
        if was_rearming or decoder.needs_idle_rearm:
            self._update_status(
                sewing_state=stable_label,
                classification_confidence=round(confidence, 4),
                counting_permitted=False,
                counting_message="Workstation restored. Waiting for a stable idle state before counting another garment.",
            )
            return
        self._update_status(
            sewing_state=stable_label,
            classification_confidence=round(confidence, 4),
            counting_permitted=not test_workflow,
            counting_message=(
                "Test workflow detected sewing — waiting for the test garment to finish."
                if test_workflow and stable_label == "SEWING"
                else "Test workflow is ready for the next garment. Production records will not change."
                if test_workflow and stable_label == "IDLE_SETUP"
                else "Test workflow is waiting for a confident sewing-state prediction."
                if test_workflow
                else "Sewing detected — waiting for the garment to finish."
                if stable_label == "SEWING"
                else "Workstation ready — waiting for the next sewing cycle."
                if stable_label == "IDLE_SETUP"
                else "Waiting for a confident sewing-state prediction."
            ),
        )

        if (
            not test_workflow
            and previous_phase != "SEWING_CONFIRMED"
            and decoder.phase == "SEWING_CONFIRMED"
        ):
            sewing_time = anchor_utc + timedelta(seconds=(decoder._sewing_started or now) - anchor_monotonic)
            self._record_sewing_start(session_id, sewing_time)

        if garment is None:
            return

        if test_workflow:
            self._update_status(
                counting_permitted=False,
                counting_message="Test garment recognized — the production count remains unchanged.",
            )
            return

        sewing_started = anchor_utc + timedelta(seconds=garment.sewing_started_at - anchor_monotonic)
        completed = anchor_utc + timedelta(seconds=garment.completed_at - anchor_monotonic)
        payload = PieceCreate(
            sewing_started_at=sewing_started,
            completed_at=completed,
            confidence=garment.confidence,
            event_source="VISION" if session_mode == "PRODUCTION" else "VALIDATION",
        )
        connection = connect(self.settings.database_path)
        try:
            try:
                event = persist_piece_event(connection, session_id, payload)
            except HTTPException:
                self._reset_tracking(workstation, smoother, decoder, frames, session_id)
                return
        finally:
            connection.close()
        self._update_status(last_event=event)

    def _session_guard(self, session_id: int) -> dict[str, Any]:
        connection = connect(self.settings.database_path)
        try:
            session = connection.execute(
                "SELECT status, operator_mode FROM production_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            configuration = connection.execute(
                "SELECT iot_connected, iot_notifications_active FROM device_configuration WHERE id = 1"
            ).fetchone()
        finally:
            connection.close()

        if session is None or session["status"] != "ACTIVE":
            raise RuntimeError("The production session is no longer active.")
        if configuration is None or not configuration["iot_connected"]:
            return {"permitted": False, "message": "Counting is paused because the controller is disconnected."}
        if not configuration["iot_notifications_active"]:
            return {"permitted": False, "message": "Counting is paused because controller notifications stopped."}
        if session["operator_mode"] != "NORMAL":
            return {
                "permitted": False,
                "message": f"Counting is paused while {str(session['operator_mode']).lower()} is active.",
            }
        return {"permitted": True, "message": "Counting is permitted."}

    def _record_sewing_start(self, session_id: int, started_at: Any) -> None:
        connection = connect(self.settings.database_path)
        try:
            with transaction(connection):
                connection.execute(
                    "UPDATE production_sessions SET first_sewing_started_at = "
                    "COALESCE(first_sewing_started_at, ?) WHERE id = ? AND status = 'ACTIVE'",
                    (format_utc(started_at), session_id),
                )
        finally:
            connection.close()

    def _reset_tracking(
        self,
        workstation: WorkstationLatch,
        smoother: ProbabilitySmoother,
        decoder: GarmentCycleDecoder,
        frames: deque[tuple[float, Any]],
        session_id: int,
    ) -> None:
        had_unfinished_cycle = decoder.phase == "SEWING_CONFIRMED"
        workstation.reset()
        smoother.reset()
        decoder.reset_cycle()
        frames.clear()
        if had_unfinished_cycle:
            connection = connect(self.settings.database_path)
            try:
                with transaction(connection):
                    connection.execute(
                        "UPDATE production_sessions SET first_sewing_started_at = NULL WHERE id = ?",
                        (session_id,),
                    )
            finally:
                connection.close()

    @staticmethod
    def _annotate(frame: Any, status: dict[str, Any], cv2: Any) -> Any:
        annotated = frame.copy()
        bbox = status.get("workstation_bbox")
        if bbox:
            x1, y1, x2, y2 = bbox
            color = (72, 180, 86) if status["workstation_visible"] else (28, 125, 222)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                f"WORKSTATION {status['workstation_confidence'] * 100:.0f}%",
                (x1, max(24, y1 - 9)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                color,
                2,
                cv2.LINE_AA,
            )
        label = str(status.get("sewing_state", "UNCERTAIN")).replace("_", " ")
        cv2.rectangle(annotated, (0, 0), (min(annotated.shape[1], 410), 48), (29, 35, 48), -1)
        cv2.putText(
            annotated,
            f"{label}  {status.get('classification_confidence', 0.0) * 100:.0f}%",
            (14, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (248, 250, 252),
            2,
            cv2.LINE_AA,
        )
        return annotated

    def _update_status(self, **changes: Any) -> None:
        with self._lock:
            self._status.update(changes, updated_at=format_utc(utc_now()))

    def _assert_not_running(self, message: str) -> None:
        thread = self._thread
        if thread and thread.is_alive() and not self._stop.is_set():
            raise RuntimeError(message)

    @staticmethod
    def _camera_index(camera_id: str) -> int:
        if not camera_id.isdigit():
            raise RuntimeError(
                "The saved camera uses an older browser identifier. Scan and test cameras again "
                "so the Python inference service receives the correct device index."
            )
        index = int(camera_id)
        if index < 0 or index >= MAX_CAMERA_INDEX:
            raise RuntimeError("The selected sewing-camera index is outside the supported range.")
        return index
