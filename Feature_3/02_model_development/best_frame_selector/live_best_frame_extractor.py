"""Live-camera Best Frame Extractor for Phase 5B.

Uses the frozen MobileNetV3-Small visual classifier and saves the highest-
confidence READY frame after each detected garment event finishes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass
class Candidate:
    frame: np.ndarray
    camera_frame_number: int
    elapsed_seconds: float
    captured_at_utc: str
    p_invalid: float
    p_not_ready: float
    p_ready: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select and save the best READY frame from a live camera."
    )
    parser.add_argument("--model", default="models/best_model.pt")
    parser.add_argument("--output-dir", default="outputs/live_run")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument(
        "--backend",
        choices=("auto", "dshow", "msmf"),
        default="auto",
        help="OpenCV camera backend; Windows users can try dshow",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--sample-fps", type=float, default=DEFAULT_SAMPLE_FPS)
    parser.add_argument("--end-gap-frames", type=int, default=DEFAULT_END_GAP)
    parser.add_argument("--min-ready-frames", type=int, default=1)
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=2.0,
        help="Camera warm-up time before event detection begins",
    )
    parser.add_argument(
        "--mirror",
        action="store_true",
        help="Mirror preview and inference frame (normally leave disabled)",
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
    if args.width < 1 or args.height < 1:
        raise ValueError("--width and --height must be positive")
    if args.warmup_seconds < 0:
        raise ValueError("--warmup-seconds cannot be negative")


def load_checkpoint(path: Path, device: torch.device) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ValueError("Checkpoint does not contain 'model_state_dict'")
    return checkpoint


def normalize_class_mapping(raw_mapping: dict) -> Dict[str, int]:
    mapping = {str(name).upper(): int(index) for name, index in raw_mapping.items()}
    required = {"INVALID", "NOT_READY", "READY"}
    if set(mapping) != required:
        raise ValueError(
            "Expected checkpoint classes INVALID, NOT_READY and READY; "
            f"found {sorted(mapping)}"
        )
    return mapping


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
    model.to(device).eval()
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


def predict(
    frame_bgr: np.ndarray,
    model: torch.nn.Module,
    transform: transforms.Compose,
    class_to_idx: Dict[str, int],
    device: torch.device,
) -> Tuple[float, float, float]:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    tensor = transform(Image.fromarray(rgb)).unsqueeze(0).to(device)
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


def open_camera(args: argparse.Namespace) -> cv2.VideoCapture:
    backend_map = {
        "auto": cv2.CAP_ANY,
        "dshow": getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY),
        "msmf": getattr(cv2, "CAP_MSMF", cv2.CAP_ANY),
    }
    capture = cv2.VideoCapture(args.camera, backend_map[args.backend])
    if not capture.isOpened():
        capture.release()
        raise OSError(
            f"Could not open camera {args.camera} with backend {args.backend}. "
            "Try --camera 1 or --backend dshow."
        )
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def save_event(
    event_number: int,
    candidate: Candidate,
    candidate_count: int,
    selected_dir: Path,
) -> dict:
    event_id = f"event_{event_number:03d}"
    image_name = f"live_{event_id}_best.jpg"
    image_path = selected_dir / image_name
    if not cv2.imwrite(str(image_path), candidate.frame):
        raise OSError(f"Could not save image: {image_path}")
    return {
        "event_id": event_id,
        "selected_image": str(image_path.resolve()),
        "camera_frame_number": candidate.camera_frame_number,
        "elapsed_seconds": f"{candidate.elapsed_seconds:.3f}",
        "captured_at_utc": candidate.captured_at_utc,
        "p_invalid": f"{candidate.p_invalid:.6f}",
        "p_not_ready": f"{candidate.p_not_ready:.6f}",
        "p_ready": f"{candidate.p_ready:.6f}",
        "ready_candidate_count": candidate_count,
    }


def write_results(output_dir: Path, results: list[dict]) -> Path:
    csv_path = output_dir / "live_extraction_results.csv"
    fieldnames = [
        "event_id",
        "selected_image",
        "camera_frame_number",
        "elapsed_seconds",
        "captured_at_utc",
        "p_invalid",
        "p_not_ready",
        "p_ready",
        "ready_candidate_count",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    return csv_path


def draw_status(
    frame: np.ndarray,
    status: str,
    p_ready: float,
    best: Optional[Candidate],
    event_number: int,
    saved_message: str,
) -> np.ndarray:
    preview = frame.copy()
    colours = {
        "WARMING UP": (255, 180, 0),
        "SEARCHING": (0, 190, 255),
        "READY": (0, 220, 0),
        "FINALIZING": (255, 180, 0),
    }
    colour = colours.get(status, (255, 255, 255))
    overlay = preview.copy()
    cv2.rectangle(overlay, (0, 0), (preview.shape[1], 145), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.62, preview, 0.38, 0, preview)
    cv2.putText(preview, status, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2)
    cv2.putText(
        preview,
        f"READY probability: {p_ready:.3f}",
        (20, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )
    best_text = f"Current best: {best.p_ready:.3f}" if best else "Current best: none"
    cv2.putText(
        preview, best_text, (20, 103), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
        (255, 255, 255), 2
    )
    cv2.putText(
        preview,
        f"Saved events: {event_number}   Q: quit   R: reset current event",
        (20, 134),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (230, 230, 230),
        2,
    )
    if saved_message:
        cv2.putText(
            preview,
            saved_message,
            (20, preview.shape[0] - 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2,
        )
    return preview


def main() -> int:
    args = parse_args()
    validate_args(args)

    model_path = Path(args.model).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    selected_dir = output_dir / "selected_frames"
    selected_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = load_checkpoint(model_path, device)
    class_to_idx = normalize_class_mapping(
        checkpoint.get("class_to_idx", {"INVALID": 0, "NOT_READY": 1, "READY": 2})
    )
    model = build_model(checkpoint, device)
    transform = build_transform(checkpoint)
    capture = open_camera(args)

    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    reported_fps = float(capture.get(cv2.CAP_PROP_FPS))
    session_started_utc = datetime.now(timezone.utc).isoformat()
    session_start = time.monotonic()
    warmup_ends = session_start + args.warmup_seconds
    inference_interval = 1.0 / args.sample_fps
    next_inference_time = warmup_ends

    frame_number = 0
    sampled_frames = 0
    candidate_count = 0
    below_threshold_count = 0
    event_number = 0
    best: Optional[Candidate] = None
    results: list[dict] = []
    p_invalid = p_not_ready = p_ready = 0.0
    status = "WARMING UP"
    saved_message = ""
    saved_message_until = 0.0

    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Camera: {args.camera} ({actual_width}x{actual_height})")
    print(f"Reported camera FPS: {reported_fps:.3f}")
    print(f"Inference sample FPS: {args.sample_fps:.3f}")
    print(f"READY threshold: {args.threshold:.2f}")
    print("Controls: Q = quit safely, R = discard/reset current event")

    stopped_reason = "camera_stream_ended"
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_number += 1
            if args.mirror:
                frame = cv2.flip(frame, 1)

            now = time.monotonic()
            elapsed = now - session_start
            if now < warmup_ends:
                status = "WARMING UP"
            elif now >= next_inference_time:
                sampled_frames += 1
                p_invalid, p_not_ready, p_ready = predict(
                    frame, model, transform, class_to_idx, device
                )
                next_inference_time = max(
                    next_inference_time + inference_interval,
                    time.monotonic() + 0.001,
                )

                if p_ready >= args.threshold:
                    status = "READY"
                    below_threshold_count = 0
                    candidate_count += 1
                    if best is None or p_ready > best.p_ready:
                        best = Candidate(
                            frame=frame.copy(),
                            camera_frame_number=frame_number,
                            elapsed_seconds=elapsed,
                            captured_at_utc=datetime.now(timezone.utc).isoformat(),
                            p_invalid=p_invalid,
                            p_not_ready=p_not_ready,
                            p_ready=p_ready,
                        )
                elif best is None:
                    status = "SEARCHING"
                else:
                    status = "FINALIZING"
                    below_threshold_count += 1
                    if below_threshold_count >= args.end_gap_frames:
                        if candidate_count >= args.min_ready_frames:
                            event_number += 1
                            row = save_event(
                                event_number, best, candidate_count, selected_dir
                            )
                            results.append(row)
                            write_results(output_dir, results)
                            saved_message = (
                                f"Saved {row['event_id']}  p_ready={row['p_ready']}"
                            )
                            saved_message_until = time.monotonic() + 3.0
                            print(saved_message)
                        best = None
                        candidate_count = 0
                        below_threshold_count = 0
                        status = "SEARCHING"

            if time.monotonic() > saved_message_until:
                saved_message = ""
            preview = draw_status(
                frame, status, p_ready, best, event_number, saved_message
            )
            cv2.imshow("Phase 5B - Live Best Frame Extractor", preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                stopped_reason = "user_pressed_q"
                break
            if key in (ord("r"), ord("R")):
                best = None
                candidate_count = 0
                below_threshold_count = 0
                status = "SEARCHING"
                print("Current event reset by user")
    finally:
        capture.release()
        cv2.destroyAllWindows()

    # Q safely saves a valid unfinished READY event before closing the session.
    if best is not None and candidate_count >= args.min_ready_frames:
        event_number += 1
        row = save_event(event_number, best, candidate_count, selected_dir)
        results.append(row)
        print(f"Saved unfinished {row['event_id']}  p_ready={row['p_ready']}")

    csv_path = write_results(output_dir, results)
    session_ended_utc = datetime.now(timezone.utc).isoformat()
    summary = {
        "session_started_utc": session_started_utc,
        "session_ended_utc": session_ended_utc,
        "session_duration_seconds": round(time.monotonic() - session_start, 3),
        "model": str(model_path),
        "device": str(device),
        "strategy": "visual_only",
        "ready_threshold": args.threshold,
        "sample_fps": args.sample_fps,
        "end_gap_frames": args.end_gap_frames,
        "min_ready_frames": args.min_ready_frames,
        "camera_index": args.camera,
        "camera_backend": args.backend,
        "camera_width": actual_width,
        "camera_height": actual_height,
        "reported_camera_fps": reported_fps,
        "mirror": args.mirror,
        "camera_frames_read": frame_number,
        "sampled_frames": sampled_frames,
        "events_saved": len(results),
        "stopped_reason": stopped_reason,
        "test_split_used": False,
    }
    summary_path = output_dir / "live_extraction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nSession completed. Events saved: {len(results)}")
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