from pathlib import Path
import sys

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import mobilenet_v3_small
from ultralytics import YOLO


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

FRAME_MODEL_PATH = BASE_DIR / "models" / "best_model.pt"
STYLE_MODEL_PATH = BASE_DIR / "models" / "best.pt"
VIDEO_PATH = BASE_DIR / "dataset" / "videos" / "v25.mp4"
OUTPUT_DIR = BASE_DIR / "outputs"

# Threshold selected during Phase 3B validation
READY_THRESHOLD = 0.74

# Run frame-selector inference at the same 3 FPS used for extraction
TARGET_INFERENCE_FPS = 3.0

# Minimum YOLO style confidence
STYLE_CONFIDENCE_THRESHOLD = 0.50

# Display video during processing
SHOW_VIDEO = True

# Automatically save the selected frame
SAVE_BEST_FRAME = True


# ============================================================
# MODEL LOADING
# ============================================================

def load_frame_selector(model_path: Path, device: torch.device):
    """Load the trained MobileNetV3 frame-selection model."""

    if not model_path.exists():
        raise FileNotFoundError(
            f"Frame-selection model not found:\n{model_path}"
        )

    # weights_only=False is needed because this trusted checkpoint
    # contains additional training metadata such as pathlib objects.
    checkpoint = torch.load(
        model_path,
        map_location=device,
        weights_only=False
    )

    # Support checkpoints saved as complete nn.Module objects
    if isinstance(checkpoint, nn.Module):
        model = checkpoint
        class_to_idx = {
            "INVALID": 0,
            "NOT_READY": 1,
            "READY": 2
        }

        normalization = {
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225]
        }

        image_size = 224

    # Expected format of your best_model.pt checkpoint
    elif isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        class_to_idx = checkpoint.get(
            "class_to_idx",
            {
                "INVALID": 0,
                "NOT_READY": 1,
                "READY": 2
            }
        )

        image_size = int(checkpoint.get("image_size", 224))

        normalization = checkpoint.get(
            "normalization",
            {
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225]
            }
        )

        model_name = checkpoint.get(
            "model_name",
            "mobilenet_v3_small"
        )

        if model_name != "mobilenet_v3_small":
            raise ValueError(
                f"Unsupported model architecture: {model_name}"
            )

        number_of_classes = len(class_to_idx)

        # Reconstruct model architecture
        model = mobilenet_v3_small(weights=None)

        input_features = model.classifier[-1].in_features
        model.classifier[-1] = nn.Linear(
            input_features,
            number_of_classes
        )

        state_dict = checkpoint["model_state_dict"]

        # Handle models trained with DataParallel
        cleaned_state_dict = {
            key.removeprefix("module."): value
            for key, value in state_dict.items()
        }

        model.load_state_dict(cleaned_state_dict)

    else:
        raise ValueError(
            "Unsupported checkpoint format. Expected a complete PyTorch "
            "model or a dictionary containing 'model_state_dict'."
        )

    model = model.to(device)
    model.eval()

    idx_to_class = {
        index: class_name
        for class_name, index in class_to_idx.items()
    }

    mean = torch.tensor(
        normalization["mean"],
        dtype=torch.float32,
        device=device
    ).view(1, 3, 1, 1)

    std = torch.tensor(
        normalization["std"],
        dtype=torch.float32,
        device=device
    ).view(1, 3, 1, 1)

    return model, idx_to_class, image_size, mean, std


def load_style_model(model_path: Path):
    """Load the YOLO garment-style model."""

    if not model_path.exists():
        raise FileNotFoundError(
            f"Style model not found:\n{model_path}"
        )

    return YOLO(str(model_path))


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def preprocess_frame(
    frame: np.ndarray,
    image_size: int,
    mean: torch.Tensor,
    std: torch.Tensor,
    device: torch.device
):
    """Convert an OpenCV frame into a normalized PyTorch tensor."""

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    resized_frame = cv2.resize(
        rgb_frame,
        (image_size, image_size),
        interpolation=cv2.INTER_AREA
    )

    tensor = torch.from_numpy(resized_frame)
    tensor = tensor.permute(2, 0, 1)
    tensor = tensor.float().div(255.0)
    tensor = tensor.unsqueeze(0).to(device)

    # ImageNet normalization used during training
    tensor = (tensor - mean) / std

    return tensor


# ============================================================
# FRAME-SELECTOR INFERENCE
# ============================================================

def predict_frame_state(
    model,
    frame,
    image_size,
    mean,
    std,
    device,
    idx_to_class
):
    """Predict READY, NOT_READY and INVALID probabilities."""

    input_tensor = preprocess_frame(
        frame=frame,
        image_size=image_size,
        mean=mean,
        std=std,
        device=device
    )

    with torch.inference_mode():
        if device.type == "cuda":
            with torch.autocast(
                device_type="cuda",
                dtype=torch.float16
            ):
                logits = model(input_tensor)
        else:
            logits = model(input_tensor)

        # Handle models returning tuple/list outputs
        if isinstance(logits, (tuple, list)):
            logits = logits[0]

        probabilities = F.softmax(logits, dim=1)[0]

    scores = {
        idx_to_class[index].upper(): float(probabilities[index].item())
        for index in range(len(probabilities))
    }

    ready_score = scores.get("READY", 0.0)
    invalid_score = scores.get("INVALID", 0.0)
    not_ready_score = scores.get("NOT_READY", 0.0)

    # Use the validation-selected READY threshold
    if ready_score >= READY_THRESHOLD:
        state = "READY"
        confidence = ready_score
        color = (0, 255, 0)

    elif invalid_score >= not_ready_score:
        state = "INVALID"
        confidence = invalid_score
        color = (0, 0, 255)

    else:
        state = "NOT_READY"
        confidence = not_ready_score
        color = (0, 255, 255)

    return state, confidence, color, scores


# ============================================================
# YOLO STYLE INFERENCE
# ============================================================

def detect_style(style_model, frame, device):
    """Run YOLO classification or detection on the best frame."""

    yolo_device = 0 if device.type == "cuda" else "cpu"

    results = style_model.predict(
        source=frame,
        device=yolo_device,
        verbose=False
    )

    result = results[0]

    # YOLO classification model
    if result.probs is not None:
        class_index = int(result.probs.top1)
        style_name = result.names[class_index]
        confidence = float(result.probs.top1conf.item())

        return style_name, confidence

    # YOLO object-detection model
    if result.boxes is not None and len(result.boxes) > 0:
        confidences = result.boxes.conf
        best_detection_index = int(torch.argmax(confidences).item())

        best_box = result.boxes[best_detection_index]

        class_index = int(best_box.cls.item())
        confidence = float(best_box.conf.item())
        style_name = result.names[class_index]

        return style_name, confidence

    return "Unknown", 0.0


# ============================================================
# OVERLAY
# ============================================================

def draw_frame_information(
    frame,
    state,
    confidence,
    color,
    scores,
    processed_frame_number,
    video_frame_number
):
    """Add frame-selector information to the displayed frame."""

    display_frame = frame.copy()

    cv2.putText(
        display_frame,
        f"State: {state} ({confidence * 100:.1f}%)",
        (15, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2
    )

    cv2.putText(
        display_frame,
        (
            f"READY: {scores.get('READY', 0.0) * 100:.1f}% | "
            f"NOT_READY: {scores.get('NOT_READY', 0.0) * 100:.1f}% | "
            f"INVALID: {scores.get('INVALID', 0.0) * 100:.1f}%"
        ),
        (15, 68),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )

    cv2.putText(
        display_frame,
        (
            f"Video frame: {video_frame_number} | "
            f"Analyzed frames: {processed_frame_number}"
        ),
        (15, 98),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )

    return display_frame


# ============================================================
# MAIN PROCESS
# ============================================================

def main():
    print("Loading models... Please wait.")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    if device.type == "cuda":
        print(f"GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        print("CUDA GPU not detected. Using CPU.")

    try:
        (
            frame_model,
            idx_to_class,
            image_size,
            normalization_mean,
            normalization_std
        ) = load_frame_selector(
            FRAME_MODEL_PATH,
            device
        )

        style_model = load_style_model(STYLE_MODEL_PATH)

    except Exception as error:
        print(f"\nModel-loading error:\n{error}")
        sys.exit(1)

    print("Models loaded successfully.")
    print(f"Device: {device}")
    print(f"Class mapping: {idx_to_class}")
    print(f"Image size: {image_size}x{image_size}")
    print(f"READY threshold: {READY_THRESHOLD:.2f}")

    if not VIDEO_PATH.exists():
        print(f"\nVideo file not found:\n{VIDEO_PATH}")
        sys.exit(1)

    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        print(f"\nCould not open video:\n{VIDEO_PATH}")
        sys.exit(1)

    source_fps = cap.get(cv2.CAP_PROP_FPS)

    if source_fps <= 0:
        source_fps = 30.0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Example: 30 FPS source / 3 FPS inference = every 10th frame
    inference_interval = max(
        1,
        round(source_fps / TARGET_INFERENCE_FPS)
    )

    display_delay = max(1, round(1000 / source_fps))

    print(f"\nVideo: {VIDEO_PATH.name}")
    print(f"Source FPS: {source_fps:.2f}")
    print(f"Total frames: {total_frames}")
    print(f"Analyzing every {inference_interval} frame(s)")
    print("Press Q to stop processing early.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    video_frame_number = 0
    analyzed_frame_count = 0

    current_state = "NOT_READY"
    current_confidence = 0.0
    current_color = (0, 255, 255)

    current_scores = {
        "INVALID": 0.0,
        "NOT_READY": 0.0,
        "READY": 0.0
    }

    highest_ready_score = 0.0
    best_frame = None
    best_frame_number = None

    while cap.isOpened():
        success, frame = cap.read()

        if not success:
            break

        video_frame_number += 1

        should_analyze = (
            video_frame_number == 1 or
            (video_frame_number - 1) % inference_interval == 0
        )

        if should_analyze:
            analyzed_frame_count += 1

            (
                current_state,
                current_confidence,
                current_color,
                current_scores
            ) = predict_frame_state(
                model=frame_model,
                frame=frame,
                image_size=image_size,
                mean=normalization_mean,
                std=normalization_std,
                device=device,
                idx_to_class=idx_to_class
            )

            ready_score = current_scores.get("READY", 0.0)

            # Only consider frames that pass the validated READY threshold
            if (
                ready_score >= READY_THRESHOLD and
                ready_score > highest_ready_score
            ):
                highest_ready_score = ready_score
                best_frame = frame.copy()
                best_frame_number = video_frame_number

        if SHOW_VIDEO:
            display_frame = draw_frame_information(
                frame=frame,
                state=current_state,
                confidence=current_confidence,
                color=current_color,
                scores=current_scores,
                processed_frame_number=analyzed_frame_count,
                video_frame_number=video_frame_number
            )

            cv2.imshow(
                "Garment Best-Frame Selection",
                display_frame
            )

            pressed_key = cv2.waitKey(display_delay) & 0xFF

            if pressed_key == ord("q"):
                print("Processing stopped by user.")
                break

    cap.release()
    cv2.destroyAllWindows()

    # ========================================================
    # FINAL STYLE DETECTION
    # ========================================================

    if best_frame is None:
        print("\n" + "=" * 60)
        print("No frame passed the READY threshold.")
        print(f"Required READY probability: {READY_THRESHOLD * 100:.1f}%")
        print("=" * 60)
        return

    print("\n" + "=" * 60)
    print("BEST FRAME SELECTED")
    print(f"Video frame number : {best_frame_number}")
    print(f"READY probability  : {highest_ready_score * 100:.2f}%")
    print("Running garment-style detection...")

    style_name, style_confidence = detect_style(
        style_model,
        best_frame,
        device
    )

    if style_confidence >= STYLE_CONFIDENCE_THRESHOLD:
        final_style = style_name.upper()
        final_color = (0, 255, 0)

        print(f"Detected style     : {final_style}")
        print(f"Style confidence   : {style_confidence * 100:.2f}%")

        display_text = (
            f"{final_style} "
            f"({style_confidence * 100:.1f}%)"
        )
    else:
        final_style = "UNKNOWN"
        final_color = (0, 0, 255)

        print("Detected style     : UNKNOWN / LOW CONFIDENCE")
        print(
            f"Model prediction   : {style_name} "
            f"({style_confidence * 100:.2f}%)"
        )

        display_text = (
            f"UNKNOWN - {style_name} "
            f"({style_confidence * 100:.1f}%)"
        )

    print("=" * 60)

    result_frame = best_frame.copy()

    cv2.putText(
        result_frame,
        (
            f"READY: {highest_ready_score * 100:.1f}% | "
            f"Frame: {best_frame_number}"
        ),
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        result_frame,
        f"Style: {display_text}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        final_color,
        2
    )

    if SAVE_BEST_FRAME:
        output_path = (
            OUTPUT_DIR /
            f"{VIDEO_PATH.stem}_best_frame.jpg"
        )

        saved = cv2.imwrite(str(output_path), result_frame)

        if saved:
            print(f"\nBest frame saved to:\n{output_path}")
        else:
            print("\nWarning: Could not save the best-frame image.")

    if SHOW_VIDEO:
        cv2.imshow(
            "Final Result - Best Frame and Garment Style",
            result_frame
        )

        print("\nPress any key in the result window to close.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()