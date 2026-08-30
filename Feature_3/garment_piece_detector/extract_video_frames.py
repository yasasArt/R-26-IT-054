r"""Extract frames from one video or every video in a directory.

Examples (PowerShell):
    python .\extract_video_frames.py --input ".\dataset_v2_fixed_height\raw_videos" --output ".\dataset_v2_fixed_height\extracted_frames" --fps 3
    python .\extract_video_frames.py --input "..\01_video_annotation\shuffled videos\v29.mp4" --output ".\dataset_v2_fixed_height\extracted_frames" --fps 3
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract frames at a fixed sampling rate without resizing them."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to one video or a directory containing videos",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Root directory for extracted frame folders",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=3.0,
        help="Frames to save per second (default: 3)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality from 1 to 100 (default: 95)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing JPG files in each video's output folder",
    )
    return parser.parse_args()


def find_videos(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError(f"Unsupported video type: {input_path.suffix}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input does not exist: {input_path}")

    videos = sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        raise FileNotFoundError(f"No supported videos found in: {input_path}")
    return videos


def extract_video(
    video_path: Path,
    output_root: Path,
    target_fps: float,
    quality: int,
    overwrite: bool,
) -> dict[str, object]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    total_source_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if source_fps <= 0:
        capture.release()
        raise RuntimeError(f"Invalid source FPS for: {video_path}")

    video_id = video_path.stem
    output_dir = output_root / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = list(output_dir.glob("*.jpg"))
    if existing and not overwrite:
        capture.release()
        raise FileExistsError(
            f"{output_dir} already contains JPG files. "
            "Use --overwrite to replace them."
        )
    if overwrite:
        for image_path in existing:
            image_path.unlink()

    source_index = 0
    saved_count = 0
    next_sample_time = 0.0
    sample_interval = 1.0 / target_fps

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        timestamp = source_index / source_fps
        if timestamp + 1e-9 >= next_sample_time:
            saved_count += 1
            frame_path = output_dir / f"{video_id}_{saved_count:04d}.jpg"
            written = cv2.imwrite(
                str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, quality]
            )
            if not written:
                capture.release()
                raise RuntimeError(f"Failed to save frame: {frame_path}")
            next_sample_time += sample_interval

        source_index += 1

    capture.release()
    duration = total_source_frames / source_fps if total_source_frames else 0.0
    return {
        "video_id": video_id,
        "video_path": str(video_path.resolve()),
        "source_fps": round(source_fps, 4),
        "target_fps": target_fps,
        "duration_seconds": round(duration, 3),
        "resolution": f"{width}x{height}",
        "source_frames": total_source_frames,
        "saved_frames": saved_count,
        "output_folder": str(output_dir.resolve()),
    }


def write_summary(output_root: Path, rows: list[dict[str, object]]) -> Path:
    summary_path = output_root / "frame_extraction_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return summary_path


def main() -> None:
    args = parse_args()
    if args.fps <= 0:
        raise ValueError("--fps must be greater than 0")
    if not 1 <= args.quality <= 100:
        raise ValueError("--quality must be between 1 and 100")

    input_path = Path(args.input).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    videos = find_videos(input_path)
    print(f"Videos found: {len(videos)}")
    print(f"Extraction rate: {args.fps} FPS")

    results: list[dict[str, object]] = []
    for number, video_path in enumerate(videos, start=1):
        print(f"\n[{number}/{len(videos)}] Processing: {video_path.name}")
        result = extract_video(
            video_path,
            output_root,
            args.fps,
            args.quality,
            args.overwrite,
        )
        results.append(result)
        print(f"Saved frames: {result['saved_frames']}")
        print(f"Output: {result['output_folder']}")

    summary_path = write_summary(output_root, results)
    print("\nFrame extraction completed successfully.")
    print(f"Summary: {summary_path.resolve()}")


if __name__ == "__main__":
    main()
