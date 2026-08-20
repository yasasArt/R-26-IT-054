import base64
import json
import math
from pathlib import Path

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

MINIMUM_CONFIDENCE = 0.70
MINIMUM_MASK_AREA_RATIO = 0.04
MAXIMUM_MASK_AREA_RATIO = 0.90

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


# ==================================================
# Mask processing
# ==================================================

def create_combined_mask(
    result,
    image_shape,
):
    image_height, image_width = (
        image_shape[:2]
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
    )

    valid_indices = torch.where(
        confidences
        >= MINIMUM_CONFIDENCE
    )[0]

    if len(valid_indices) == 0:
        return (
            "LOW_CONFIDENCE",
            (
                "Garment confidence is too low. "
                "Adjust the garment and lighting."
            ),
            None,
            None,
        )

    selected_masks = (
        result.masks.data[
            valid_indices
        ]
    )

    combined_tensor = torch.any(
        selected_masks > 0.5,
        dim=0,
    )

    combined_mask = (
        combined_tensor
        .cpu()
        .numpy()
        .astype(np.uint8)
        * 255
    )

    if combined_mask.shape != (
        image_height,
        image_width,
    ):
        combined_mask = cv2.resize(
            combined_mask,
            (
                image_width,
                image_height,
            ),
            interpolation=cv2.INTER_NEAREST,
        )

    kernel = np.ones(
        (7, 7),
        dtype=np.uint8,
    )

    combined_mask = cv2.morphologyEx(
        combined_mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2,
    )

    component_count, labels, stats, _ = (
        cv2.connectedComponentsWithStats(
            combined_mask,
            connectivity=8,
        )
    )

    image_area = float(
        image_height * image_width
    )

    components = []

    for label in range(
        1,
        component_count,
    ):
        area = int(
            stats[
                label,
                cv2.CC_STAT_AREA,
            ]
        )

        if area >= (
            image_area * 0.003
        ):
            components.append(
                (label, area)
            )

    if not components:
        return (
            "NO_GARMENT",
            "No garment detected.",
            None,
            None,
        )

    components.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    if (
        len(components) > 1
        and components[1][1]
        >= components[0][1] * 0.25
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

    largest_label = components[0][0]

    final_mask = (
        labels == largest_label
    ).astype(np.uint8) * 255

    mask_area = float(
        np.count_nonzero(final_mask)
    )

    area_ratio = (
        mask_area / image_area
    )

    if (
        area_ratio
        < MINIMUM_MASK_AREA_RATIO
    ):
        return (
            "NO_GARMENT",
            (
                "No valid garment detected. "
                "Move the garment into the zone."
            ),
            None,
            None,
        )

    if (
        area_ratio
        > MAXIMUM_MASK_AREA_RATIO
    ):
        return (
            "PARTIAL_GARMENT",
            (
                "Garment is too close or fills "
                "the complete camera view."
            ),
            None,
            None,
        )

    border_size = 6

    touches_boundary = any([
        np.any(
            final_mask[
                :border_size,
                :
            ]
        ),
        np.any(
            final_mask[
                -border_size:,
                :
            ]
        ),
        np.any(
            final_mask[
                :,
                :border_size
            ]
        ),
        np.any(
            final_mask[
                :,
                -border_size:
            ]
        ),
    ])

    if touches_boundary:
        return (
            "PARTIAL_GARMENT",
            (
                "Garment is not fully inside "
                "the detection zone."
            ),
            None,
            None,
        )

    best_confidence = float(
        confidences[
            valid_indices
        ].max().item()
    )

    return (
        "VALID",
        "Garment mask is valid.",
        final_mask,
        best_confidence,
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
    }


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
        return make_response(
            state="MARKER_MISSING",
            message=(
                "Calibration marker not detected. "
                "Keep the complete marker visible."
            ),
            garment_type=garment_type,
        )

    predictions = model.predict(
        source=detection_zone,
        imgsz=640,
        conf=0.50,
        device=DEVICE,
        retina_masks=True,
        verbose=False,
    )

    if not predictions:
        return make_response(
            state="NO_GARMENT",
            message="No garment detected.",
            garment_type=garment_type,
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
        )

    result = predictions[0]

    (
        mask_state,
        mask_message,
        garment_mask,
        confidence,
    ) = create_combined_mask(
        result,
        detection_zone.shape,
    )

    if garment_mask is None:
        return make_response(
            state=mask_state,
            message=mask_message,
            garment_type=garment_type,
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
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
        return make_response(
            state="MEASUREMENT_FAILED",
            message=str(error),
            garment_type=garment_type,
            pixels_per_cm=round(
                pixels_per_cm,
                4,
            ),
        )

    width_cm = (
        width_pixels
        / pixels_per_cm
    )

    height_cm = (
        height_pixels
        / pixels_per_cm
    )

    size, size_distance = classify_size(
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
        pixels_per_cm=round(
            pixels_per_cm,
            4,
        ),
        annotated_image=encoded_image,
    )