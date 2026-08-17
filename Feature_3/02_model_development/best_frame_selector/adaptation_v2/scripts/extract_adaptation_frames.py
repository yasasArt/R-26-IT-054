"""Extract original-resolution frames from adaptation videos at a fixed FPS.

Default project usage extracts v29.mp4 through v39.mp4 at 3 FPS into
adaptation_v2/extracted_frames/vXX. Frames are decoded and saved without any
crop or resize. A CSV manifest and JSON summary are written for auditing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2


IMAGE_EXTENSIONS = {"jpg", "png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract original-resolution adaptation frames at fixed FPS."
    )
    parser.add_argument(
        "--video-dir",
        default="sample_videos",
        help="Folder containing v29.mp4, v30.mp4, etc.",
    )
    parser.add_argument(
        "--output-dir",
        default="adaptation_v2/extracted_frames",
        help="Destination root for per-video frame folders.",
    )
    parser.add_argument(
        "--manifest-dir",
        default="adaptation_v2/manifests",
        help="Destination for extraction_manifest.csv and summary JSON.",
    )
    parser.add_argument("--start-video", type=int, default=29)
    parser.add_argument("--end-video", type=int, default=39)
    parser.add_argument("--sample-fps", type=float, default=3.0)
    parser.add_argument(
        "--image-format",
        choices=sorted(IMAGE_EXTENSIONS),
        default="jpg",
        help="JPG is compatible with the existing annotation tool; PNG is lossless.",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=100,
        help="JPEG quality from 1 to 100 (default: 100).",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.start_video < 0:
        raise ValueError("--start-video must be zero or greater")
    if args.end_video < args.start_video:
        raise ValueError("--end-video must be greater than or equal to --start-video")
    if args.sample_fps <= 0:
        raise ValueError("--sample-fps must be greater than zero")
    if not 1 <= args.jpeg_quality <= 100:
        raise ValueError("--jpeg-quality must be between 1 and 100")


def existing_images(folder: Path) -> list[Path]:
    files: list[Path] = []
    for extension in IMAGE_EXTENSIONS:
        files.extend(folder.glob(f"*.{extension}"))
        files.extend(folder.glob(f"*.{extension.upper()}"))
    return files


def extract_video(
    video_id: str,
    video_path: Path,
    output_root: Path,
    requested_sample_fps: float,
    image_format: str,
    jpeg_quality: int,
) -> tuple[list[dict], dict]:
    output_folder = output_root / video_id
    output_folder.mkdir(parents=True, exist_ok=True)

    already_present = existing_images(output_folder)
    if already_present:
        raise FileExistsError(
            f"{output_folder} already contains {len(already_present)} image(s). "
            "Use an empty output folder so old and new frames are not mixed."
        )

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Could not open video: {video_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    total_source_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if source_fps <= 0:
        capture.release()
        raise ValueError(f"Video does not report a valid FPS: {video_path}")

    sample_interval = max(1, round(source_fps / requested_sample_fps))
    effective_sample_fps = source_fps / sample_interval
    source_frame_number = 0
    saved_index = 0
    rows: list[dict] = []
    decoded_width = 0
    decoded_height = 0

    if image_format == "jpg":
        write_parameters = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
    else:
        write_parameters = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if source_frame_number % sample_interval == 0:
                saved_index += 1
                decoded_height, decoded_width = frame.shape[:2]
                frame_id = f"{video_id}_{saved_index:03d}"
                image_path = output_folder / f"{frame_id}.{image_format}"

                # Save the untouched decoded frame: no crop and no resize.
                if not cv2.imwrite(str(image_path), frame, write_parameters):
                    raise OSError(f"Could not save frame: {image_path}")

                rows.append(
                    {
                        "video_id": video_id,
                        "frame_id": frame_id,
                        "source_frame_number": source_frame_number,
                        "timestamp_seconds": f"{source_frame_number / source_fps:.6f}",
                        "source_fps": f"{source_fps:.6f}",
                        "effective_sample_fps": f"{effective_sample_fps:.6f}",
                        "image_width": decoded_width,
                        "image_height": decoded_height,
                        "image_format": image_format,
                        "image_path": str(image_path.resolve()),
                    }
                )

                if saved_index % 100 == 0:
                    print(f"  {video_id}: saved {saved_index} frames")

            source_frame_number += 1
    finally:
        capture.release()

    if saved_index == 0:
        raise ValueError(f"No frames were extracted from {video_path}")

    summary = {
        "video_id": video_id,
        "video_path": str(video_path.resolve()),
        "source_fps": source_fps,
        "total_source_frames_reported": total_source_frames,
        "total_source_frames_decoded": source_frame_number,
        "sample_interval": sample_interval,
        "requested_sample_fps": requested_sample_fps,
        "effective_sample_fps": effective_sample_fps,
        "frames_saved": saved_index,
        "image_width": decoded_width,
        "image_height": decoded_height,
        "image_format": image_format,
        "resized": False,
        "cropped": False,
    }
    return rows, summary


def main() -> int:
    args = parse_args()
    validate_args(args)

    video_dir = Path(args.video_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    manifest_dir = Path(args.manifest_dir).expanduser().resolve()

    if not video_dir.is_dir():
        raise FileNotFoundError(f"Video folder not found: {video_dir}")

    video_numbers = range(args.start_video, args.end_video + 1)
    planned_videos = [f"v{number:02d}" for number in video_numbers]
    missing = [
        f"{video_id}.mp4"
        for video_id in planned_videos
        if not (video_dir / f"{video_id}.mp4").is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Missing video files: {', '.join(missing)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    video_summaries: list[dict] = []

    print(f"Videos: {planned_videos[0]} to {planned_videos[-1]}")
    print(f"Requested sample FPS: {args.sample_fps:.3f}")
    print("Output frames keep their decoded source resolution.")

    for video_id in planned_videos:
        video_path = video_dir / f"{video_id}.mp4"
        print(f"\nExtracting {video_id}: {video_path.name}")
        rows, summary = extract_video(
            video_id=video_id,
            video_path=video_path,
            output_root=output_dir,
            requested_sample_fps=args.sample_fps,
            image_format=args.image_format,
            jpeg_quality=args.jpeg_quality,
        )
        all_rows.extend(rows)
        video_summaries.append(summary)
        print(
            f"  Completed {video_id}: {summary['frames_saved']} frames, "
            f"{summary['image_width']} x {summary['image_height']}"
        )

    manifest_path = manifest_dir / "extraction_manifest.csv"
    fieldnames = [
        "video_id",
        "frame_id",
        "source_frame_number",
        "timestamp_seconds",
        "source_fps",
        "effective_sample_fps",
        "image_width",
        "image_height",
        "image_format",
        "image_path",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    summary = {
        "video_start": planned_videos[0],
        "video_end": planned_videos[-1],
        "videos_processed": len(video_summaries),
        "total_frames_saved": len(all_rows),
        "requested_sample_fps": args.sample_fps,
        "image_format": args.image_format,
        "resized": False,
        "cropped": False,
        "videos": video_summaries,
    }
    summary_path = manifest_dir / "extraction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nAdaptation frame extraction complete")
    print(f"Videos processed: {len(video_summaries)}")
    print(f"Total frames saved: {len(all_rows)}")
    print(f"Frames folder: {output_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
