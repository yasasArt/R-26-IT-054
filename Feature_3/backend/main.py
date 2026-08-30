import base64
import json
import math
import os
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import torch

#adding database imports add parth
from database import (
    DATABASE_PATH,
    delete_production_order,
    get_all_measurements,
    get_current_session_data,
    get_production_orders,
    initialize_database,
    save_production_order,
    save_garment_measurement,
    start_new_session,
)

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from ultralytics import YOLO


# ==================================================
# Paths and configuration
# ==================================================

BACKEND_DIRECTORY = (
    Path(__file__).resolve().parent
)

PROJECT_ROOT = (
    BACKEND_DIRECTORY.parent
)

TRAINING_RESULTS = (
    PROJECT_ROOT
    / "training_results"
)

EXPERIMENT_RESULTS = (
    PROJECT_ROOT
    / "experiment_results"
)

SIZE_CHART_PATH = (
    BACKEND_DIRECTORY
    / "size_chart.json"
)

CALIBRATION_PATH = (
    BACKEND_DIRECTORY
    / "calibration.json"
)

# Runtime is marker-free.  The scale is measured once at the fixed 100 cm
# installation height and stored in calibration.json.  9.15 px/cm is only the
# initial value observed in the user's earlier 1920x1080 calibration; run
# calibrate_scale.py once on the final installation before collecting results.
CAMERA_HEIGHT_CM = 100.0

# A low inference threshold helps dark garments reach the validation stage.
# A result is never counted from confidence alone; geometry and temporal
# consistency are checked below.
INFERENCE_CONFIDENCE = 0.25
MINIMUM_CONFIDENCE = 0.60
SHIRT_INFERENCE_CONFIDENCE = 0.15
SHIRT_MINIMUM_CONFIDENCE = 0.38
MINIMUM_MASK_AREA_RATIO = 0.04
MAXIMUM_MASK_AREA_RATIO = 0.50

INFERENCE_IMAGE_SIZE = 640

# Automatic garment lifecycle settings. At a 200 ms frontend scan interval,
# three stable frames confirm a measurement. Three consecutive model-confirmed
# removal frames re-arm the next item, including another garment with exactly
# the same type, colour and size.
STABLE_FRAMES_REQUIRED = 3
SHIRT_STABLE_FRAMES_REQUIRED = 3
EMPTY_FRAMES_TO_REARM = 3
MAX_STABLE_WIDTH_CHANGE_CM = 1.5
MAX_STABLE_LENGTH_CHANGE_CM = 2.0

# A YOLO miss is not proof that the garment was removed. The current camera
# scene must also be visibly different from the scene that was counted.
# This prevents one stationary garment being counted again after temporary
# segmentation failures.
MINIMUM_REMOVAL_SCENE_DIFFERENCE = 0.025

# These margins are used only to reject obviously incomplete T-shirt masks.
# The actual size label is still obtained from size_chart.json.
TSHIRT_EXTRA_WIDTH_MARGIN_CM = 10.0
TSHIRT_EXTRA_LENGTH_MARGIN_CM = 15.0
# The garment is automatically deskewed, so a complete T-shirt may still
# look wider/shorter than the catalogue reference because of sleeves,
# relaxed-fit cuts and perspective. Keep this as an extreme-fragment guard,
# not as a strict fashion-size rule.
TSHIRT_MIN_WIDTH_LENGTH_RATIO = 0.35
TSHIRT_MAX_WIDTH_LENGTH_RATIO = 1.10

ROI_MARGIN_X = 0.04
ROI_MARGIN_Y = 0.04

SIZE_DISTANCE_LIMIT_CM = 8.0

ALLOWED_GARMENT_TYPES = {
    "tshirt",
    "shirt",
    "trouser",
}

MAX_UPLOAD_SIZE = (
    10 * 1024 * 1024
)


# ==================================================
# Load size chart
# ==================================================

def load_size_chart() -> dict:
    if not SIZE_CHART_PATH.exists():
        raise FileNotFoundError(
            f"Size chart not found:\n"
            f"{SIZE_CHART_PATH}"
        )

    with SIZE_CHART_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


SIZE_CHART = load_size_chart()


def load_calibration() -> dict:
    if not CALIBRATION_PATH.exists():
        raise FileNotFoundError(
            f"Calibration file not found:\n{CALIBRATION_PATH}\n"
            "Run: python calibrate_scale.py"
        )

    with CALIBRATION_PATH.open("r", encoding="utf-8") as file:
        calibration = json.load(file)

    required = {"pixels_per_cm", "frame_width", "frame_height"}
    missing = required.difference(calibration)
    if missing:
        raise ValueError(
            "calibration.json is missing: " + ", ".join(sorted(missing))
        )

    if float(calibration["pixels_per_cm"]) <= 0:
        raise ValueError("pixels_per_cm must be greater than zero.")

    return calibration


CALIBRATION = load_calibration()


# ==================================================
# Automatic counting and lifecycle state
# ==================================================

COUNTED_SIZES = (
    "XS",
    "S",
    "M",
    "L",
    "XL",
    "XXL",
    "3XL",
    "UNKNOWN",
)


def empty_count_table() -> dict:
    return {
        garment_type: {
            size: 0
            for size in COUNTED_SIZES
        }
        for garment_type in sorted(
            ALLOWED_GARMENT_TYPES
        )
    }


TRACKER_LOCK = Lock()

TRACKER = {
    "tracking_state": "EMPTY",
    "stable_samples": deque(
        maxlen=max(
            STABLE_FRAMES_REQUIRED,
            SHIRT_STABLE_FRAMES_REQUIRED,
        )
    ),
    "empty_frames": 0,
    "current_garment_counted": False,
    "last_counted_scene_signature": None,
    "counts": empty_count_table(),
    "history": deque(maxlen=50),
}


# Create the SQLite tables when the backend starts. If a current counting
# session already exists, restore its totals and recent history so a backend
# restart does not erase the dashboard data.
initialize_database()


def restore_tracker_from_database() -> None:
    saved_data = get_current_session_data(
        history_limit=50,
    )

    TRACKER["counts"] = saved_data["counts"]
    TRACKER["history"].clear()

    # Database history is newest-first. appendleft() also inserts at the
    # newest position, therefore restore from oldest to newest.
    for record in reversed(saved_data["history"]):
        TRACKER["history"].appendleft(record)


restore_tracker_from_database()


def calculate_scene_signature(image: np.ndarray) -> dict:
    """Create a small colour-and-edge signature for removal verification."""

    small_image = cv2.resize(
        image,
        (64, 36),
        interpolation=cv2.INTER_AREA,
    )
    small_image = cv2.GaussianBlur(
        small_image,
        (5, 5),
        0,
    )
    colour = small_image.astype(np.float32) / 255.0

    gray = cv2.cvtColor(small_image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150).astype(np.float32) / 255.0

    return {
        "colour": colour,
        "edges": edges,
    }


def scene_signature_difference(
    first_signature: dict | None,
    second_signature: dict | None,
) -> float:
    """Return 0 for the same scene and a larger value for a changed scene."""

    if first_signature is None or second_signature is None:
        return 0.0

    colour_difference = float(
        np.mean(
            np.abs(
                first_signature["colour"]
                - second_signature["colour"]
            )
        )
    )
    edge_difference = float(
        np.mean(
            np.abs(
                first_signature["edges"]
                - second_signature["edges"]
            )
        )
    )

    return colour_difference * 0.70 + edge_difference * 0.30


def stable_frames_required_for(garment_type: str | None) -> int:
    """Use a longer stability window for closely spaced shirt sizes."""
    return (
        SHIRT_STABLE_FRAMES_REQUIRED
        if garment_type == "shirt"
        else STABLE_FRAMES_REQUIRED
    )


def tracker_snapshot(
    *,
    counted_now: bool = False,
) -> dict:
    counts = {
        garment: dict(size_counts)
        for garment, size_counts
        in TRACKER["counts"].items()
    }

    total_count = sum(
        count
        for size_counts in counts.values()
        for count in size_counts.values()
    )

    display_measurement = None

    if (
        TRACKER["current_garment_counted"]
        and TRACKER["history"]
    ):
        latest_record = TRACKER["history"][0]
        display_measurement = {
            "garment_type": latest_record["garment_type"],
            "size": latest_record["size"],
            "width_cm": float(latest_record["width_cm"]),
            "length_cm": float(latest_record["length_cm"]),
            "confidence": float(latest_record["confidence"]),
        }
    elif TRACKER["stable_samples"]:
        samples = list(TRACKER["stable_samples"])
        median_width = float(
            np.median([sample["width_cm"] for sample in samples])
        )
        median_length = float(
            np.median([sample["length_cm"] for sample in samples])
        )
        median_confidence = float(
            np.median([sample["confidence"] for sample in samples])
        )
        median_size, _ = classify_size(
            samples[-1]["garment_type"],
            median_width,
            median_length,
        )
        display_measurement = {
            "garment_type": samples[-1]["garment_type"],
            "size": median_size,
            "width_cm": median_width,
            "length_cm": median_length,
            "confidence": median_confidence,
        }

    return {
        "tracking_state": (
            TRACKER["tracking_state"]
        ),
        "stable_count": len(
            TRACKER["stable_samples"]
        ),
        "stable_required": stable_frames_required_for(
            (
                TRACKER["stable_samples"][-1]["garment_type"]
                if TRACKER["stable_samples"]
                else (
                    TRACKER["history"][0]["garment_type"]
                    if TRACKER["current_garment_counted"] and TRACKER["history"]
                    else None
                )
            )
        ),
        "counted_now": counted_now,
        "ready_for_next_garment": not (
            TRACKER[
                "current_garment_counted"
            ]
        ),
        "counts": counts,
        "total_count": total_count,
        "recent_history": list(
            TRACKER["history"]
        )[:10],
        "display_measurement": display_measurement,
    }


def update_tracker_non_ready(
    state: str,
    scene_signature: dict | None = None,
) -> dict:
    """Update lifecycle for an invalid or empty camera frame."""
    with TRACKER_LOCK:
        TRACKER["stable_samples"].clear()

        if state == "NO_GARMENT":
            if TRACKER["current_garment_counted"]:
                removal_difference = scene_signature_difference(
                    TRACKER["last_counted_scene_signature"],
                    scene_signature,
                )
                removal_confirmed = (
                    removal_difference
                    >= MINIMUM_REMOVAL_SCENE_DIFFERENCE
                )

                # A YOLO miss alone cannot re-arm the tracker. The scene must
                # be sufficiently different from the frame that was counted.
                if not removal_confirmed:
                    TRACKER["empty_frames"] = 0
                    TRACKER["tracking_state"] = "WAIT_REMOVAL"
                    return tracker_snapshot()

            TRACKER["empty_frames"] += 1

            if (
                TRACKER["empty_frames"]
                >= EMPTY_FRAMES_TO_REARM
            ):
                TRACKER[
                    "current_garment_counted"
                ] = False
                TRACKER[
                    "tracking_state"
                ] = "EMPTY"
                TRACKER[
                    "last_counted_scene_signature"
                ] = None
            elif TRACKER[
                "current_garment_counted"
            ]:
                TRACKER[
                    "tracking_state"
                ] = "WAIT_REMOVAL"
            else:
                TRACKER[
                    "tracking_state"
                ] = "EMPTY"
        else:
            # Marker/partial/low-confidence frames do not prove that the
            # previous garment was removed, so they never re-arm counting.
            TRACKER["empty_frames"] = 0

            if TRACKER[
                "current_garment_counted"
            ]:
                TRACKER[
                    "tracking_state"
                ] = "WAIT_REMOVAL"
            else:
                TRACKER[
                    "tracking_state"
                ] = state

        return tracker_snapshot()


def stable_samples_are_consistent(
    previous: dict,
    current: dict,
) -> bool:
    width_limit = (
        2.5
        if current["garment_type"] == "shirt"
        else MAX_STABLE_WIDTH_CHANGE_CM
    )
    length_limit = (
        3.0
        if current["garment_type"] == "shirt"
        else MAX_STABLE_LENGTH_CHANGE_CM
    )

    return (
        previous["garment_type"]
        == current["garment_type"]
        and abs(
            previous["width_cm"]
            - current["width_cm"]
        ) <= width_limit
        and abs(
            previous["length_cm"]
            - current["length_cm"]
        ) <= length_limit
    )


def update_tracker_ready(
    *,
    garment_type: str,
    size: str,
    width_cm: float,
    length_cm: float,
    confidence: float,
    scene_signature: dict | None = None,
) -> dict:
    """Count one garment after stable measurements and removal."""

    current_sample = {
        "garment_type": garment_type,
        "size": size,
        "width_cm": float(width_cm),
        "length_cm": float(length_cm),
        "confidence": float(confidence),
    }

    with TRACKER_LOCK:
        # UNKNOWN results production count එකට එකතු නොකරයි.
        if size not in COUNTED_SIZES or size in {
            "UNKNOWN",
            "REFERENCE_REQUIRED",
        }:
            TRACKER["stable_samples"].clear()
            TRACKER["empty_frames"] = 0
            TRACKER["tracking_state"] = "SIZE_UNKNOWN"

            return tracker_snapshot()

        TRACKER["empty_frames"] = 0

        # කලින් garment එක count කරලා නම් remove කරන තුරු wait කරන්න.
        if TRACKER["current_garment_counted"]:
            TRACKER["tracking_state"] = "WAIT_REMOVAL"

            return tracker_snapshot()

        samples = TRACKER["stable_samples"]

        # Measurements අතර වෙනස වැඩි නම් නැවත stabilizing පටන්ගන්න.
        if samples and not stable_samples_are_consistent(
            samples[-1],
            current_sample,
        ):
            samples.clear()

        samples.append(current_sample)
        TRACKER["tracking_state"] = "STABILIZING"

        required_samples = stable_frames_required_for(
            garment_type,
        )

        if len(samples) < required_samples:
            return tracker_snapshot()

        widths = [
            sample["width_cm"]
            for sample in samples
        ]

        lengths = [
            sample["length_cm"]
            for sample in samples
        ]

        confidences = [
            sample["confidence"]
            for sample in samples
        ]

        final_width = float(np.median(widths))
        final_length = float(np.median(lengths))
        final_confidence = float(np.median(confidences))

        # Reclassify from the robust median dimensions instead of trusting
        # only the final frame in the stable sequence.
        count_size, _ = classify_size(
            garment_type,
            final_width,
            final_length,
        )

        if count_size not in COUNTED_SIZES or count_size in {
            "UNKNOWN",
            "REFERENCE_REQUIRED",
        }:
            TRACKER["stable_samples"].clear()
            TRACKER["tracking_state"] = "SIZE_UNKNOWN"
            return tracker_snapshot()

        # Persist first. The in-memory count is changed only after SQLite
        # commits successfully, preventing the UI and database from diverging.
        record = save_garment_measurement(
            garment_type=garment_type,
            size=count_size,
            width_cm=final_width,
            length_cm=final_length,
            confidence=final_confidence,
        )

        TRACKER["counts"][garment_type][count_size] += 1
        TRACKER["history"].appendleft(record)
        TRACKER["current_garment_counted"] = True
        TRACKER["last_counted_scene_signature"] = scene_signature
        TRACKER["tracking_state"] = "COUNTED"

        return tracker_snapshot(counted_now=True)
     

# ==================================================
# Find latest YOLO model
# ==================================================

def find_latest_model() -> Path:
    configured_model = os.getenv("GARMENT_MODEL_PATH")
    if configured_model:
        configured_path = Path(configured_model).expanduser().resolve()
        if not configured_path.exists():
            raise FileNotFoundError(
                f"GARMENT_MODEL_PATH does not exist: {configured_path}"
            )
        return configured_path

    # The repository and packaged desktop app keep the uploaded model in
    # resources/models. This relative path works on Windows, macOS and Linux.
    resource_model = (
        BACKEND_DIRECTORY.parent
        / "resources"
        / "models"
        / "best_model.pt"
    )
    if resource_model.exists():
        return resource_model

    # Backward-compatible model location used by older ThreadScan builds.
    bundled_model = (
        BACKEND_DIRECTORY
        / "models"
        / "best.pt"
    )
    if bundled_model.exists():
        return bundled_model

    preferred_v5_model = (
        EXPERIMENT_RESULTS
        / "garment_seg_100cm_clean_v5"
        / "train"
        / "weights"
        / "best.pt"
    )
    if preferred_v5_model.exists():
        return preferred_v5_model

    legacy_model = (
        TRAINING_RESULTS
        / "garment_seg_v2_100cm-2"
        / "weights"
        / "best.pt"
    )
    if legacy_model.exists():
        return legacy_model

    model_files = (
        list(EXPERIMENT_RESULTS.rglob("best.pt"))
        + list(TRAINING_RESULTS.rglob("best.pt"))
    )

    if not model_files:
        raise FileNotFoundError(
            "No best.pt model was found inside "
            "experiment_results or training_results."
        )

    return max(
        model_files,
        key=lambda path: path.stat().st_mtime,
    )


MODEL_PATH = find_latest_model()


# ==================================================
# Select GPU or CPU
# ==================================================

if torch.cuda.is_available():
    DEVICE = 0
    DEVICE_NAME = (
        torch.cuda.get_device_name(0)
    )
else:
    DEVICE = "cpu"
    DEVICE_NAME = "CPU"


print("=" * 65)
print("Garment Measurement Backend")
print("=" * 65)
print(f"Model: {MODEL_PATH}")
print(f"Device: {DEVICE_NAME}")
print(
    f"Fixed camera height: "
    f"{CAMERA_HEIGHT_CM:.0f} cm"
)
print(
    "Calibration: "
    f"{float(CALIBRATION['pixels_per_cm']):.4f} px/cm at "
    f"{int(CALIBRATION['frame_width'])}x"
    f"{int(CALIBRATION['frame_height'])}"
)
print("Loading YOLO model...")

model = YOLO(str(MODEL_PATH))

print("YOLO model loaded successfully.")
print("=" * 65)


# ==================================================
# FastAPI
# ==================================================

app = FastAPI(
    title="Garment Measurement API",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    # Backend එක 127.0.0.1 local interface එකේ පමණක් run වෙන නිසා
    # Electron, localhost සහ static production frontend requests allow කරයි.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warm_up_model():
    """Remove the long delay from the first real camera request."""
    dummy_image = np.zeros(
        (640, 640, 3),
        dtype=np.uint8,
    )

    try:
        model.predict(
            source=dummy_image,
            imgsz=640,
            conf=INFERENCE_CONFIDENCE,
            iou=0.45,
            max_det=3,
            agnostic_nms=True,
            device=DEVICE,
            half=torch.cuda.is_available(),
            verbose=False,
        )
        print("YOLO model warm-up completed.")
    except Exception as error:
        # The API can still start and report the actual inference error later.
        print(f"YOLO warm-up warning: {error}")


# ==================================================
# Utility functions
# ==================================================

def encode_image(
    image: np.ndarray,
) -> str:
    success, encoded = cv2.imencode(
        ".jpg",
        image,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            92,
        ],
    )

    if not success:
        raise RuntimeError(
            "Result image encoding failed."
        )

    return base64.b64encode(
        encoded.tobytes()
    ).decode("utf-8")


def make_response(
    *,
    state: str,
    message: str,
    garment_type: str,
    detected: bool = False,
    confidence=None,
    width_pixels=None,
    height_pixels=None,
    width_cm=None,
    length_cm=None,
    size=None,
    pixels_per_cm=None,
    annotated_image=None,
    size_distance_cm=None,
    **tracking_data,
) -> dict:
    return {
        "state": state,
        "message": message,
        "detected": detected,
        "garment_type": garment_type,
        "confidence": confidence,
        "width_pixels": width_pixels,
        "height_pixels": height_pixels,
        "width_cm": width_cm,
        "length_cm": length_cm,
        "size": size,
        "pixels_per_cm": pixels_per_cm,
        "annotated_image": annotated_image,
        "size_distance_cm": size_distance_cm,
        **tracking_data,
    }


def extract_detection_zone(
    image: np.ndarray,
):
    height, width = image.shape[:2]

    x1 = int(
        width * ROI_MARGIN_X
    )

    x2 = int(
        width * (
            1.0 - ROI_MARGIN_X
        )
    )

    y1 = int(
        height * ROI_MARGIN_Y
    )

    y2 = int(
        height * (
            1.0 - ROI_MARGIN_Y
        )
    )

    detection_zone = image[
        y1:y2,
        x1:x2,
    ].copy()

    return (
        detection_zone,
        (x1, y1, x2, y2),
    )


def pixels_per_cm_for_frame(image: np.ndarray) -> float:
    """Scale the stored calibration when the browser supplies the same
    camera aspect ratio at a different resolution.
    """
    frame_height, frame_width = image.shape[:2]
    calibration_width = float(CALIBRATION["frame_width"])
    calibration_height = float(CALIBRATION["frame_height"])

    width_scale = frame_width / calibration_width
    height_scale = frame_height / calibration_height

    if abs(width_scale - height_scale) > 0.03:
        raise ValueError(
            "Camera aspect ratio changed after calibration. "
            "Keep the browser camera at the calibrated resolution."
        )

    resolution_scale = (width_scale + height_scale) / 2.0
    return float(CALIBRATION["pixels_per_cm"]) * resolution_scale


def enhance_low_contrast_frame(
    image: np.ndarray,
) -> np.ndarray:
    """Create a conservative fallback image for garment/background colours
    that are very similar. Geometry is unchanged, so returned masks still
    align with the original detection-zone image.
    """
    lab_image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2LAB,
    )
    lightness, channel_a, channel_b = cv2.split(
        lab_image
    )

    clahe = cv2.createCLAHE(
        clipLimit=1.8,
        tileGridSize=(8, 8),
    )
    enhanced_lightness = clahe.apply(lightness)
    enhanced_lab = cv2.merge(
        (
            enhanced_lightness,
            channel_a,
            channel_b,
        )
    )
    enhanced = cv2.cvtColor(
        enhanced_lab,
        cv2.COLOR_LAB2BGR,
    )

    blurred = cv2.GaussianBlur(
        enhanced,
        (0, 0),
        1.0,
    )
    return cv2.addWeighted(
        enhanced,
        1.15,
        blurred,
        -0.15,
        0,
    )


def prediction_has_mask(predictions) -> bool:
    if not predictions:
        return False

    result = predictions[0]
    return bool(
        result.boxes is not None
        and len(result.boxes) > 0
        and result.masks is not None
        and len(result.masks.data) > 0
    )


def select_best_garment_mask(
    result,
    image_shape,
    garment_type: str,
):
    image_height, image_width = (
        image_shape[:2]
    )

    image_area = float(
        image_height * image_width
    )

    if (
        result.boxes is None
        or len(result.boxes) == 0
        or result.masks is None
        or len(result.masks.data) == 0
    ):
        return (
            "NO_GARMENT",
            "No garment detected.",
            None,
            None,
        )

    confidences = (
        result.boxes.conf
        .detach()
        .cpu()
        .numpy()
    )

    mask_data = (
        result.masks.data
        .detach()
        .cpu()
        .numpy()
    )

    number_of_masks = min(
        len(confidences),
        len(mask_data),
    )

    candidates = []

    boundary_rejections = 0
    area_rejections = 0
    confidence_rejections = 0

    image_centre_x = (
        image_width / 2.0
    )

    image_centre_y = (
        image_height / 2.0
    )

    maximum_centre_distance = math.sqrt(
        image_centre_x ** 2
        + image_centre_y ** 2
    )

    for index in range(
        number_of_masks
    ):
        confidence = float(
            confidences[index]
        )

        minimum_confidence = (
            SHIRT_MINIMUM_CONFIDENCE
            if garment_type == "shirt"
            else MINIMUM_CONFIDENCE
        )

        if confidence < minimum_confidence:
            confidence_rejections += 1
            continue

        current_mask = (
            mask_data[index] > 0.5
        ).astype(np.uint8) * 255

        if current_mask.shape != (
            image_height,
            image_width,
        ):
            current_mask = cv2.resize(
                current_mask,
                (
                    image_width,
                    image_height,
                ),
                interpolation=(
                    cv2.INTER_NEAREST
                ),
            )

        # Remove isolated segmentation noise
        open_kernel = np.ones(
            (5, 5),
            dtype=np.uint8,
        )

        current_mask = (
            cv2.morphologyEx(
                current_mask,
                cv2.MORPH_OPEN,
                open_kernel,
                iterations=1,
            )
        )

        # Close small holes inside garment
        close_kernel = np.ones(
            (7, 7),
            dtype=np.uint8,
        )

        current_mask = (
            cv2.morphologyEx(
                current_mask,
                cv2.MORPH_CLOSE,
                close_kernel,
                iterations=2,
            )
        )

        (
            component_count,
            component_labels,
            component_stats,
            _,
        ) = cv2.connectedComponentsWithStats(
            current_mask,
            connectivity=8,
        )

        if component_count <= 1:
            continue

        component_areas = (
            component_stats[
                1:,
                cv2.CC_STAT_AREA,
            ]
        )

        largest_component_index = (
            int(
                np.argmax(
                    component_areas
                )
            )
            + 1
        )

        clean_mask = (
            component_labels
            == largest_component_index
        ).astype(np.uint8) * 255

        mask_area = float(
            np.count_nonzero(
                clean_mask
            )
        )

        area_ratio = (
            mask_area / image_area
        )

        if (
            area_ratio
            < MINIMUM_MASK_AREA_RATIO
            or area_ratio
            > MAXIMUM_MASK_AREA_RATIO
        ):
            area_rejections += 1
            continue

        nonzero_points = (
            cv2.findNonZero(
                clean_mask
            )
        )

        if nonzero_points is None:
            continue

        x, y, width, height = (
            cv2.boundingRect(
                nonzero_points
            )
        )

        # Ignore masks that meaningfully
        # extend into detection-zone edges
        border_size = max(
            8,
            int(
                min(
                    image_height,
                    image_width,
                ) * 0.01
            ),
        )

        edge_pixel_counts = [
            int(
                np.count_nonzero(
                    clean_mask[
                        :border_size,
                        :
                    ]
                )
            ),
            int(
                np.count_nonzero(
                    clean_mask[
                        -border_size:,
                        :
                    ]
                )
            ),
            int(
                np.count_nonzero(
                    clean_mask[
                        :,
                        :border_size
                    ]
                )
            ),
            int(
                np.count_nonzero(
                    clean_mask[
                        :,
                        -border_size:
                    ]
                )
            ),
        ]

        maximum_edge_ratio = max(
            edge_pixel_counts
        ) / max(
            mask_area,
            1.0,
        )

        if maximum_edge_ratio > 0.015:
            boundary_rejections += 1
            continue

        mask_centre_x = (
            x + width / 2.0
        )

        mask_centre_y = (
            y + height / 2.0
        )

        centre_distance = math.sqrt(
            (
                mask_centre_x
                - image_centre_x
            ) ** 2
            + (
                mask_centre_y
                - image_centre_y
            ) ** 2
        )

        normalised_centre_distance = min(
            centre_distance
            / maximum_centre_distance,
            1.0,
        )

        centre_score = (
            1.0
            - normalised_centre_distance
        )

        # Garments generally occupy a useful
        # but not excessive part of the zone
        area_score = min(
            area_ratio / 0.25,
            1.0,
        )

        final_score = (
            confidence * 0.70
            + centre_score * 0.20
            + area_score * 0.10
        )

        candidates.append({
            "mask": clean_mask,
            "confidence": confidence,
            "area": mask_area,
            "area_ratio": area_ratio,
            "score": final_score,
            "box": (
                x,
                y,
                width,
                height,
            ),
        })

    if not candidates:
        if confidence_rejections > 0:
            return (
                "LOW_CONFIDENCE",
                (
                    "A possible garment was found, "
                    "but confidence is too low."
                ),
                None,
                None,
            )

        if boundary_rejections > 0:
            return (
                "PARTIAL_GARMENT",
                (
                    "Garment is not fully inside "
                    "the detection zone."
                ),
                None,
                None,
            )

        if area_rejections > 0:
            return (
                "INVALID_GARMENT_AREA",
                (
                    "Detected region is too small "
                    "or too large to be a garment."
                ),
                None,
                None,
            )

        return (
            "NO_GARMENT",
            "No garment detected.",
            None,
            None,
        )

    candidates.sort(
        key=lambda candidate:
            candidate["score"],
        reverse=True,
    )

    best_candidate = candidates[0]

    # If another similarly large mask exists,
    # there may be multiple garments
    if len(candidates) > 1:
        second_candidate = (
            candidates[1]
        )

        second_is_significant = (
            second_candidate["area"]
            >= best_candidate["area"]
            * 0.45
        )

        second_has_similar_score = (
            second_candidate["score"]
            >= best_candidate["score"]
            * 0.75
        )

        if (
            second_is_significant
            and second_has_similar_score
        ):
            return (
                "MULTIPLE_GARMENTS",
                (
                    "Multiple garments detected. "
                    "Keep only one garment inside "
                    "the detection zone."
                ),
                None,
                None,
            )

    print(
        "Selected garment mask | "
        f"confidence="
        f"{best_candidate['confidence']:.3f} | "
        f"area_ratio="
        f"{best_candidate['area_ratio']:.3f} | "
        f"score="
        f"{best_candidate['score']:.3f}"
    )

    return (
        "VALID",
        "Best garment mask selected.",
        best_candidate["mask"],
        best_candidate["confidence"],
    )

# ==================================================
# Rotate garment upright
# ==================================================

def rotate_image_and_mask(
    image: np.ndarray,
    mask: np.ndarray,
    garment_type: str,
):
    y_values, x_values = np.where(
        mask > 0
    )

    points = np.column_stack(
        (
            x_values,
            y_values,
        )
    ).astype(np.float32)

    centre = points.mean(
        axis=0
    )

    centred_points = (
        points - centre
    )

    covariance = np.cov(
        centred_points,
        rowvar=False,
    )

    eigenvalues, eigenvectors = (
        np.linalg.eigh(covariance)
    )

    major_axis = eigenvectors[
        :,
        np.argmax(eigenvalues),
    ]

    major_angle = math.degrees(
        math.atan2(
            major_axis[1],
            major_axis[0],
        )
    )

    rotation_angle = (
        90.0 - major_angle
    )

    while rotation_angle > 90:
        rotation_angle -= 180

    while rotation_angle < -90:
        rotation_angle += 180

    height, width = image.shape[:2]

    rotation_matrix = (
        cv2.getRotationMatrix2D(
            (
                width / 2,
                height / 2,
            ),
            rotation_angle,
            1.0,
        )
    )

    cosine = abs(
        rotation_matrix[0, 0]
    )

    sine = abs(
        rotation_matrix[0, 1]
    )

    new_width = int(
        height * sine
        + width * cosine
    )

    new_height = int(
        height * cosine
        + width * sine
    )

    rotation_matrix[
        0,
        2,
    ] += (
        new_width / 2
        - width / 2
    )

    rotation_matrix[
        1,
        2,
    ] += (
        new_height / 2
        - height / 2
    )

    rotated_image = cv2.warpAffine(
        image,
        rotation_matrix,
        (
            new_width,
            new_height,
        ),
        flags=cv2.INTER_LINEAR,
        borderValue=(30, 30, 30),
    )

    rotated_mask = cv2.warpAffine(
        mask,
        rotation_matrix,
        (
            new_width,
            new_height,
        ),
        flags=cv2.INTER_NEAREST,
        borderValue=0,
    )

    y_values, x_values = np.where(
        rotated_mask > 0
    )

    padding = 25

    x1 = max(
        int(x_values.min()) - padding,
        0,
    )

    x2 = min(
        int(x_values.max()) + padding,
        new_width - 1,
    )

    y1 = max(
        int(y_values.min()) - padding,
        0,
    )

    y2 = min(
        int(y_values.max()) + padding,
        new_height - 1,
    )

    cropped_image = rotated_image[
        y1:y2 + 1,
        x1:x2 + 1,
    ]

    cropped_mask = rotated_mask[
        y1:y2 + 1,
        x1:x2 + 1,
    ]

    # PCA has a 180-degree ambiguity. Ensure the collar/waist side is at the
    # top by comparing foreground widths near both ends. T-shirts and shirts
    # are wider at the sleeve/shoulder end; trousers contain more continuous
    # foreground at the waistband end than at the separated leg openings.
    cropped_y, _ = np.where(cropped_mask > 0)
    garment_top = int(cropped_y.min())
    garment_bottom = int(cropped_y.max())
    garment_height = garment_bottom - garment_top + 1
    row_foreground = np.count_nonzero(cropped_mask > 0, axis=1)

    upper_start = int(garment_top + garment_height * 0.08)
    upper_end = int(garment_top + garment_height * 0.34)
    lower_start = int(garment_top + garment_height * 0.66)
    lower_end = int(garment_top + garment_height * 0.92)

    upper_values = row_foreground[upper_start:upper_end + 1]
    lower_values = row_foreground[lower_start:lower_end + 1]
    upper_values = upper_values[upper_values > 0]
    lower_values = lower_values[lower_values > 0]

    if len(upper_values) and len(lower_values):
        upper_score = float(np.percentile(upper_values, 75))
        lower_score = float(np.percentile(lower_values, 75))

        if lower_score > upper_score * 1.08:
            cropped_image = cv2.rotate(
                cropped_image,
                cv2.ROTATE_180,
            )
            cropped_mask = cv2.rotate(
                cropped_mask,
                cv2.ROTATE_180,
            )
            print(
                f"Auto orientation corrected | {garment_type} | "
                "collar/waist moved to top"
            )

    return (
        cropped_image,
        cropped_mask,
    )


# ==================================================
# Mask boundary refinement
# ==================================================

def refine_garment_mask(
    image: np.ndarray,
    initial_mask: np.ndarray,
) -> np.ndarray:
    """
    Use the YOLO mask as a GrabCut prior to remove table/background regions
    that occasionally leak into the segmentation. If refinement is not
    trustworthy, return the original YOLO mask unchanged.
    """

    image_height, image_width = image.shape[:2]
    maximum_side = max(image_height, image_width)
    resize_scale = min(1.0, 640.0 / max(maximum_side, 1))

    working_width = max(1, int(round(image_width * resize_scale)))
    working_height = max(1, int(round(image_height * resize_scale)))

    working_image = cv2.resize(
        image,
        (working_width, working_height),
        interpolation=cv2.INTER_AREA,
    )
    working_mask = cv2.resize(
        (initial_mask > 0).astype(np.uint8) * 255,
        (working_width, working_height),
        interpolation=cv2.INTER_NEAREST,
    )

    initial_area = int(np.count_nonzero(working_mask))
    if initial_area < 100:
        return initial_mask

    kernel_size = max(5, int(round(min(working_height, working_width) * 0.02)))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)

    dilated_mask = cv2.dilate(working_mask, kernel, iterations=1)

    grabcut_mask = np.full(
        (working_height, working_width),
        cv2.GC_BGD,
        dtype=np.uint8,
    )
    grabcut_mask[dilated_mask > 0] = cv2.GC_PR_BGD
    grabcut_mask[working_mask > 0] = cv2.GC_PR_FGD

    # Learn the fixed table/background colours from pixels outside the YOLO
    # region. Foreground seeds are selected by colour distance from those
    # background clusters. This prevents a leaked red/white table section
    # from becoming the definite-foreground seed.
    lab_image = cv2.cvtColor(
        working_image,
        cv2.COLOR_BGR2LAB,
    ).astype(np.float32)
    background_pixels = lab_image[dilated_mask == 0]

    if len(background_pixels) < 100:
        return initial_mask

    sample_step = max(1, int(math.ceil(len(background_pixels) / 6000)))
    background_sample = background_pixels[::sample_step]
    cluster_count = min(4, max(1, len(background_sample) // 100))
    criteria = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
        30,
        0.5,
    )

    cv2.setRNGSeed(42)
    try:
        _, _, background_centres = cv2.kmeans(
            background_sample,
            cluster_count,
            None,
            criteria,
            5,
            cv2.KMEANS_PP_CENTERS,
        )
    except cv2.error:
        return initial_mask

    colour_distances = np.linalg.norm(
        lab_image[:, :, None, :] - background_centres[None, None, :, :],
        axis=3,
    )
    nearest_background_distance = np.min(colour_distances, axis=2)

    outside_distances = nearest_background_distance[dilated_mask == 0]
    background_threshold = max(
        8.0,
        float(np.percentile(outside_distances, 95)) + 3.0,
    )
    inside_distances = nearest_background_distance[working_mask > 0]
    foreground_threshold = max(
        background_threshold + 6.0,
        float(np.percentile(inside_distances, 70)),
    )

    background_like_leak = (
        (working_mask > 0)
        & (nearest_background_distance <= background_threshold)
    )
    grabcut_mask[background_like_leak] = cv2.GC_PR_BGD

    sure_foreground = (
        (working_mask > 0)
        & (nearest_background_distance >= foreground_threshold)
    )

    if int(np.count_nonzero(sure_foreground)) < 25:
        return initial_mask

    grabcut_mask[sure_foreground] = cv2.GC_FGD

    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)

    try:
        cv2.grabCut(
            working_image,
            grabcut_mask,
            None,
            background_model,
            foreground_model,
            3,
            cv2.GC_INIT_WITH_MASK,
        )
    except cv2.error:
        return initial_mask

    refined_mask = np.where(
        (grabcut_mask == cv2.GC_FGD)
        | (grabcut_mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    refined_mask[dilated_mask == 0] = 0

    refined_mask = cv2.morphologyEx(
        refined_mask,
        cv2.MORPH_CLOSE,
        np.ones((7, 7), dtype=np.uint8),
        iterations=2,
    )
    refined_mask = cv2.morphologyEx(
        refined_mask,
        cv2.MORPH_OPEN,
        np.ones((3, 3), dtype=np.uint8),
        iterations=1,
    )

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        refined_mask,
        connectivity=8,
    )
    if component_count <= 1:
        return initial_mask

    largest_index = 1 + int(
        np.argmax(stats[1:, cv2.CC_STAT_AREA])
    )
    refined_mask = (labels == largest_index).astype(np.uint8) * 255
    refined_area = int(np.count_nonzero(refined_mask))
    retained_ratio = refined_area / max(initial_area, 1)

    # Reject refinements that removed most of the garment or expanded beyond
    # the model prior. This keeps the operation a safe correction, not a new
    # uncontrolled segmentation method.
    if not 0.45 <= retained_ratio <= 1.05:
        return initial_mask

    refined_mask = cv2.resize(
        refined_mask,
        (image_width, image_height),
        interpolation=cv2.INTER_NEAREST,
    )

    print(
        "Mask refinement accepted | "
        f"retained_ratio={retained_ratio:.3f}"
    )
    return refined_mask


# ==================================================
# Straight-line measurements
# ==================================================

def row_measurement(
    mask: np.ndarray,
    start_row: int,
    end_row: int,
):
    candidates = []

    start_row = max(
        start_row,
        0,
    )

    end_row = min(
        end_row,
        mask.shape[0] - 1,
    )

    for row in range(
        start_row,
        end_row + 1,
    ):
        x_values = np.where(
            mask[row] > 0
        )[0]

        if len(x_values) < 2:
            continue

        left_x = int(
            x_values.min()
        )

        right_x = int(
            x_values.max()
        )

        width = (
            right_x - left_x + 1
        )

        candidates.append(
            (
                width,
                row,
                left_x,
                right_x,
            )
        )

    if not candidates:
        raise ValueError(
            "Could not calculate width line."
        )

    widths = [
        item[0]
        for item in candidates
    ]

    median_width = float(
        np.median(widths)
    )

    return min(
        candidates,
        key=lambda item: abs(
            item[0] - median_width
        ),
    )


def column_measurement(
    mask: np.ndarray,
    start_column: int,
    end_column: int,
):
    """Find a stable straight vertical garment measurement."""

    candidates = []
    start_column = max(int(start_column), 0)
    end_column = min(int(end_column), mask.shape[1] - 1)

    for column in range(start_column, end_column + 1):
        y_values = np.where(mask[:, column] > 0)[0]

        if len(y_values) < 2:
            continue

        top_y = int(y_values.min())
        bottom_y = int(y_values.max())
        height = bottom_y - top_y + 1
        candidates.append((height, column, top_y, bottom_y))

    if not candidates:
        raise ValueError(
            "Could not calculate vertical measurement."
        )

    median_height = float(
        np.median([item[0] for item in candidates])
    )

    return min(
        candidates,
        key=lambda item: abs(item[0] - median_height),
    )


def longest_column_measurement(
    mask: np.ndarray,
    start_column: int,
    end_column: int,
):
    """Find the collar-centre to bottom-hem vertical extent."""

    candidates = []
    start_column = max(int(start_column), 0)
    end_column = min(int(end_column), mask.shape[1] - 1)

    for column in range(start_column, end_column + 1):
        y_values = np.where(mask[:, column] > 0)[0]
        if len(y_values) < 2:
            continue

        top_y = int(y_values.min())
        bottom_y = int(y_values.max())
        extent = bottom_y - top_y + 1
        candidates.append((extent, column, top_y, bottom_y))

    if not candidates:
        raise ValueError(
            "Could not calculate collar-to-hem measurement."
        )

    return max(candidates, key=lambda item: item[0])


def body_chest_measurement(
    mask: np.ndarray,
    top_y: int,
    bottom_y: int,
    left_x: int,
    right_x: int,
):
    """
    Measure the persistent torso width below both sleeves. A column must be
    garment foreground through most torso rows, so short-lived mask leaks and
    sleeve protrusions cannot enlarge the chest width.
    """

    total_height = bottom_y - top_y + 1
    torso_start = int(top_y + total_height * 0.34)
    torso_end = int(top_y + total_height * 0.78)
    torso = mask[torso_start:torso_end + 1, left_x:right_x + 1] > 0

    if torso.size == 0:
        raise ValueError("Could not locate the T-shirt body region.")

    column_support = np.mean(torso, axis=0)
    persistent_columns = np.where(column_support >= 0.70)[0]

    if len(persistent_columns) < 2:
        return row_measurement(
            mask,
            int(top_y + total_height * 0.36),
            int(top_y + total_height * 0.46),
        )

    # Split supported columns into continuous runs and keep the widest body
    # run. Isolated table/background strips are therefore ignored.
    split_points = np.where(np.diff(persistent_columns) > 1)[0] + 1
    runs = np.split(persistent_columns, split_points)
    body_run = max(runs, key=len)

    body_left_x = left_x + int(body_run[0])
    body_right_x = left_x + int(body_run[-1])
    body_width = body_right_x - body_left_x + 1

    target_row = int(top_y + total_height * 0.42)
    candidate_rows = range(
        int(top_y + total_height * 0.36),
        int(top_y + total_height * 0.48) + 1,
    )
    width_y = min(
        candidate_rows,
        key=lambda row: (
            0 if (
                mask[row, body_left_x] > 0
                and mask[row, body_right_x] > 0
            ) else 1,
            abs(row - target_row),
        ),
    )

    return (
        int(body_width),
        int(width_y),
        int(body_left_x),
        int(body_right_x),
    )


def calculate_straight_measurements(
    mask: np.ndarray,
    garment_type: str,
):
    """
    T-shirt/Shirt:
        width  = straight body/chest line below both sleeves
        length = centre collar to centre bottom hem

    Trouser:
        width  = flat waistband width
        length = straight outside seam (not the crotch/centre line)
    """

    y_values, x_values = np.where(mask > 0)

    if len(x_values) == 0 or len(y_values) == 0:
        raise ValueError("Garment mask is empty.")

    top_y = int(y_values.min())
    bottom_y = int(y_values.max())
    left_x = int(x_values.min())
    right_x = int(x_values.max())

    total_height = bottom_y - top_y + 1
    total_width = right_x - left_x + 1

    if garment_type in {"tshirt", "shirt"}:
        # Straight line across the body immediately below both sleeves.
        (
            width_pixels,
            width_y,
            width_left_x,
            width_right_x,
        ) = body_chest_measurement(
            mask,
            top_y,
            bottom_y,
            left_x,
            right_x,
        )

        # Exact requested definition: centre collar to centre bottom edge.
        (
            height_pixels,
            height_x,
            height_top_y,
            height_bottom_y,
        ) = longest_column_measurement(
            mask,
            int(left_x + total_width * 0.47),
            int(left_x + total_width * 0.53),
        )

    elif garment_type == "trouser":
        waist_start = int(top_y + total_height * 0.03)
        waist_end = int(top_y + total_height * 0.12)

        (
            width_pixels,
            width_y,
            width_left_x,
            width_right_x,
        ) = row_measurement(mask, waist_start, waist_end)

        # The centre column ends at the crotch. Measure both outer seam
        # bands and keep the longer complete seam.
        left_result = column_measurement(
            mask,
            int(left_x + total_width * 0.05),
            int(left_x + total_width * 0.20),
        )
        right_result = column_measurement(
            mask,
            int(left_x + total_width * 0.80),
            int(left_x + total_width * 0.95),
        )

        (
            height_pixels,
            height_x,
            height_top_y,
            height_bottom_y,
        ) = max(
            (left_result, right_result),
            key=lambda result: result[0],
        )

    else:
        raise ValueError(
            f"Unsupported garment type: {garment_type}"
        )

    measurement_points = {
        "width_start": (int(width_left_x), int(width_y)),
        "width_end": (int(width_right_x), int(width_y)),
        "height_start": (int(height_x), int(height_top_y)),
        "height_end": (int(height_x), int(height_bottom_y)),
    }

    return (
        float(width_pixels),
        float(height_pixels),
        measurement_points,
    )


# ==================================================
# Full-garment geometry validation
# ==================================================

def validate_physical_measurement(
    garment_type: str,
    width_cm: float,
    length_cm: float,
) -> tuple[bool, str]:
    """
    Reject masks that contain only a narrow garment fragment or an
    implausibly large background region. Bounds are derived from the local
    size chart instead of inventing a second independent size chart.
    """
    if (
        not np.isfinite(width_cm)
        or not np.isfinite(length_cm)
        or width_cm <= 0
        or length_cm <= 0
    ):
        return (
            False,
            "Garment dimensions could not be calculated.",
        )

    references = SIZE_CHART.get(
        garment_type,
        [],
    )

    # A category without approved local references can still be measured,
    # but it cannot be assigned a reliable size label yet.
    if not references:
        return True, "Physical dimensions calculated."

    reference_widths = [
        float(reference["width_cm"])
        for reference in references
    ]
    reference_lengths = [
        float(reference["height_cm"])
        for reference in references
    ]

    minimum_width = (
        min(reference_widths)
        - TSHIRT_EXTRA_WIDTH_MARGIN_CM
    )
    maximum_width = (
        max(reference_widths)
        + TSHIRT_EXTRA_WIDTH_MARGIN_CM
    )
    minimum_length = (
        min(reference_lengths)
        - TSHIRT_EXTRA_LENGTH_MARGIN_CM
    )
    maximum_length = (
        max(reference_lengths)
        + TSHIRT_EXTRA_LENGTH_MARGIN_CM
    )

    width_length_ratio = (
        width_cm / length_cm
    )

    if not (
        minimum_width
        <= width_cm
        <= maximum_width
    ):
        return (
            False,
            "Only part of the garment was segmented: invalid width.",
        )

    if not (
        minimum_length
        <= length_cm
        <= maximum_length
    ):
        return (
            False,
            "Only part of the garment was segmented: invalid length.",
        )

    if garment_type in {"tshirt", "shirt"} and not (
        TSHIRT_MIN_WIDTH_LENGTH_RATIO
        <= width_length_ratio
        <= TSHIRT_MAX_WIDTH_LENGTH_RATIO
    ):
        return (
            False,
            "Garment shape is incomplete or heavily folded. "
            "Keep the complete garment inside the detection zone.",
        )

    return True, "Complete garment geometry accepted."


# ==================================================
# Size classification
# ==================================================

def classify_size(
    garment_type: str,
    width_cm: float,
    height_cm: float,
):
    references = SIZE_CHART.get(
        garment_type,
        [],
    )

    if not references:
        return (
            "REFERENCE_REQUIRED",
            None,
        )

    scored_sizes = []

    for reference in references:
        width_difference = (
            width_cm
            - float(
                reference["width_cm"]
            )
        )

        height_difference = (
            height_cm
            - float(
                reference["height_cm"]
            )
        )

        if garment_type == "shirt":
            # Chest width is the stronger discriminator for adjacent shirt
            # sizes. A weighted distance prevents small collar/hem mask noise
            # from switching a stable S shirt to M (or the reverse).
            distance = math.sqrt(
                0.70 * width_difference ** 2
                + 0.30 * height_difference ** 2
            )
        else:
            distance = math.sqrt(
                width_difference ** 2
                + height_difference ** 2
            )

        scored_sizes.append(
            (
                distance,
                reference["size"],
            )
        )

    scored_sizes.sort(
        key=lambda item: item[0]
    )

    best_distance, best_size = (
        scored_sizes[0]
    )

    if (
        best_distance
        > SIZE_DISTANCE_LIMIT_CM
    ):
        return (
            "UNKNOWN",
            best_distance,
        )

    return (
        best_size,
        best_distance,
    )


# ==================================================
# Annotated result
# ==================================================

def create_annotated_result(
    image: np.ndarray,
    mask: np.ndarray,
    measurement_points: dict,
    width_cm: float,
    height_cm: float,
    confidence: float,
    size: str,
    pixels_per_cm: float,
):
    annotated = image.copy()

    colour_mask = np.zeros_like(
        annotated
    )

    colour_mask[
        mask > 0
    ] = (180, 0, 180)

    annotated = cv2.addWeighted(
        annotated,
        1.0,
        colour_mask,
        0.35,
        0,
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    cv2.drawContours(
        annotated,
        contours,
        -1,
        (0, 255, 0),
        3,
    )

    cv2.line(
        annotated,
        measurement_points[
            "width_start"
        ],
        measurement_points[
            "width_end"
        ],
        (255, 255, 0),
        4,
    )

    cv2.line(
        annotated,
        measurement_points[
            "height_start"
        ],
        measurement_points[
            "height_end"
        ],
        (0, 255, 255),
        4,
    )

    cv2.putText(
        annotated,
        f"Width: {width_cm:.1f} cm",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated,
        f"Height: {height_cm:.1f} cm",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated,
        f"Size: {size}",
        (20, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated,
        (
            f"Confidence: "
            f"{confidence:.2f}"
        ),
        (20, 140),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated,
        (
            f"Scale: "
            f"{pixels_per_cm:.3f} px/cm"
        ),
        (20, 172),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    return annotated


# ==================================================
# API endpoints
# ==================================================

ORDER_SIZES = ("S", "M", "L", "XL")
ORDER_STATUSES = {"active", "paused", "completed"}


def _require_text(payload: dict, key: str, *, maximum: int = 120) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail=f"{key} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise HTTPException(
            status_code=400,
            detail=f"{key} must be {maximum} characters or fewer.",
        )
    return value


def _parse_order_date(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format.",
        ) from error
    return value


def _parse_order_time(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use HH:MM format.",
        ) from error
    return value


def _order_counts(value: object, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} is invalid.")
    result = {}
    for size in ORDER_SIZES:
        item = value.get(size, 0)
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise HTTPException(
                status_code=400,
                detail=f"{field_name}.{size} must be a number.",
            )
        if item < 0 or int(item) != item:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name}.{size} must be a non-negative whole number.",
            )
        result[size] = int(item)
    return result


def validate_order_payload(payload: object) -> dict:
    """Validate and normalize the complete order snapshot sent by the UI."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Order body must be an object.")

    session_id = _require_text(payload, "id")
    order_id = _require_text(payload, "orderId")
    garment_type = _require_text(payload, "garmentType", maximum=40)
    status = payload.get("status")
    if status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid order status.")

    schedule = payload.get("schedule")
    if not isinstance(schedule, dict):
        raise HTTPException(status_code=400, detail="schedule is required.")
    schedule_order_id = _require_text(schedule, "orderId")
    if schedule_order_id.casefold() != order_id.casefold():
        raise HTTPException(
            status_code=400,
            detail="The schedule Order ID does not match the session Order ID.",
        )

    start_date = _parse_order_date(schedule.get("startDate"), "Start date")
    end_date = _parse_order_date(schedule.get("endDate"), "End date")
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date.",
        )

    shift_start = _parse_order_time(schedule.get("shiftStart"), "Shift start")
    shift_end = _parse_order_time(schedule.get("shiftEnd"), "Shift end")
    if shift_start >= shift_end:
        raise HTTPException(
            status_code=400,
            detail="Shift end time must be after shift start time.",
        )

    targets = _order_counts(schedule.get("targets"), "targets")
    if sum(targets.values()) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Set at least one size target above 0.",
        )

    breaks = schedule.get("breaks", [])
    if not isinstance(breaks, list):
        raise HTTPException(status_code=400, detail="breaks must be a list.")
    clean_breaks = []
    for index, item in enumerate(breaks, start=1):
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=400, detail=f"Break {index} is invalid."
            )
        break_id = _require_text(item, "id")
        name = _require_text(item, "name")
        break_start = _parse_order_time(item.get("start"), f"Break {index} start")
        break_end = _parse_order_time(item.get("end"), f"Break {index} end")
        if break_start >= break_end:
            raise HTTPException(
                status_code=400,
                detail=f"Break {index} end time must be after its start time.",
            )
        if break_start < shift_start or break_end > shift_end:
            raise HTTPException(
                status_code=400,
                detail=f"Break {index} must be inside the shift time.",
            )
        clean_breaks.append(
            {"id": break_id, "name": name, "start": break_start, "end": break_end}
        )

    clean_schedule = {
        "garmentType": garment_type,
        "orderId": order_id,
        "startDate": start_date,
        "endDate": end_date,
        "shiftStart": shift_start,
        "shiftEnd": shift_end,
        "targets": targets,
        "breaks": clean_breaks,
    }
    accumulated_minutes = payload.get("accumulatedMinutes", 0)
    if (
        isinstance(accumulated_minutes, bool)
        or not isinstance(accumulated_minutes, (int, float))
        or accumulated_minutes < 0
        or int(accumulated_minutes) != accumulated_minutes
    ):
        raise HTTPException(
            status_code=400,
            detail="accumulatedMinutes must be a non-negative whole number.",
        )

    result = {
        "id": session_id,
        "orderId": order_id,
        "garmentType": garment_type,
        "status": status,
        "schedule": clean_schedule,
        "packed": _order_counts(payload.get("packed"), "packed"),
        "carriedCounts": _order_counts(
            payload.get("carriedCounts"), "carriedCounts"
        ),
        "baselineCounts": _order_counts(
            payload.get("baselineCounts"), "baselineCounts"
        ),
        "createdAt": _require_text(payload, "createdAt"),
        "startedAt": _require_text(payload, "startedAt"),
        "activeStartedAt": _require_text(payload, "activeStartedAt"),
        "accumulatedMinutes": int(accumulated_minutes),
    }
    measurement_session_id = payload.get("measurementSessionId")
    if measurement_session_id is not None:
        if (
            isinstance(measurement_session_id, bool)
            or not isinstance(measurement_session_id, int)
            or measurement_session_id < 1
        ):
            raise HTTPException(
                status_code=400, detail="measurementSessionId is invalid."
            )
        result["measurementSessionId"] = measurement_session_id
    for key in ("endedAt", "completedAt"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise HTTPException(status_code=400, detail=f"{key} is invalid.")
            result[key] = value
    return result

@app.get("/")
def root():
    return {
        "message": (
            "Garment Measurement "
            "API is running"
        )
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": True,
        "model_path": str(MODEL_PATH),
        "device": DEVICE_NAME,
        "calibration_mode": "fixed_100cm_marker_free",
        "camera_height_cm": CAMERA_HEIGHT_CM,
        "calibrated_pixels_per_cm": float(CALIBRATION["pixels_per_cm"]),
        "calibration_resolution": [
            int(CALIBRATION["frame_width"]),
            int(CALIBRATION["frame_height"]),
        ],
        "inference_image_size": INFERENCE_IMAGE_SIZE,
        "stable_frames_required": STABLE_FRAMES_REQUIRED,
        "empty_frames_to_rearm": EMPTY_FRAMES_TO_REARM,
        "removal_scene_difference": MINIMUM_REMOVAL_SCENE_DIFFERENCE,
        "database": "sqlite",
        "database_path": str(DATABASE_PATH),
    }


@app.get("/counts")
def get_counts():
    """Return size-wise totals and the most recent counted garments."""
    with TRACKER_LOCK:
        return tracker_snapshot()


@app.get("/measurements")
def get_measurements(
    limit: int = 100,
):
    """Return persistent garment records from all counting sessions."""
    return {
        "measurements": get_all_measurements(
            limit=limit,
        )
    }


@app.get("/orders")
def get_orders():
    """Return database-backed production orders for History and Analytics."""
    return {"orders": get_production_orders()}


@app.post("/orders")
def upsert_order(payload: dict):
    """Create or update one order after server-side validation."""
    order = validate_order_payload(payload)
    try:
        return {"order": save_production_order(order)}
    except sqlite3.IntegrityError as error:
        message = str(error).lower()
        if "order_id" in message:
            detail = f"Order ID {order['orderId']} already exists."
        elif "active" in message or "status" in message:
            detail = "Another order is already active. End it before starting this one."
        else:
            detail = "The order conflicts with an existing database record."
        raise HTTPException(status_code=409, detail=detail) from error


@app.delete("/orders/{session_id}")
def delete_order(session_id: str):
    """Permanently delete one old order and its linked measurement rows."""
    try:
        return delete_production_order(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Order not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/counts/reset")
def reset_counts():
    """
    Finish the current database session and start a new counting session.
    Previous measurements remain available in SQLite.
    """
    session_id = start_new_session()

    with TRACKER_LOCK:
        TRACKER["tracking_state"] = "EMPTY"
        TRACKER["stable_samples"].clear()
        TRACKER["empty_frames"] = 0
        TRACKER["current_garment_counted"] = False
        TRACKER["last_counted_scene_signature"] = None
        TRACKER["counts"] = empty_count_table()
        TRACKER["history"].clear()
        snapshot = tracker_snapshot()
        snapshot["session_id"] = session_id
        return snapshot


@app.post("/measure")
async def measure_garment(
    file: UploadFile = File(...),
    garment_type: str = Form(...),
):
    garment_type = (
        garment_type.lower().strip()
    )

    if (
        garment_type
        not in ALLOWED_GARMENT_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid garment type.",
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    if (
        len(image_bytes)
        > MAX_UPLOAD_SIZE
    ):
        raise HTTPException(
            status_code=413,
            detail="Image exceeds 10 MB.",
        )

    image_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8,
    )

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid image.",
        )

    try:
        pixels_per_cm = pixels_per_cm_for_frame(image)
    except ValueError as error:
        tracking_data = update_tracker_non_ready(
            "CALIBRATION_MISMATCH"
        )
        return make_response(
            state="CALIBRATION_MISMATCH",
            message=str(error),
            garment_type=garment_type,
            **tracking_data,
        )

    detection_zone, _ = extract_detection_zone(image)
    scene_signature = calculate_scene_signature(detection_zone)
    prediction_confidence = (
        SHIRT_INFERENCE_CONFIDENCE
        if garment_type == "shirt"
        else INFERENCE_CONFIDENCE
    )

    predictions = model.predict(
        source=detection_zone,
        imgsz=INFERENCE_IMAGE_SIZE,
        conf=prediction_confidence,
        iou=0.45,
        max_det=3,
        agnostic_nms=True,
        device=DEVICE,
        half=torch.cuda.is_available(),
        retina_masks=True,
        verbose=False,
    )

    inference_variant = "original"

    # Retry only missed frames. This preserves normal speed while improving
    # pale-on-pale and dark-on-dark garment detection.
    if not prediction_has_mask(predictions):
        enhanced_zone = enhance_low_contrast_frame(
            detection_zone
        )
        predictions = model.predict(
            source=enhanced_zone,
            imgsz=INFERENCE_IMAGE_SIZE,
            conf=prediction_confidence,
            iou=0.45,
            max_det=3,
            agnostic_nms=True,
            device=DEVICE,
            half=torch.cuda.is_available(),
            retina_masks=True,
            # Test-time augmentation was the main source of the long pause
            # seen with patterned shirts. The contrast pass is already a
            # second observation, so keep it as one fast inference.
            augment=False,
            verbose=False,
        )
        inference_variant = "contrast_enhanced"

    if not predictions:
        tracking_data = update_tracker_non_ready(
            "NO_GARMENT",
            scene_signature=scene_signature,
        )
        return make_response(
            state="NO_GARMENT",
            message="No garment detected.",
            garment_type=garment_type,
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
            **tracking_data,
        )

    result = predictions[0]

    (
        mask_state,
        mask_message,
        garment_mask,
        confidence,
    ) = select_best_garment_mask(
        result,
        detection_zone.shape,
        garment_type,
    )

    # A raw YOLO result can contain a weak/background mask and therefore skip
    # the old "no mask" retry, even though candidate validation rejects it.
    # Retry rejected shirt candidates once on the contrast-enhanced frame.
    # This fixes intermittent shirt misses without running the expensive retry
    # for every successful frame.
    if (
        garment_mask is None
        and garment_type == "shirt"
        and inference_variant == "original"
    ):
        enhanced_zone = enhance_low_contrast_frame(
            detection_zone
        )
        retry_predictions = model.predict(
            source=enhanced_zone,
            imgsz=INFERENCE_IMAGE_SIZE,
            conf=prediction_confidence,
            iou=0.45,
            max_det=3,
            agnostic_nms=True,
            device=DEVICE,
            half=torch.cuda.is_available(),
            retina_masks=True,
            augment=False,
            verbose=False,
        )

        if retry_predictions:
            (
                retry_state,
                retry_message,
                retry_mask,
                retry_confidence,
            ) = select_best_garment_mask(
                retry_predictions[0],
                detection_zone.shape,
                garment_type,
            )

            if retry_mask is not None:
                mask_state = retry_state
                mask_message = retry_message
                garment_mask = retry_mask
                confidence = retry_confidence
                inference_variant = "contrast_enhanced"
    
    if garment_mask is None:
        tracking_data = update_tracker_non_ready(
            mask_state,
            scene_signature=scene_signature,
        )
        return make_response(
            state=mask_state,
            message=mask_message,
            garment_type=garment_type,
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
            **tracking_data,
        )

    garment_mask = refine_garment_mask(
        detection_zone,
        garment_mask,
    )

    (
        upright_image,
        upright_mask,
    ) = rotate_image_and_mask(
        detection_zone,
        garment_mask,
        garment_type,
    )

    try:
        (
            width_pixels,
            height_pixels,
            measurement_points,
        ) = calculate_straight_measurements(
            upright_mask,
            garment_type,
        )
    except ValueError as error:
        tracking_data = update_tracker_non_ready(
            "MEASUREMENT_FAILED",
            scene_signature=scene_signature,
        )
        return make_response(
            state="MEASUREMENT_FAILED",
            message=str(error),
            garment_type=garment_type,
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
            **tracking_data,
        )

    width_cm = (
        width_pixels
        / pixels_per_cm
    )

    height_cm = (
        height_pixels
        / pixels_per_cm
    )

    (
        physical_measurement_valid,
        physical_validation_message,
    ) = validate_physical_measurement(
        garment_type,
        width_cm,
        height_cm,
    )

    if not physical_measurement_valid:
        tracking_data = update_tracker_non_ready(
            "PARTIAL_GARMENT",
            scene_signature=scene_signature,
        )
        return make_response(
            state="PARTIAL_GARMENT",
            message=physical_validation_message,
            garment_type=garment_type,
            detected=False,
            confidence=round(confidence, 4),
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
            **tracking_data,
        )

    size, size_distance = classify_size(
        garment_type,
        width_cm,
        height_cm,
    )

    tracking_data = update_tracker_ready(
        garment_type=garment_type,
        size=size,
        width_cm=width_cm,
        length_cm=height_cm,
        confidence=confidence,
        scene_signature=scene_signature,
    )

    # Display the rolling/stored median instead of a noisy single-frame
    # measurement. Once counted, the values remain locked until the garment
    # is physically removed from the table.
    display_measurement = tracking_data.get("display_measurement")
    if (
        display_measurement is not None
        and display_measurement["garment_type"] == garment_type
    ):
        width_cm = float(display_measurement["width_cm"])
        height_cm = float(display_measurement["length_cm"])
        confidence = float(display_measurement["confidence"])
        size = str(display_measurement["size"])
        width_pixels = width_cm * pixels_per_cm
        height_pixels = height_cm * pixels_per_cm
        _, size_distance = classify_size(
            garment_type,
            width_cm,
            height_cm,
        )

    annotated_image = (
        create_annotated_result(
            upright_image,
            upright_mask,
            measurement_points,
            width_cm,
            height_cm,
            confidence,
            size,
            pixels_per_cm,
        )
    )

    encoded_image = encode_image(
        annotated_image
    )

    print(
        f"READY | {garment_type} | "
        f"{width_cm:.2f} cm × "
        f"{height_cm:.2f} cm | "
        f"Size: {size} | "
        f"Scale: {pixels_per_cm:.3f}"
    )

    return make_response(
        state="READY",
        message=(
            "Garment measured successfully."
        ),
        garment_type=garment_type,
        detected=True,
        confidence=round(
            confidence,
            4,
        ),
        width_pixels=round(
            width_pixels,
            2,
        ),
        height_pixels=round(
            height_pixels,
            2,
        ),
        width_cm=round(
            width_cm,
            2,
        ),
        length_cm=round(
            height_cm,
            2,
        ),
        size=size,
        size_distance_cm=(
            round(size_distance, 2)
            if size_distance is not None
            else None
        ),
        pixels_per_cm=round(
            pixels_per_cm,
            4,
        ),
        annotated_image=encoded_image,
        inference_variant=inference_variant,
        **tracking_data,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("GARMENT_FEATURE_PORT", "8013")),
    )
