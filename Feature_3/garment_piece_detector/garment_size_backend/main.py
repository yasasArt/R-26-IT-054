import base64
import json
import math
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import torch
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

SIZE_CHART_PATH = (
    BACKEND_DIRECTORY
    / "size_chart.json"
)

MARKER_SIZE_CM = 10.0
MARKER_ID = 0

# A low inference threshold helps dark garments reach the validation stage.
# A result is never counted from confidence alone; geometry and temporal
# consistency are checked below.
INFERENCE_CONFIDENCE = 0.15
MINIMUM_CONFIDENCE = 0.30
MINIMUM_MASK_AREA_RATIO = 0.025
MAXIMUM_MASK_AREA_RATIO = 0.55

INFERENCE_IMAGE_SIZE = 768

# Automatic garment lifecycle settings. At an approximately 450 ms frontend
# scan interval, three stable frames take about 1.35 seconds. Four empty frames
# are required before the same station is armed for the next garment.
STABLE_FRAMES_REQUIRED = 3
EMPTY_FRAMES_TO_REARM = 4
MAX_STABLE_WIDTH_CHANGE_CM = 2.0
MAX_STABLE_LENGTH_CHANGE_CM = 2.5

# These margins are used only to reject obviously incomplete T-shirt masks.
# The actual size label is still obtained from size_chart.json.
TSHIRT_EXTRA_WIDTH_MARGIN_CM = 10.0
TSHIRT_EXTRA_LENGTH_MARGIN_CM = 15.0
TSHIRT_MIN_WIDTH_LENGTH_RATIO = 0.48
TSHIRT_MAX_WIDTH_LENGTH_RATIO = 1.10

ROI_MARGIN_X = 0.04
ROI_MARGIN_Y = 0.04

SIZE_DISTANCE_LIMIT_CM = 6.0

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
        maxlen=STABLE_FRAMES_REQUIRED
    ),
    "empty_frames": 0,
    "current_garment_counted": False,
    "counts": empty_count_table(),
    "history": deque(maxlen=50),
}


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

    return {
        "tracking_state": (
            TRACKER["tracking_state"]
        ),
        "stable_count": len(
            TRACKER["stable_samples"]
        ),
        "stable_required": (
            STABLE_FRAMES_REQUIRED
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
    }


def update_tracker_non_ready(
    state: str,
) -> dict:
    """Update lifecycle for an invalid or empty camera frame."""
    with TRACKER_LOCK:
        TRACKER["stable_samples"].clear()

        if state == "NO_GARMENT":
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
    return (
        previous["garment_type"]
        == current["garment_type"]
        and previous["size"]
        == current["size"]
        and abs(
            previous["width_cm"]
            - current["width_cm"]
        ) <= MAX_STABLE_WIDTH_CHANGE_CM
        and abs(
            previous["length_cm"]
            - current["length_cm"]
        ) <= MAX_STABLE_LENGTH_CHANGE_CM
    )


def update_tracker_ready(
    *,
    garment_type: str,
    size: str,
    width_cm: float,
    length_cm: float,
    confidence: float,
) -> dict:
    """Count one garment only after consistent frames and one removal."""
    current_sample = {
        "garment_type": garment_type,
        "size": size,
        "width_cm": float(width_cm),
        "length_cm": float(length_cm),
        "confidence": float(confidence),
    }

    with TRACKER_LOCK:
        TRACKER["empty_frames"] = 0

        if TRACKER[
            "current_garment_counted"
        ]:
            TRACKER[
                "tracking_state"
            ] = "WAIT_REMOVAL"
            return tracker_snapshot()

        samples = TRACKER[
            "stable_samples"
        ]

        if (
            samples
            and not stable_samples_are_consistent(
                samples[-1],
                current_sample,
            )
        ):
            samples.clear()

        samples.append(current_sample)
        TRACKER[
            "tracking_state"
        ] = "STABILIZING"

        if len(samples) < STABLE_FRAMES_REQUIRED:
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
        final_confidence = float(
            np.median(confidences)
        )

        count_size = (
            size
            if size in COUNTED_SIZES
            else "UNKNOWN"
        )

        TRACKER["counts"][garment_type][
            count_size
        ] += 1

        record = {
            "id": datetime.now(
                timezone.utc
            ).isoformat(),
            "garment_type": garment_type,
            "size": count_size,
            "width_cm": round(
                final_width,
                2,
            ),
            "length_cm": round(
                final_length,
                2,
            ),
            "confidence": round(
                final_confidence,
                4,
            ),
        }

        TRACKER["history"].appendleft(
            record
        )
        TRACKER[
            "current_garment_counted"
        ] = True
        TRACKER[
            "tracking_state"
        ] = "COUNTED"

        return tracker_snapshot(
            counted_now=True
        )


# ==================================================
# Find latest YOLO model
# ==================================================

def find_latest_model() -> Path:
    model_files = list(
        TRAINING_RESULTS.rglob("best.pt")
    )

    if not model_files:
        raise FileNotFoundError(
            "No best.pt model was found inside "
            "training_results."
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
    f"Marker physical size: "
    f"{MARKER_SIZE_CM} cm"
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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
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


# ==================================================
# ArUco calibration
# ==================================================

def detect_pixels_per_cm(
    image: np.ndarray,
):
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    dictionary = (
        cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
    )

    if hasattr(
        cv2.aruco,
        "ArucoDetector",
    ):
        parameters = (
            cv2.aruco.DetectorParameters()
        )

        detector = (
            cv2.aruco.ArucoDetector(
                dictionary,
                parameters,
            )
        )

        corners, ids, _ = (
            detector.detectMarkers(gray)
        )
    else:
        parameters = (
            cv2.aruco.DetectorParameters_create()
        )

        corners, ids, _ = (
            cv2.aruco.detectMarkers(
                gray,
                dictionary,
                parameters=parameters,
            )
        )

    if ids is None:
        return None, None

    marker_ids = ids.flatten()

    if MARKER_ID not in marker_ids:
        return None, None

    marker_index = int(
        np.where(
            marker_ids == MARKER_ID
        )[0][0]
    )

    marker_corners = (
        corners[marker_index][0]
        .astype(np.float32)
    )

    side_lengths = []

    for index in range(4):
        current_point = (
            marker_corners[index]
        )

        next_point = (
            marker_corners[
                (index + 1) % 4
            ]
        )

        side_lengths.append(
            float(
                np.linalg.norm(
                    current_point
                    - next_point
                )
            )
        )

    average_side_pixels = float(
        np.mean(side_lengths)
    )

    pixels_per_cm = (
        average_side_pixels
        / MARKER_SIZE_CM
    )

    return (
        pixels_per_cm,
        marker_corners,
    )


def select_best_garment_mask(
    result,
    image_shape,
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

        if (
            confidence
            < MINIMUM_CONFIDENCE
        ):
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

    return (
        cropped_image,
        cropped_mask,
    )


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


def calculate_straight_measurements(
    mask: np.ndarray,
    garment_type: str,
):
    y_values, x_values = np.where(
        mask > 0
    )

    top_y = int(
        y_values.min()
    )

    bottom_y = int(
        y_values.max()
    )

    total_height = (
        bottom_y - top_y + 1
    )

    if garment_type in {
        "tshirt",
        "shirt",
    }:
        upper_limit = int(
            top_y
            + total_height * 0.35
        )

        upper_widths = []

        for row in range(
            top_y,
            upper_limit + 1,
        ):
            row_x = np.where(
                mask[row] > 0
            )[0]

            if len(row_x) >= 2:
                upper_widths.append(
                    (
                        row,
                        int(
                            row_x.max()
                            - row_x.min()
                            + 1
                        ),
                    )
                )

        maximum_upper_width = max(
            width
            for _, width
            in upper_widths
        )

        shoulder_threshold = (
            maximum_upper_width * 0.70
        )

        shoulder_y = next(
            row
            for row, width
            in upper_widths
            if width
            >= shoulder_threshold
        )

        garment_height_pixels = (
            bottom_y - shoulder_y + 1
        )

        chest_start = int(
            shoulder_y
            + garment_height_pixels * 0.25
        )

        chest_end = int(
            shoulder_y
            + garment_height_pixels * 0.35
        )

        (
            width_pixels,
            width_y,
            left_x,
            right_x,
        ) = row_measurement(
            mask,
            chest_start,
            chest_end,
        )

        height_start_y = shoulder_y

    else:
        garment_height_pixels = (
            bottom_y - top_y + 1
        )

        waist_start = int(
            top_y
            + garment_height_pixels * 0.03
        )

        waist_end = int(
            top_y
            + garment_height_pixels * 0.12
        )

        (
            width_pixels,
            width_y,
            left_x,
            right_x,
        ) = row_measurement(
            mask,
            waist_start,
            waist_end,
        )

        height_start_y = top_y

    centre_x = int(
        (
            x_values.min()
            + x_values.max()
        ) / 2
    )

    measurement_points = {
        "width_start": (
            left_x,
            width_y,
        ),
        "width_end": (
            right_x,
            width_y,
        ),
        "height_start": (
            centre_x,
            height_start_y,
        ),
        "height_end": (
            centre_x,
            bottom_y,
        ),
    }

    return (
        float(width_pixels),
        float(garment_height_pixels),
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
            "Only part of the garment was segmented: invalid silhouette ratio.",
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
        "marker_size_cm": MARKER_SIZE_CM,
        "inference_image_size": INFERENCE_IMAGE_SIZE,
        "stable_frames_required": STABLE_FRAMES_REQUIRED,
    }


@app.get("/counts")
def get_counts():
    """Return size-wise totals and the most recent counted garments."""
    with TRACKER_LOCK:
        return tracker_snapshot()


@app.post("/counts/reset")
def reset_counts():
    """Start a new counting session without restarting the API."""
    with TRACKER_LOCK:
        TRACKER["tracking_state"] = "EMPTY"
        TRACKER["stable_samples"].clear()
        TRACKER["empty_frames"] = 0
        TRACKER["current_garment_counted"] = False
        TRACKER["counts"] = empty_count_table()
        TRACKER["history"].clear()
        return tracker_snapshot()


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

    detection_zone, _ = (
        extract_detection_zone(image)
    )

    (
        pixels_per_cm,
        marker_corners,
    ) = detect_pixels_per_cm(
        detection_zone
    )

    if pixels_per_cm is None:
        tracking_data = update_tracker_non_ready(
            "MARKER_MISSING"
        )
        return make_response(
            state="MARKER_MISSING",
            message=(
                "Calibration marker not detected. "
                "Keep the complete marker visible."
            ),
            garment_type=garment_type,
            **tracking_data,
        )

    predictions = model.predict(
        source=detection_zone,
        imgsz=INFERENCE_IMAGE_SIZE,
        conf=INFERENCE_CONFIDENCE,
        device=DEVICE,
        half=torch.cuda.is_available(),
        retina_masks=True,
        verbose=False,
    )

    if not predictions:
        tracking_data = update_tracker_non_ready(
            "NO_GARMENT"
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
    )
    
    if garment_mask is None:
        tracking_data = update_tracker_non_ready(
            mask_state
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

    (
        upright_image,
        upright_mask,
    ) = rotate_image_and_mask(
        detection_zone,
        garment_mask,
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
            "MEASUREMENT_FAILED"
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
            "PARTIAL_GARMENT"
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
        **tracking_data,
    )