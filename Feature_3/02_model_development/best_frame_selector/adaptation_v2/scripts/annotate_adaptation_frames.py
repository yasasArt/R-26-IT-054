"""Keyboard annotation tool for Best Frame Selector adaptation frames.

Labels one extracted video folder at a time using the project's existing
states: READY, NOT_READY and INVALID. Annotations are auto-saved after every
change and can be resumed later from the same CSV file.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict

import cv2
import numpy as np


VALID_STATES = ("INVALID", "NOT_READY", "READY")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
LEFT_KEYS = {81, 2424832, 65361}
RIGHT_KEYS = {83, 2555904, 65363}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate adaptation frames as READY, NOT_READY or INVALID."
    )
    parser.add_argument(
        "frames_dir",
        help="One extracted video folder, for example adaptation_v2/extracted_frames/v29",
    )
    parser.add_argument(
        "--csv-dir",
        default="adaptation_v2/annotated_csvs",
        help="Folder for per-video annotation CSV files.",
    )
    parser.add_argument("--window-width", type=int, default=1400)
    parser.add_argument("--window-height", type=int, default=900)
    return parser.parse_args()


def natural_sort_key(path: Path) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def find_frames(folder: Path) -> list[Path]:
    return sorted(
        [path for path in folder.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS],
        key=natural_sort_key,
    )


def load_annotations(csv_path: Path, video_id: str) -> Dict[str, str]:
    if not csv_path.is_file():
        return {}

    annotations: Dict[str, str] = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"video_id", "frame_id", "state"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"Existing CSV must contain columns {sorted(required)}: {csv_path}"
            )

        for row_number, row in enumerate(reader, start=2):
            row_video_id = str(row.get("video_id", "")).strip()
            frame_id = str(row.get("frame_id", "")).strip()
            state = str(row.get("state", "")).strip().upper()

            if row_video_id != video_id:
                raise ValueError(
                    f"CSV row {row_number} has video_id={row_video_id}, "
                    f"expected {video_id}"
                )
            if state not in VALID_STATES:
                raise ValueError(
                    f"CSV row {row_number} has invalid state={state!r}"
                )
            annotations[frame_id] = state

    return annotations


def save_annotations(
    csv_path: Path,
    video_id: str,
    frames: list[Path],
    annotations: Dict[str, str],
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = csv_path.with_suffix(csv_path.suffix + ".tmp")

    with temporary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["video_id", "frame_id", "state"],
        )
        writer.writeheader()
        for frame_path in frames:
            frame_id = frame_path.stem
            if frame_id in annotations:
                writer.writerow(
                    {
                        "video_id": video_id,
                        "frame_id": frame_id,
                        "state": annotations[frame_id],
                    }
                )

    temporary_path.replace(csv_path)


def first_unannotated_index(
    frames: list[Path], annotations: Dict[str, str]
) -> int:
    for index, frame_path in enumerate(frames):
        if frame_path.stem not in annotations:
            return index
    return max(0, len(frames) - 1)


def next_unannotated_index(
    frames: list[Path], annotations: Dict[str, str], current_index: int
) -> int:
    for index in range(current_index + 1, len(frames)):
        if frames[index].stem not in annotations:
            return index
    return min(current_index + 1, len(frames) - 1)


def create_display(
    image: np.ndarray,
    frame_id: str,
    current_state: str,
    index: int,
    total: int,
    annotations: Dict[str, str],
    window_width: int,
    window_height: int,
) -> np.ndarray:
    header_height = 125
    image_area_height = window_height - header_height
    image_height, image_width = image.shape[:2]

    scale = min(
        window_width / image_width,
        image_area_height / image_height,
        1.0,
    )
    display_width = max(1, round(image_width * scale))
    display_height = max(1, round(image_height * scale))

    if (display_width, display_height) == (image_width, image_height):
        resized = image.copy()
    else:
        resized = cv2.resize(
            image,
            (display_width, display_height),
            interpolation=cv2.INTER_AREA,
        )

    canvas = np.full((window_height, window_width, 3), 24, dtype=np.uint8)
    x_offset = (window_width - display_width) // 2
    y_offset = header_height + (image_area_height - display_height) // 2
    canvas[
        y_offset : y_offset + display_height,
        x_offset : x_offset + display_width,
    ] = resized

    counts = Counter(annotations.values())
    annotated_count = len(annotations)
    state_text = current_state if current_state else "UNLABELED"
    state_colours = {
        "READY": (0, 220, 0),
        "NOT_READY": (0, 190, 255),
        "INVALID": (80, 80, 255),
        "UNLABELED": (220, 220, 220),
    }

    cv2.putText(
        canvas,
        f"{frame_id}   Frame {index + 1}/{total}   Label: {state_text}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        state_colours[state_text],
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "R=READY   N=NOT_READY   I=INVALID   D=Clear   Left/Right=Navigate   Esc=Save and exit",
        (20, 68),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (235, 235, 235),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        (
            f"Annotated {annotated_count}/{total}   "
            f"READY {counts['READY']}   NOT_READY {counts['NOT_READY']}   "
            f"INVALID {counts['INVALID']}"
        ),
        (20, 102),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (190, 220, 255),
        1,
        cv2.LINE_AA,
    )
    return canvas


def print_summary(
    video_id: str,
    total: int,
    annotations: Dict[str, str],
    csv_path: Path,
) -> None:
    counts = Counter(annotations.values())
    print(f"\nVideo: {video_id}")
    print(f"Total frames: {total}")
    print(f"Annotated: {len(annotations)}")
    print(f"Remaining: {total - len(annotations)}")
    print(f"READY: {counts['READY']}")
    print(f"NOT_READY: {counts['NOT_READY']}")
    print(f"INVALID: {counts['INVALID']}")
    print(f"CSV: {csv_path}")


def main() -> int:
    args = parse_args()
    if args.window_width < 640 or args.window_height < 480:
        raise ValueError("Annotation window must be at least 640 x 480")

    frames_dir = Path(args.frames_dir).expanduser().resolve()
    csv_dir = Path(args.csv_dir).expanduser().resolve()
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"Frames folder not found: {frames_dir}")

    video_id = frames_dir.name
    if not re.fullmatch(r"v\d+", video_id, flags=re.IGNORECASE):
        raise ValueError(
            f"Frames folder name must be a video ID such as v29: {frames_dir.name}"
        )

    frames = find_frames(frames_dir)
    if not frames:
        raise FileNotFoundError(f"No JPG/PNG frames found in {frames_dir}")

    csv_path = csv_dir / f"{video_id}_annotations.csv"
    annotations = load_annotations(csv_path, video_id)
    valid_frame_ids = {frame_path.stem for frame_path in frames}
    unknown_ids = sorted(set(annotations) - valid_frame_ids)
    if unknown_ids:
        raise ValueError(
            f"CSV contains {len(unknown_ids)} frame IDs not present in {frames_dir}"
        )

    index = first_unannotated_index(frames, annotations)
    window_name = f"Adaptation Annotation - {video_id}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, args.window_width, args.window_height)

    print(f"Selected video folder: {frames_dir}")
    print(f"Video ID: {video_id}")
    print(f"Frames found: {len(frames)}")
    print(f"Existing annotations: {len(annotations)}")
    print(f"Starting at: {frames[index].name}")
    print("Controls: R READY, N NOT_READY, I INVALID, arrows navigate, Esc saves")

    try:
        while True:
            frame_path = frames[index]
            image = cv2.imread(str(frame_path))
            if image is None:
                raise OSError(f"Could not read image: {frame_path}")

            frame_id = frame_path.stem
            current_state = annotations.get(frame_id, "")
            display = create_display(
                image=image,
                frame_id=frame_id,
                current_state=current_state,
                index=index,
                total=len(frames),
                annotations=annotations,
                window_width=args.window_width,
                window_height=args.window_height,
            )
            cv2.imshow(window_name, display)
            key = cv2.waitKeyEx(0)

            if key in (27, ord("q"), ord("Q")):
                save_annotations(csv_path, video_id, frames, annotations)
                break
            if key in LEFT_KEYS:
                index = max(0, index - 1)
                continue
            if key in RIGHT_KEYS:
                index = min(len(frames) - 1, index + 1)
                continue
            if key in (ord("r"), ord("R")):
                annotations[frame_id] = "READY"
            elif key in (ord("n"), ord("N")):
                annotations[frame_id] = "NOT_READY"
            elif key in (ord("i"), ord("I")):
                annotations[frame_id] = "INVALID"
            elif key in (ord("d"), ord("D")):
                annotations.pop(frame_id, None)
                save_annotations(csv_path, video_id, frames, annotations)
                continue
            else:
                continue

            # Crash-safe progress: save after every label, then advance.
            save_annotations(csv_path, video_id, frames, annotations)
            index = next_unannotated_index(frames, annotations, index)
    finally:
        cv2.destroyAllWindows()

    print_summary(video_id, len(frames), annotations, csv_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
