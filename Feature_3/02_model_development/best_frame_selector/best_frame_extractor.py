"""Extract the highest-confidence READY frame from each garment event in a video.

This script uses the frozen MobileNetV3-Small checkpoint from the Best Frame
Selector project. It samples the input video at 3 FPS by default, matching the
frame-extraction rate used during model development.
"""

from __future__ import annotations


import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms



DEFAULT_THRESHOLD = 0.74
DEFAULT_SAMPLE_FPS = 3.0
DEFAULT_END_GAP = 5
DEFAULT_PREVIEW_WIDTH = 1600
DEFAULT_PREVIEW_HEIGHT = 900
DEFAULT_IMAGE_FORMAT = "png"


@dataclass
class Candidate:
    frame: np.ndarray
    source_frame_number: int
    timestamp_seconds: float
    p_invalid: float
    p_not_ready: float
    p_ready: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract one best READY frame from each garment event."
    )
    parser.add_argument("--video", required=True, help="Input video path")
    parser.add_argument(
        "--model", default="models/best_model.pt", help="Checkpoint path"
    )
    parser.add_argument(
        "--output-dir", default="outputs", help="Directory for images and CSV"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Frozen READY probability threshold (default: 0.74)",
    )
    parser.add_argument(
        "--sample-fps",
        type=float,
        default=DEFAULT_SAMPLE_FPS,
        help="Inference sampling rate (default: 3 FPS)",
    )
    parser.add_argument(
        "--end-gap-frames",
        type=int,
        default=DEFAULT_END_GAP,
        help="Below-threshold sampled frames required to close an event",
    )
    parser.add_argument(
        "--min-ready-frames",
        type=int,
        default=1,
        help="Minimum READY candidates required before saving an event",
    )
    parser.add_argument(
        "--preview", action="store_true", help="Show a live preview; press Q to stop"
    )
    parser.add_argument(
        "--preview-width",
        type=int,
        default=DEFAULT_PREVIEW_WIDTH,
        help="Maximum preview width without cropping (default: 1600)",
    )
    parser.add_argument(
        "--preview-height",
        type=int,
        default=DEFAULT_PREVIEW_HEIGHT,
        help="Maximum preview height without cropping (default: 900)",
    )
    parser.add_argument(
        "--image-format",
        choices=("png", "jpg"),
        default=DEFAULT_IMAGE_FORMAT,
        help="Selected-frame format: lossless PNG or quality-100 JPG (default: png)",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 0.0 <= args.threshold <= 1.0:
        raise ValueError("--threshold must be between 0 and 1")
    if args.sample_fps <= 0:
        raise ValueError("--sample-fps must be greater than 0")
    if args.end_gap_frames < 1:
        raise ValueError("--end-gap-frames must be at least 1")
    if args.min_ready_frames < 1:
        raise ValueError("--min-ready-frames must be at least 1")
    if args.preview_width < 1:
        raise ValueError("--preview-width must be at least 1")
    if args.preview_height < 1:
        raise ValueError("--preview-height must be at least 1")


def create_letterbox_preview(
    frame: np.ndarray,
    max_width: int,
    max_height: int,
) -> np.ndarray:
    """Fit a frame inside a preview canvas without cropping or distortion.

    Only this display copy is resized. The original decoded video frame remains
    unchanged and is the frame stored in each Candidate and written to disk.
    """
    original_height, original_width = frame.shape[:2]
    scale = min(
        max_width / original_width,
        max_height / original_height,
        1.0,
    )

    preview_width = max(1, round(original_width * scale))
    preview_height = max(1, round(original_height * scale))

    if (preview_width, preview_height) == (original_width, original_height):
        resized = frame.copy()
    else:
        resized = cv2.resize(
            frame,
            (preview_width, preview_height),
            interpolation=cv2.INTER_AREA,
        )

    canvas = np.zeros((max_height, max_width, 3), dtype=np.uint8)
    x_offset = (max_width - preview_width) // 2
    y_offset = (max_height - preview_height) // 2
    canvas[
        y_offset : y_offset + preview_height,
        x_offset : x_offset + preview_width,
    ] = resized
    return canvas


def load_checkpoint(path: Path, device: torch.device) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")

    # This project checkpoint is trusted and may contain training metadata that
    # is not accepted by PyTorch's restricted weights-only loader.
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ValueError("Checkpoint does not contain 'model_state_dict'")
    return checkpoint


def build_model(checkpoint: dict, device: torch.device) -> torch.nn.Module:
    model_name = checkpoint.get("model_name", "mobilenet_v3_small")
    if model_name != "mobilenet_v3_small":
        raise ValueError(f"Unsupported model architecture: {model_name}")

    class_to_idx = checkpoint.get(
        "class_to_idx", {"INVALID": 0, "NOT_READY": 1, "READY": 2}
    )
    model = models.mobilenet_v3_small(weights=None)
    model.classifier[3] = torch.nn.Linear(
        model.classifier[3].in_features, len(class_to_idx)
    )
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.to(device)
    model.eval()
    return model


def build_transform(checkpoint: dict) -> transforms.Compose:
    image_size = int(checkpoint.get("image_size", 224))
    normalization = checkpoint.get("normalization", {})
    mean = normalization.get("mean", [0.485, 0.456, 0.406])
    std = normalization.get("std", [0.229, 0.224, 0.225])
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )


def normalize_class_mapping(raw_mapping: dict) -> Dict[str, int]:
    mapping = {str(name).upper(): int(index) for name, index in raw_mapping.items()}
    required = {"INVALID", "NOT_READY", "READY"}
    if set(mapping) != required:
        raise ValueError(
            "Expected checkpoint classes INVALID, NOT_READY and READY; "
            f"found {sorted(mapping)}"
        )
    return mapping


def predict(
    frame_bgr: np.ndarray,
    model: torch.nn.Module,
    transform: transforms.Compose,
    class_to_idx: Dict[str, int],
    device: torch.device,
) -> Tuple[float, float, float]:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    tensor = transform(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)

    with torch.inference_mode():
        if device.type == "cuda":
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                logits = model(tensor)
        else:
            logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1)[0].float().cpu().numpy()

    return (
        float(probabilities[class_to_idx["INVALID"]]),
        float(probabilities[class_to_idx["NOT_READY"]]),
        float(probabilities[class_to_idx["READY"]]),
    )


def save_event(
    event_number: int,
    candidate: Candidate,
    candidate_count: int,
    selected_dir: Path,
    video_stem: str,
    image_format: str,
) -> dict:
    event_id = f"event_{event_number:03d}"
    image_name = f"{video_stem}_{event_id}_best.{image_format}"
    image_path = selected_dir / image_name

    if image_format == "png":
        write_parameters = [cv2.IMWRITE_PNG_COMPRESSION, 3]
    else:
        write_parameters = [cv2.IMWRITE_JPEG_QUALITY, 100]

    # candidate.frame is the untouched, full-resolution decoded source frame.
    if not cv2.imwrite(str(image_path), candidate.frame, write_parameters):
        raise OSError(f"Could not save image: {image_path}")

    image_height, image_width = candidate.frame.shape[:2]

    return {
        "event_id": event_id,
        "selected_image": str(image_path.resolve()),
        "source_frame_number": candidate.source_frame_number,
        "timestamp_seconds": f"{candidate.timestamp_seconds:.3f}",
        "p_invalid": f"{candidate.p_invalid:.6f}",
        "p_not_ready": f"{candidate.p_not_ready:.6f}",
        "p_ready": f"{candidate.p_ready:.6f}",
        "ready_candidate_count": candidate_count,
        "image_width": image_width,
        "image_height": image_height,
        "image_format": image_format,
    }


def main() -> int:
    args = parse_args()
    validate_args(args)

    video_path = Path(args.video).expanduser().resolve()
    model_path = Path(args.model).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    selected_dir = output_dir / "selected_frames"
    selected_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = load_checkpoint(model_path, device)
    class_to_idx = normalize_class_mapping(
        checkpoint.get("class_to_idx", {"INVALID": 0, "NOT_READY": 1, "READY": 2})
    )
    model = build_model(checkpoint, device)
    transform = build_transform(checkpoint)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {video_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if source_fps <= 0:
        capture.release()
        raise ValueError("The video does not report a valid FPS value")

    sample_interval = max(1, round(source_fps / args.sample_fps))
    effective_sample_fps = source_fps / sample_interval
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_frame_number = -1
    sampled_frames = 0
    below_threshold_count = 0
    candidate_count = 0
    event_number = 0
    best: Optional[Candidate] = None
    results = []

    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Source FPS: {source_fps:.3f}")
    print(f"Source resolution: {source_width} x {source_height}")
    print(f"Effective sample FPS: {effective_sample_fps:.3f}")
    print(f"READY threshold: {args.threshold:.2f}")
    print(f"Saved image format: {args.image_format.upper()}")

    stopped_by_user = False
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            source_frame_number += 1
            if source_frame_number % sample_interval != 0:
                continue

            sampled_frames += 1
            # Keep an untouched copy for candidate selection and output.
            original_frame = frame.copy()
            timestamp_seconds = source_frame_number / source_fps
            p_invalid, p_not_ready, p_ready = predict(
                original_frame, model, transform, class_to_idx, device
            )

            if p_ready >= args.threshold:
                below_threshold_count = 0
                candidate_count += 1
                if best is None or p_ready > best.p_ready:
                    best = Candidate(
                        frame=original_frame.copy(),
                        source_frame_number=source_frame_number,
                        timestamp_seconds=timestamp_seconds,
                        p_invalid=p_invalid,
                        p_not_ready=p_not_ready,
                        p_ready=p_ready,
                    )
            elif best is not None:
                below_threshold_count += 1
                if below_threshold_count >= args.end_gap_frames:
                    if candidate_count >= args.min_ready_frames:
                        event_number += 1
                        row = save_event(
                            event_number,
                            best,
                            candidate_count,
                            selected_dir,
                            video_path.stem,
                            args.image_format,
                        )
                        results.append(row)
                        print(
                            f"Saved {row['event_id']}: frame "
                            f"{row['source_frame_number']}, "
                            f"p_ready={row['p_ready']}"
                        )
                    best = None
                    candidate_count = 0
                    below_threshold_count = 0

            if args.preview:
                label = "READY" if p_ready >= args.threshold else "SEARCHING"
                colour = (0, 220, 0) if label == "READY" else (0, 180, 255)
                preview = create_letterbox_preview(
                    original_frame,
                    args.preview_width,
                    args.preview_height,
                )
                cv2.putText(
                    preview,
                    f"{label}  p_ready={p_ready:.3f}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    colour,
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("Best Frame Extractor - press Q to stop", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    stopped_by_user = True
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()

    # Flush an unfinished READY period at the end of the video or after Q.
    if best is not None and candidate_count >= args.min_ready_frames:
        event_number += 1
        row = save_event(
            event_number,
            best,
            candidate_count,
            selected_dir,
            video_path.stem,
            args.image_format,
        )
        results.append(row)
        print(
            f"Saved {row['event_id']}: frame {row['source_frame_number']}, "
            f"p_ready={row['p_ready']}"
        )

    csv_path = output_dir / "extraction_results.csv"
    fieldnames = [
        "event_id",
        "selected_image",
        "source_frame_number",
        "timestamp_seconds",
        "p_invalid",
        "p_not_ready",
        "p_ready",
        "ready_candidate_count",
        "image_width",
        "image_height",
        "image_format",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "video": str(video_path),
        "model": str(model_path),
        "device": str(device),
        "strategy": "visual_only",
        "ready_threshold": args.threshold,
        "source_fps": source_fps,
        "source_width": source_width,
        "source_height": source_height,
        "requested_sample_fps": args.sample_fps,
        "effective_sample_fps": effective_sample_fps,
        "end_gap_frames": args.end_gap_frames,
        "min_ready_frames": args.min_ready_frames,
        "sampled_frames": sampled_frames,
        "events_saved": len(results),
        "saved_image_format": args.image_format,
        "preview_width": args.preview_width,
        "preview_height": args.preview_height,
        "stopped_by_user": stopped_by_user,
        "test_split_used": False,
    }
    summary_path = output_dir / "extraction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nCompleted. Events saved: {len(results)}")
    print(f"Selected frames: {selected_dir}")
    print(f"Results CSV: {csv_path}")
    print(f"Summary JSON: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
