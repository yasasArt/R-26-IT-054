import base64
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
# Project configuration
# ==================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

TRAINING_RESULTS = (
    PROJECT_ROOT
    / "training_results"
)

ALLOWED_GARMENT_TYPES = {
    "tshirt",
    "shirt",
    "trouser",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


# ==================================================
# Find trained model
# ==================================================

def find_latest_model() -> Path:
    model_files = list(
        TRAINING_RESULTS.rglob("best.pt")
    )

    if not model_files:
        raise FileNotFoundError(
            "training_results folder එක "
            "ඇතුළේ best.pt model එක "
            "හමු වුණේ නැහැ."
        )

    latest_model = max(
        model_files,
        key=lambda path: path.stat().st_mtime,
    )

    return latest_model


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
print("Garment Size Backend")
print("=" * 65)
print(f"Project root : {PROJECT_ROOT}")
print(f"Model        : {MODEL_PATH}")
print(f"Device       : {DEVICE_NAME}")
print("Loading YOLO model...")

model = YOLO(str(MODEL_PATH))

print("YOLO model loaded successfully.")
print("=" * 65)


# ==================================================
# FastAPI application
# ==================================================

app = FastAPI(
    title="Garment Size Detection API",
    version="1.0.0",
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

def encode_image_to_base64(
    image: np.ndarray,
) -> str:
    success, encoded_image = cv2.imencode(
        ".jpg",
        image,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            92,
        ],
    )

    if not success:
        raise ValueError(
            "Could not encode result image."
        )

    base64_image = base64.b64encode(
        encoded_image.tobytes()
    ).decode("utf-8")

    return base64_image


def empty_detection_response(
    garment_type: str,
    message: str,
) -> dict:
    return {
        "detected": False,
        "garment_type": garment_type,
        "confidence": None,
        "width_cm": None,
        "length_cm": None,
        "width_pixels": None,
        "length_pixels": None,
        "size": None,
        "message": message,
        "annotated_image": None,
    }


# ==================================================
# API endpoints
# ==================================================

@app.get("/")
def root():
    return {
        "message": (
            "Garment Size Detection "
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
    }


@app.post("/measure")
async def measure_garment(
    file: UploadFile = File(...),
    garment_type: str = Form(...),
):
    garment_type = garment_type.lower().strip()

    if garment_type not in ALLOWED_GARMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid garment type. "
                "Use tshirt, shirt or trouser."
            ),
        )

    if file.content_type not in {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type.",
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "Image is too large. "
                "Maximum size is 10 MB."
            ),
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
            detail="Could not decode image.",
        )

    try:
        predictions = model.predict(
            source=image,
            imgsz=640,
            conf=0.50,
            device=DEVICE,
            retina_masks=True,
            verbose=False,
        )
    except Exception as error:
        print(f"YOLO inference error: {error}")

        raise HTTPException(
            status_code=500,
            detail="YOLO inference failed.",
        ) from error

    if not predictions:
        return empty_detection_response(
            garment_type,
            "No garment was detected.",
        )

    result = predictions[0]

    if (
        result.boxes is None
        or len(result.boxes) == 0
        or result.masks is None
        or len(result.masks.data) == 0
    ):
        return empty_detection_response(
            garment_type,
            (
                "No garment mask was detected. "
                "Place the garment clearly "
                "inside the camera view."
            ),
        )

        # ==================================================
    # Combine every detected garment mask
    # ==================================================

    mask_data = result.masks.data

    combined_mask_tensor = torch.any(
        mask_data > 0.5,
        dim=0,
    )

    combined_mask = (
        combined_mask_tensor
        .cpu()
        .numpy()
        .astype(np.uint8)
        * 255
    )

    image_height, image_width = (
        image.shape[:2]
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

    # Remove small holes and noise
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

    contours, _ = cv2.findContours(
        combined_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if not contours:
        return empty_detection_response(
            garment_type,
            (
                "Garment detected, but combined "
                "mask contour could not be created."
            ),
        )

    # Join the points from all detected regions
    all_contour_points = np.vstack(
        contours
    )

    # One bounding box around every detected region
    x, y, box_width, box_height = (
        cv2.boundingRect(
            all_contour_points
        )
    )

    width_pixels = float(box_width)
    height_pixels = float(box_height)

    # Use the highest detection confidence
    confidence = float(
        result.boxes.conf.max().item()
    )

    # ==================================================
    # Draw one combined result
    # ==================================================

    annotated_image = image.copy()

    colour_mask = np.zeros_like(
        image
    )

    colour_mask[
        combined_mask > 0
    ] = (255, 0, 180)

    annotated_image = cv2.addWeighted(
        annotated_image,
        1.0,
        colour_mask,
        0.35,
        0,
    )

    # Draw all combined contours
    cv2.drawContours(
        annotated_image,
        contours,
        -1,
        (0, 255, 0),
        3,
    )

    # Draw one overall bounding rectangle
    cv2.rectangle(
        annotated_image,
        (x, y),
        (
            x + box_width,
            y + box_height,
        ),
        (255, 255, 0),
        4,
    )

    label_y = max(
        y - 15,
        35,
    )

    cv2.putText(
        annotated_image,
        (
            f"Combined garment "
            f"{confidence:.2f}"
        ),
        (x, label_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated_image,
        (
            f"Pixel width: "
            f"{width_pixels:.0f}px"
        ),
        (25, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated_image,
        (
            f"Pixel height: "
            f"{height_pixels:.0f}px"
        ),
        (25, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    encoded_result = (
        encode_image_to_base64(
            annotated_image
        )
    )

    detection_count = len(
        result.boxes
    )

    print(
        f"Combined detections: "
        f"{detection_count} | "
        f"Confidence: {confidence:.4f} | "
        f"Pixel width: {width_pixels:.0f} | "
        f"Pixel height: {height_pixels:.0f}"
    )

    return {
        "detected": True,
        "garment_type": garment_type,
        "confidence": confidence,

        "width_pixels": round(
            width_pixels,
            2,
        ),

        "height_pixels": round(
            height_pixels,
            2,
        ),

        # Physical measurements require calibration
        "width_cm": None,
        "length_cm": None,
        "size": None,

        "message": (
            f"{detection_count} detected "
            "garment regions were combined. "
            "Pixel dimensions calculated."
        ),

        "annotated_image": encoded_result,
    }

    # Remove small holes and noise
    kernel = np.ones(
        (5, 5),
        dtype=np.uint8,
    )

    selected_mask = cv2.morphologyEx(
        selected_mask,
        cv2.MORPH_CLOSE,
        kernel,
    )

    contours, _ = cv2.findContours(
        selected_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if not contours:
        return empty_detection_response(
            garment_type,
            (
                "Garment was detected, but "
                "the mask contour could not "
                "be calculated."
            ),
        )

    largest_contour = max(
        contours,
        key=cv2.contourArea,
    )

    contour_area = cv2.contourArea(
        largest_contour
    )

    minimum_area = (
        image_height
        * image_width
        * 0.02
    )

    if contour_area < minimum_area:
        return empty_detection_response(
            garment_type,
            (
                "Detected garment is too small. "
                "Move the garment closer."
            ),
        )

    # Rotated rectangle around garment
    rotated_rectangle = cv2.minAreaRect(
        largest_contour
    )

    rectangle_points = cv2.boxPoints(
        rotated_rectangle
    )

    rectangle_points = np.int32(
        rectangle_points
    )

    rectangle_width, rectangle_height = (
        rotated_rectangle[1]
    )

    length_pixels = max(
        rectangle_width,
        rectangle_height,
    )

    width_pixels = min(
        rectangle_width,
        rectangle_height,
    )

    # Draw prediction result
    annotated_image = result.plot()

    cv2.drawContours(
        annotated_image,
        [largest_contour],
        -1,
        (0, 255, 0),
        3,
    )

    cv2.polylines(
        annotated_image,
        [rectangle_points],
        True,
        (255, 255, 0),
        3,
    )

    cv2.putText(
        annotated_image,
        (
            f"Confidence: "
            f"{confidence:.2f}"
        ),
        (25, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated_image,
        (
            f"Pixel width: "
            f"{width_pixels:.1f}"
        ),
        (25, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        annotated_image,
        (
            f"Pixel length: "
            f"{length_pixels:.1f}"
        ),
        (25, 115),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    encoded_result = (
        encode_image_to_base64(
            annotated_image
        )
    )

    print(
        f"Detected: {garment_type} | "
        f"Confidence: {confidence:.4f} | "
        f"Width pixels: {width_pixels:.1f} | "
        f"Length pixels: {length_pixels:.1f}"
    )

    return {
        "detected": True,
        "garment_type": garment_type,
        "confidence": confidence,

        # Real centimetres require calibration
        "width_cm": None,
        "length_cm": None,

        "width_pixels": round(
            float(width_pixels),
            2,
        ),
        "length_pixels": round(
            float(length_pixels),
            2,
        ),

        "size": None,

        "message": (
            "Garment detected successfully. "
            "Physical size calibration is "
            "required to calculate centimetres."
        ),

        "annotated_image": encoded_result,
    }