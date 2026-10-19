"""Live garment-style decision engine (version 3.2).

Why this module exists
----------------------
The supplied ThreadScan YOLO model (``models/garment-style-colour/best.pt``) was
trained on 3,033 catalogue-style photographs in which one garment fills almost
the whole image. It has no "nothing here" class, so whatever it is shown it
answers with one of SHIRT / SHORT / TROUSER / T_SHIRT. Measured on this
project's own data:

* a patch of the empty red packing table is reported as SHORT (86-94 %) and a
  plain red image as T_SHIRT (88 %); an empty wooden table as T_SHIRT (83 %);
* on a full camera frame it frequently draws its box around the whole frame,
  so the "garment crop" contained large areas of table;
* the previous loop captured on the first two sharp frames, while the garment
  was still being placed or smoothed by hand, and auto-unlocked after 90
  frames, so the same garment was captured again while it was being folded
  (a folded T-shirt or trouser looks like a dark rectangle -> SHORT/T_SHIRT).

The model itself is accurate (about 95 % on still, unobstructed, tightly
cropped garments from the live history). The errors came from *when* and *on
what pixels* it was asked. This engine therefore decides those two things
before the model is consulted:

1. Presence and localisation come from comparing the camera image with a
   learned picture of the empty folding zone (background model), not from the
   model, so an empty table can never be "detected".
2. Only a tight crop around the garment's own pixels is classified, at the
   model's training resolution (640 px).
3. Classification starts only when the garment is still and no hands/face are
   in or next to it.
4. Several frames vote; the style is accepted only when they agree with
   enough confidence and margin over the runner-up class.
5. After a capture the zone stays locked until it is genuinely empty, so
   folding the same garment never produces a second record.

The engine is pure logic (NumPy/OpenCV only). The camera loop in
``live_webcam_pipeline.py`` feeds it frames, and
``tools/replay_style_video.py`` feeds it recorded videos for evaluation.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

import cv2
import numpy as np


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class EngineConfig:
    """Tunable thresholds. Every value can be overridden with an environment
    variable (THREADSCAN_<NAME in upper case>) without touching code."""

    # Region of the camera frame treated as the folding zone (fractions).
    roi_margin: float = 0.03
    # Width (px) of the low-resolution copy used for background/motion maths.
    work_width: int = 192
    # Colour distance (CIE Lab, delta-E units) above which a pixel differs from
    # the empty-table picture. Lightness is down-weighted so shadows and webcam
    # auto-exposure are not mistaken for a garment.
    foreground_delta_e: float = 14.0
    lightness_weight: float = 0.6
    # A garment must cover at least this fraction of the folding zone.
    min_garment_fraction: float = 0.05
    # If almost the whole zone differs from the empty-table picture, the light
    # or camera position changed: the background is re-learned.
    global_change_fraction: float = 0.92
    # A pixel is "moving" if its brightness changed by more than
    # motion_pixel_delta since the previous frame OR since motion_window_seconds
    # ago (the longer comparison also catches slow movement). The garment is
    # still when at most still_motion_fraction of its box is moving.
    still_motion_fraction: float = 0.02
    motion_pixel_delta: float = 14.0
    motion_window_seconds: float = 0.4
    still_seconds: float = 0.3
    # Garment outline overlap (IoU) required with the previous frame and with
    # the outline motion_window_seconds ago for the garment to count as settled.
    outline_iou_frame: float = 0.85
    outline_iou_window: float = 0.75
    # Votes are kept through a brief wobble, but discarded once the garment's
    # outline differs this much from where voting started (it was moved,
    # folded or replaced).
    vote_reset_iou: float = 0.6
    # How long the empty zone must be still before it is learned as background.
    calibration_still_seconds: float = 1.0
    # How long the zone must be empty before the next garment is accepted.
    empty_seconds: float = 1.2
    # Skin-coloured foreground pixels (hands, arms, face) lying on or right
    # next to the garment, as a fraction of the garment's own area. Resting
    # hands at the edge are tolerated; a hand or face covering the garment
    # (which changes its apparent sleeve/leg length) blocks classification.
    hand_block_fraction: float = 0.06
    # Voting.
    vote_frames: int = 3
    vote_window: int = 7
    min_agreement: float = 0.8
    min_confidence: float = 0.60
    min_margin: float = 0.25
    uncertain_after_votes: int = 12
    # Padding added around the garment box before classification.
    crop_padding: float = 0.05
    # How long the "CAPTURED" state is shown before "WAITING_REMOVAL".
    captured_display_seconds: float = 1.5

    @classmethod
    def from_env(cls) -> "EngineConfig":
        config = cls()
        for name, value in vars(config).items():
            env_name = f"THREADSCAN_{name.upper()}"
            if env_name not in os.environ:
                continue
            if isinstance(value, int) and not isinstance(value, bool):
                setattr(config, name, _env_int(env_name, value))
            else:
                setattr(config, name, _env_float(env_name, value))
        return config


# ----------------------------------------------------------------- helpers --

def compute_roi(frame_w: int, frame_h: int, margin: float = 0.03) -> tuple[int, int, int, int]:
    """Folding-zone rectangle (x1, y1, x2, y2) inside a camera frame."""
    return (
        int(frame_w * margin),
        int(frame_h * margin),
        int(frame_w * (1.0 - margin)),
        int(frame_h * (1.0 - margin)),
    )


def skin_mask(bgr_image: np.ndarray) -> np.ndarray:
    """Rough skin-tone mask (Chai & Ngan YCrCb range). Wooden tables and beige
    fabric can fall inside this range too, so it is only ever combined with
    the background-difference mask - a skin-coloured pixel that is part of the
    empty table is not a hand. A minimum brightness (Y >= 70) is added because
    the blurred border between a dark garment and a red table, and shadows on
    a red table, are dark reds that otherwise fall in the same range."""
    ycrcb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2YCrCb)
    lower = np.array([70, 133, 77], dtype=np.uint8)
    upper = np.array([255, 173, 127], dtype=np.uint8)
    return cv2.inRange(ycrcb, lower, upper) > 0


def to_lab(bgr_small: np.ndarray) -> np.ndarray:
    """True-unit CIE Lab (L 0-100, a/b about -128..127) as float32."""
    return cv2.cvtColor(bgr_small.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)


def laplacian_sharpness(bgr_image: np.ndarray) -> float:
    if bgr_image is None or bgr_image.size == 0:
        return 0.0
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def _open(mask: np.ndarray, size: int) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)


class BackgroundModel:
    """A picture of the empty folding zone, in Lab, at low resolution."""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.reference: Optional[np.ndarray] = None

    @property
    def ready(self) -> bool:
        return self.reference is not None

    def clear(self) -> None:
        self.reference = None

    def set(self, lab: np.ndarray) -> None:
        self.reference = lab.copy()

    def difference(self, lab: np.ndarray) -> np.ndarray:
        """Per-pixel colour distance to the empty-table picture, with a global
        lightness offset removed (webcams re-expose when a dark or bright
        garment enters the frame, which shifts the whole table's brightness)."""
        ref = self.reference
        d_ab = np.sqrt((lab[..., 1] - ref[..., 1]) ** 2 + (lab[..., 2] - ref[..., 2]) ** 2)
        d_l = lab[..., 0] - ref[..., 0]
        table_like = d_ab < 6.0
        if table_like.mean() > 0.2:
            offset = float(np.median(d_l[table_like]))
        else:
            offset = float(np.median(d_l))
        weighted_l = self.config.lightness_weight * (d_l - offset)
        return np.sqrt(d_ab ** 2 + weighted_l ** 2)

    def foreground(self, lab: np.ndarray) -> np.ndarray:
        mask = (self.difference(lab) > self.config.foreground_delta_e).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        return mask.astype(bool)

    def table_colour(self, foreground: np.ndarray) -> np.ndarray:
        visible = ~foreground
        pixels = self.reference[visible] if visible.mean() > 0.1 else self.reference.reshape(-1, 3)
        return np.median(pixels, axis=0)

    def blend(self, lab: np.ndarray, alpha: float, where: Optional[np.ndarray] = None) -> None:
        """Slowly follow gradual lighting drift (only where nothing is lying)."""
        if where is None:
            self.reference = (1.0 - alpha) * self.reference + alpha * lab
        else:
            self.reference[where] = (1.0 - alpha) * self.reference[where] + alpha * lab[where]

    def absorb(self, lab: np.ndarray, region: np.ndarray) -> None:
        self.reference[region] = lab[region]


@dataclass
class Vote:
    scores: np.ndarray
    crop: np.ndarray
    mask: Optional[np.ndarray]
    sharpness: float

    @property
    def label_index(self) -> int:
        return int(np.argmax(self.scores))


@dataclass
class Capture:
    style: str
    confidence: float  # 0-1, mean winning-class score across the votes
    agreement: float  # 0-1, share of votes that chose the winning class
    image: np.ndarray  # untouched camera crop of the best voting frame
    mask: Optional[np.ndarray]  # garment pixels inside `image` (for colour)
    class_scores: dict = field(default_factory=dict)


@dataclass
class FrameResult:
    state: str
    detail: str
    style: Optional[str] = None
    confidence: Optional[float] = None  # percent
    progress: Optional[tuple[int, int]] = None
    box: Optional[tuple[int, int, int, int]] = None  # full-frame coordinates
    roi: Optional[tuple[int, int, int, int]] = None
    capture: Optional[Capture] = None
    calibrated: bool = False


Classifier = Callable[[np.ndarray], np.ndarray]


class StyleCaptureEngine:
    """Frame-by-frame state machine. Call :meth:`process` for every new camera
    frame with a monotonic timestamp in seconds."""

    def __init__(self, classify: Classifier, class_names: list[str], config: Optional[EngineConfig] = None):
        self.classify = classify
        self.class_names = [str(name).upper() for name in class_names]
        self.config = config or EngineConfig()
        self.background = BackgroundModel(self.config)
        self.reset()

    # ------------------------------------------------------------ control --

    def reset(self) -> None:
        """Forget everything, including the empty-table picture (used when the
        camera changes)."""
        self.background.clear()
        self._calibration_requested = True
        self._gray_history: deque[tuple[float, np.ndarray]] = deque(maxlen=64)
        self._outline_history: deque[tuple[float, np.ndarray]] = deque(maxlen=64)
        self._scene_still_since: Optional[float] = None
        self._garment_still_since: Optional[float] = None
        self._empty_since: Optional[float] = None
        self._locked = False
        self._captured_style: Optional[str] = None
        self._captured_confidence: Optional[float] = None
        self._captured_at: Optional[float] = None
        self._votes: deque[Vote] = deque(maxlen=self.config.vote_window)
        self._vote_anchor: Optional[np.ndarray] = None
        self._votes_since_ready = 0

    def request_calibration(self) -> None:
        """Re-learn the empty table on the next still moment (operator button,
        lighting change)."""
        self._calibration_requested = True

    @property
    def calibrated(self) -> bool:
        return self.background.ready and not self._calibration_requested

    @property
    def locked(self) -> bool:
        return self._locked

    # -------------------------------------------------------------- frame --

    def process(self, frame_bgr: np.ndarray, now: float) -> FrameResult:
        cfg = self.config
        frame_h, frame_w = frame_bgr.shape[:2]
        roi = compute_roi(frame_w, frame_h, cfg.roi_margin)
        rx1, ry1, rx2, ry2 = roi
        roi_bgr = frame_bgr[ry1:ry2, rx1:rx2]
        roi_h, roi_w = roi_bgr.shape[:2]

        scale = cfg.work_width / float(roi_w)
        small_w, small_h = cfg.work_width, max(8, int(round(roi_h * scale)))
        small = cv2.resize(roi_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (5, 5), 0)
        lab = to_lab(small)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)

        moving = self._motion_mask(gray, now)

        scene_motion = float(moving.mean())
        if scene_motion < cfg.still_motion_fraction:
            self._scene_still_since = self._scene_still_since if self._scene_still_since is not None else now
        else:
            self._scene_still_since = None
        scene_still_for = 0.0 if self._scene_still_since is None else now - self._scene_still_since

        # ---- calibration: learn the empty folding zone --------------------
        if self._calibration_requested or not self.background.ready:
            if scene_still_for >= cfg.calibration_still_seconds:
                self.background.set(lab)
                self._calibration_requested = False
                self._clear_garment_tracking()
                self._locked = False
                self._empty_since = now
                return FrameResult("EMPTY", "Folding zone learned - place a garment", roi=roi, calibrated=True)
            return FrameResult(
                "CALIBRATING",
                "Keep the folding zone empty and still",
                roi=roi,
                progress=(int(min(scene_still_for, cfg.calibration_still_seconds) * 10), int(cfg.calibration_still_seconds * 10)),
            )

        foreground = self.background.foreground(lab)
        foreground_fraction = float(foreground.mean())

        if foreground_fraction >= cfg.global_change_fraction:
            # Lighting or camera position changed: re-learn once still again.
            self.request_calibration()
            return FrameResult("CALIBRATING", "Lighting changed - keep the zone empty", roi=roi)

        skin = skin_mask(small)
        hands = self._hand_pixels(skin & foreground)
        # Anything substantial that differs from the empty table means the
        # zone is occupied (a garment, possibly still moving).
        occupied_mask = _open(foreground & ~hands, 5)
        occupant, _ = self._pick_garment_component(occupied_mask)

        if occupant is not None and self._is_ghost(lab, occupant, foreground):
            # Something that was lying on the table when the background was
            # learned has been removed: the table is visible again there.
            self.background.absorb(lab, cv2.dilate(occupant.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool))
            occupant = None

        # ---- nothing on the table -----------------------------------------
        if occupant is None:
            self._clear_garment_tracking()
            if self._empty_since is None:
                self._empty_since = now
            empty_for = now - self._empty_since
            if empty_for >= cfg.empty_seconds:
                self._locked = False
                self._captured_style = None
                self._captured_confidence = None
                if scene_still_for >= 1.0 and foreground_fraction < 0.03:
                    self.background.blend(lab, 0.05, ~cv2.dilate(foreground.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool))
                return FrameResult("EMPTY", "Waiting for garment", roi=roi, calibrated=True)
            if self._locked:
                return self._locked_result(roi, None, now, "Garment removed?")
            return FrameResult("EMPTY", "Waiting for garment", roi=roi, calibrated=True)

        self._empty_since = None
        inv = 1.0 / scale

        def to_full(box):
            bx1, by1, bx2, by2 = box
            return (rx1 + int(bx1 * inv), ry1 + int(by1 * inv), rx1 + int(np.ceil(bx2 * inv)), ry1 + int(np.ceil(by2 * inv)))

        # The garment itself is the part of the occupied area that is NOT
        # moving: a reaching arm, the operator's body at the table edge or a
        # garment being shaken out are excluded automatically, so they can
        # neither stretch the crop nor be classified as clothing.
        moving_wide = cv2.dilate(moving.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        component, component_box = self._pick_garment_component(_open(foreground & ~hands & ~moving_wide, 5))

        if self._locked:
            self._votes.clear()
            return self._locked_result(roi, to_full(component_box) if component_box else None, now)

        if component is None:
            self._clear_garment_tracking()
            return FrameResult("DETECTING", "Garment moving - hold still", roi=roi, calibrated=True)

        sx1, sy1, sx2, sy2 = component_box
        box_full = to_full(component_box)

        # ---- gates: hands/face, stillness -----------------------------------
        reach = max(3, int(0.05 * max(sx2 - sx1, sy2 - sy1)))
        near_garment = cv2.dilate(
            component.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach + 1, 2 * reach + 1))
        ).astype(bool)
        garment_pixels = max(1, int(component.sum()))
        hand_pixels = int((hands & near_garment).sum())
        # A beige/tan garment is itself "skin coloured"; then the skin mask
        # describes the garment, not a hand, and must not block it.
        skin_coloured_garment = int((skin & component).sum()) > 0.5 * garment_pixels
        hands_present = (not skin_coloured_garment) and hand_pixels > cfg.hand_block_fraction * garment_pixels

        # The garment is settled when its own outline stops changing: an arm
        # sweeping over it, smoothing, shaking or folding all change the
        # outline, while hands resting at its edge or the operator moving
        # elsewhere do not.
        if self._vote_anchor is not None and _iou(component, self._vote_anchor) < cfg.vote_reset_iou:
            self._votes.clear()
            self._votes_since_ready = 0
            self._vote_anchor = None
        if self._outline_is_stable(component, now):
            self._garment_still_since = self._garment_still_since if self._garment_still_since is not None else now
        else:
            self._garment_still_since = None
        still_for = 0.0 if self._garment_still_since is None else now - self._garment_still_since

        if hands_present:
            return FrameResult("DETECTING", "Hands in the zone - release the garment", box=box_full, roi=roi, calibrated=True)
        if still_for < cfg.still_seconds:
            return FrameResult("DETECTING", "Garment moving - hold still", box=box_full, roi=roi, calibrated=True)

        # ---- classify a tight crop and vote -------------------------------
        crop, crop_mask = self._crop(roi_bgr, component, component_box, inv)
        scores = np.asarray(self.classify(crop), dtype=np.float32).reshape(-1)
        if scores.size != len(self.class_names):
            raise ValueError("Classifier returned a score vector of the wrong length.")
        self._votes.append(Vote(scores=scores, crop=crop, mask=crop_mask, sharpness=laplacian_sharpness(crop)))
        self._votes_since_ready += 1
        if self._vote_anchor is None:
            self._vote_anchor = component

        decision = self._decide()
        leader, leader_conf, agreement, margin = decision
        if (
            len(self._votes) >= cfg.vote_frames
            and agreement >= cfg.min_agreement
            and leader_conf >= cfg.min_confidence
            and margin >= cfg.min_margin
        ):
            capture = self._make_capture(leader, leader_conf, agreement)
            self._locked = True
            self._captured_style = capture.style
            self._captured_confidence = round(capture.confidence * 100, 2)
            self._captured_at = now
            self._votes.clear()
            self._votes_since_ready = 0
            self._vote_anchor = None
            return FrameResult(
                "CAPTURED",
                f"Captured {capture.style} ({self._captured_confidence}%)",
                style=capture.style,
                confidence=self._captured_confidence,
                box=box_full,
                roi=roi,
                capture=capture,
                calibrated=True,
            )

        leader_name = self.class_names[leader]
        if self._votes_since_ready >= cfg.uncertain_after_votes:
            return FrameResult(
                "UNCERTAIN",
                "Style unclear - spread the garment flat",
                style=leader_name,
                confidence=round(leader_conf * 100, 2),
                box=box_full,
                roi=roi,
                calibrated=True,
            )
        return FrameResult(
            "ANALYSING",
            f"Analysing {min(len(self._votes), cfg.vote_frames)}/{cfg.vote_frames}",
            style=leader_name,
            confidence=round(leader_conf * 100, 2),
            progress=(min(len(self._votes), cfg.vote_frames), cfg.vote_frames),
            box=box_full,
            roi=roi,
            calibrated=True,
        )

    # ---------------------------------------------------------- internals --

    def _clear_garment_tracking(self) -> None:
        self._garment_still_since = None
        self._outline_history.clear()
        self._vote_anchor = None
        self._votes.clear()
        self._votes_since_ready = 0

    def _locked_result(self, roi, box, now: float, detail: Optional[str] = None) -> FrameResult:
        just_captured = self._captured_at is not None and now - self._captured_at < self.config.captured_display_seconds
        return FrameResult(
            "CAPTURED" if just_captured else "WAITING_REMOVAL",
            detail or "Captured - fold and remove the garment",
            style=self._captured_style,
            confidence=self._captured_confidence,
            box=box,
            roi=roi,
            calibrated=True,
        )

    def _outline_is_stable(self, component: np.ndarray, now: float) -> bool:
        cfg = self.config
        history = self._outline_history
        if history and history[-1][1].shape != component.shape:
            history.clear()
        previous = history[-1][1] if history else None
        older = None
        for stamp, mask in history:
            if now - stamp < cfg.motion_window_seconds:
                break
            older = mask
        history.append((now, component))
        while len(history) > 2 and now - history[1][0] > cfg.motion_window_seconds:
            history.popleft()
        if previous is None or older is None:
            return False
        return _iou(component, previous) >= cfg.outline_iou_frame and _iou(component, older) >= cfg.outline_iou_window

    def _motion_mask(self, gray: np.ndarray, now: float) -> np.ndarray:
        cfg = self.config
        history = self._gray_history
        if history and history[-1][1].shape != gray.shape:
            history.clear()
        if not history:
            history.append((now, gray))
            return np.ones(gray.shape, dtype=bool)
        moving = np.abs(gray - history[-1][1]) > cfg.motion_pixel_delta
        older = None
        for stamp, frame in history:
            if now - stamp <= cfg.motion_window_seconds:
                break
            older = frame
        if older is None:
            older = history[0][1]
        moving |= np.abs(gray - older) > cfg.motion_pixel_delta
        history.append((now, gray))
        while len(history) > 2 and now - history[1][0] > cfg.motion_window_seconds:
            history.popleft()
        return moving

    def _hand_pixels(self, skin_foreground: np.ndarray) -> np.ndarray:
        """Skin-coloured foreground, minus any blob too large to be a hand or
        forearm - that is a beige/tan garment, which must stay a garment."""
        h, w = skin_foreground.shape
        # Hands are blobs; thin rings of mixed colour along garment edges are not.
        skin_foreground = _open(skin_foreground, 5)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(skin_foreground.astype(np.uint8), connectivity=8)
        hands = skin_foreground.copy()
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_AREA] >= 0.12 * h * w:
                hands[labels == label] = False
        return hands

    def _pick_garment_component(self, foreground: np.ndarray):
        cfg = self.config
        h, w = foreground.shape
        count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground.astype(np.uint8), connectivity=8)
        min_area = cfg.min_garment_fraction * h * w
        best_label, best_score = None, 0.0
        for label in range(1, count):
            x, y, bw, bh, area = stats[label]
            if area < min_area:
                continue
            touches = int(x <= 0) + int(y <= 0) + int(x + bw >= w) + int(y + bh >= h)
            # The operator's body entering from an edge is foreground too; a
            # garment laid on the table rarely touches the zone border, so a
            # border-touching blob only wins when it is clearly the largest.
            score = float(area) * (1.0 if touches == 0 else 0.55 if touches == 1 else 0.3)
            if score > best_score:
                best_label, best_score = label, score
        if best_label is None:
            return None, None
        x, y, bw, bh, _ = stats[best_label]
        return labels == best_label, (int(x), int(y), int(x + bw), int(y + bh))

    def _is_ghost(self, lab: np.ndarray, component: np.ndarray, foreground: np.ndarray) -> bool:
        """True when the 'object' is really the bare table showing through
        where something used to lie while the background was learned."""
        table = self.background.table_colour(foreground)
        now_mean = lab[component].mean(axis=0)
        ref_mean = self.background.reference[component].mean(axis=0)
        now_to_table = float(np.linalg.norm(now_mean - table))
        ref_to_table = float(np.linalg.norm(ref_mean - table))
        return now_to_table < 10.0 and ref_to_table > 18.0

    def _crop(self, roi_bgr: np.ndarray, component: np.ndarray, box, inv: float):
        cfg = self.config
        sx1, sy1, sx2, sy2 = box
        roi_h, roi_w = roi_bgr.shape[:2]
        x1, y1 = sx1 * inv, sy1 * inv
        x2, y2 = sx2 * inv, sy2 * inv
        pad_x, pad_y = (x2 - x1) * cfg.crop_padding, (y2 - y1) * cfg.crop_padding
        cx1, cy1 = max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y))
        cx2, cy2 = min(roi_w, int(np.ceil(x2 + pad_x))), min(roi_h, int(np.ceil(y2 + pad_y)))
        crop = roi_bgr[cy1:cy2, cx1:cx2].copy()
        mask_full = cv2.resize(component.astype(np.uint8), (roi_w, roi_h), interpolation=cv2.INTER_NEAREST)
        crop_mask = mask_full[cy1:cy2, cx1:cx2].astype(bool)
        return crop, crop_mask

    def _decide(self):
        votes = list(self._votes)
        stacked = np.stack([vote.scores for vote in votes])
        mean_scores = stacked.mean(axis=0)
        leader = int(np.argmax(mean_scores))
        ordered = np.sort(mean_scores)
        runner_up = float(ordered[-2]) if ordered.size > 1 else 0.0
        leader_conf = float(mean_scores[leader])
        agreement = float(np.mean([vote.label_index == leader for vote in votes]))
        return leader, leader_conf, agreement, leader_conf - runner_up

    def _make_capture(self, leader: int, leader_conf: float, agreement: float) -> Capture:
        candidates = [vote for vote in self._votes if vote.label_index == leader]
        best = max(candidates, key=lambda vote: (round(float(vote.scores[leader]), 2), vote.sharpness))
        mean_scores = np.stack([vote.scores for vote in self._votes]).mean(axis=0)
        return Capture(
            style=self.class_names[leader],
            confidence=leader_conf,
            agreement=agreement,
            image=best.crop,
            mask=best.mask,
            class_scores={name: round(float(score) * 100, 2) for name, score in zip(self.class_names, mean_scores)},
        )


class YoloStyleClassifier:
    """Turns an Ultralytics detection model into a per-class score vector for
    one garment crop: for each class, the highest box confidence the model
    reports for it (non-agnostic NMS keeps one box per class, so a SHIRT box
    and a T_SHIRT box for the same garment both contribute)."""

    def __init__(self, model, imgsz: int = 640, min_score: float = 0.05):
        self.model = model
        self.imgsz = imgsz
        self.min_score = min_score
        names = model.names
        self.class_names = [names[index] for index in sorted(names)] if isinstance(names, dict) else list(names)

    def __call__(self, crop_bgr: np.ndarray) -> np.ndarray:
        scores = np.zeros(len(self.class_names), dtype=np.float32)
        if crop_bgr is None or crop_bgr.size == 0:
            return scores
        result = self.model(crop_bgr, verbose=False, imgsz=self.imgsz, conf=self.min_score)[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return scores
        for class_id, confidence in zip(boxes.cls.tolist(), boxes.conf.tolist()):
            index = int(class_id)
            scores[index] = max(scores[index], float(confidence))
        return scores
