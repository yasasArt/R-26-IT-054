"""Manually select segmentation-ready best frames from one extracted video.

Use this tool when an automatic best-frame model does not generalize to a new
capture setup. Frames auto-play like a video. Pause near a fully unfolded event,
step to the sharpest frame, and press B. Selections and playback position are
auto-saved; selected images are copied without resize, crop or recompression.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Dict

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VALID_DECISIONS = {"BEST", "SKIP"}
LEFT_KEYS = {81, 2424832, 65361}
RIGHT_KEYS = {83, 2555904, 65363}
UP_KEYS = {82, 2490368, 65362}
DOWN_KEYS = {84, 2621440, 65364}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually select best frames for Roboflow segmentation."
    )
    parser.add_argument(
        "frames_dir",
        help="One folder such as adaptation_v2/extracted_frames/v29",
    )
    parser.add_argument(
        "--selected-dir",
        default="adaptation_v2/selected_best_frames",
        help="Folder that receives untouched selected images.",
    )
    parser.add_argument(
        "--csv-dir",
        default="adaptation_v2/best_frame_selections",
        help="Folder for per-video BEST/SKIP decision CSV files.",
    )
    parser.add_argument("--window-width", type=int, default=1400)
    parser.add_argument("--window-height", type=int, default=900)
    parser.add_argument("--jump", type=int, default=10)
    parser.add_argument(
        "--source-sample-fps",
        type=float,
        default=3.0,
        help="FPS used to extract these frames (default: 3).",
    )
    parser.add_argument(
        "--play-fps",
        type=float,
        default=12.0,
        help="Initial display FPS. 12 FPS is 4x speed for 3-FPS frames.",
    )
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


def load_decisions(csv_path: Path, video_id: str) -> Dict[str, str]:
    if not csv_path.is_file():
        return {}

    decisions: Dict[str, str] = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"video_id", "frame_id", "decision"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"Existing CSV must contain columns {sorted(required)}: {csv_path}"
            )
        for row_number, row in enumerate(reader, start=2):
            row_video_id = str(row.get("video_id", "")).strip()
            frame_id = str(row.get("frame_id", "")).strip()
            decision = str(row.get("decision", "")).strip().upper()
            if row_video_id != video_id:
                raise ValueError(
                    f"CSV row {row_number} has video_id={row_video_id}, "
                    f"expected {video_id}"
                )
            if decision not in VALID_DECISIONS:
                raise ValueError(
                    f"CSV row {row_number} has invalid decision={decision!r}"
                )
            decisions[frame_id] = decision
    return decisions


def load_player_index(state_path: Path, total_frames: int) -> int:
    if not state_path.is_file():
        return 0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        saved_index = int(data.get("current_index", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
    return min(max(saved_index, 0), total_frames - 1)


def save_player_state(
    state_path: Path,
    video_id: str,
    current_index: int,
    play_fps: float,
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "video_id": video_id,
                "current_index": current_index,
                "play_fps": play_fps,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(state_path)


def save_decisions(
    csv_path: Path,
    video_id: str,
    frames: list[Path],
    decisions: Dict[str, str],
    selected_dir: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = csv_path.with_suffix(csv_path.suffix + ".tmp")
    frame_by_id = {path.stem: path for path in frames}

    with temporary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "video_id",
                "frame_id",
                "decision",
                "source_image",
                "selected_image",
            ],
        )
        writer.writeheader()
        for frame_path in frames:
            frame_id = frame_path.stem
            decision = decisions.get(frame_id)
            if decision is None:
                continue
            selected_path = selected_dir / frame_path.name
            writer.writerow(
                {
                    "video_id": video_id,
                    "frame_id": frame_id,
                    "decision": decision,
                    "source_image": str(frame_path.resolve()),
                    "selected_image": (
                        str(selected_path.resolve()) if decision == "BEST" else ""
                    ),
                }
            )
    temporary_path.replace(csv_path)

    unknown_ids = set(decisions) - set(frame_by_id)
    if unknown_ids:
        raise ValueError(f"Unknown frame IDs in decisions: {sorted(unknown_ids)[:5]}")


def apply_decision(
    frame_path: Path,
    decision: str,
    decisions: Dict[str, str],
    selected_dir: Path,
) -> None:
    selected_dir.mkdir(parents=True, exist_ok=True)
    frame_id = frame_path.stem
    selected_path = selected_dir / frame_path.name
    decisions[frame_id] = decision

    if decision == "BEST":
        # Copy the untouched extracted image. No resize, crop or recompression.
        shutil.copy2(frame_path, selected_path)
    elif selected_path.exists():
        # This is only a derived copy; the original extracted frame is preserved.
        selected_path.unlink()


def clear_decision(
    frame_path: Path,
    decisions: Dict[str, str],
    selected_dir: Path,
) -> None:
    decisions.pop(frame_path.stem, None)
    selected_path = selected_dir / frame_path.name
    if selected_path.exists():
        selected_path.unlink()


def first_undecided_index(frames: list[Path], decisions: Dict[str, str]) -> int:
    for index, frame_path in enumerate(frames):
        if frame_path.stem not in decisions:
            return index
    return max(0, len(frames) - 1)


def next_undecided_index(
    frames: list[Path], decisions: Dict[str, str], current_index: int
) -> int:
    for index in range(current_index + 1, len(frames)):
        if frames[index].stem not in decisions:
            return index
    return min(current_index + 1, len(frames) - 1)


def create_display(
    image: np.ndarray,
    frame_id: str,
    decision: str,
    index: int,
    total: int,
    decisions: Dict[str, str],
    window_width: int,
    window_height: int,
    jump: int,
    playing: bool,
    play_fps: float,
    source_sample_fps: float,
) -> np.ndarray:
    header_height = 132
    image_area_height = window_height - header_height
    image_height, image_width = image.shape[:2]
    scale = min(
        window_width / image_width,
        image_area_height / image_height,
        1.0,
    )
    display_width = max(1, round(image_width * scale))
    display_height = max(1, round(image_height * scale))
    resized = (
        image.copy()
        if (display_width, display_height) == (image_width, image_height)
        else cv2.resize(
            image,
            (display_width, display_height),
            interpolation=cv2.INTER_AREA,
        )
    )

    canvas = np.full((window_height, window_width, 3), 24, dtype=np.uint8)
    x_offset = (window_width - display_width) // 2
    y_offset = header_height + (image_area_height - display_height) // 2
    canvas[
        y_offset : y_offset + display_height,
        x_offset : x_offset + display_width,
    ] = resized

    counts = Counter(decisions.values())
    decision_text = decision or "UNREVIEWED"
    colours = {
        "BEST": (0, 230, 0),
        "SKIP": (0, 190, 255),
        "UNREVIEWED": (225, 225, 225),
    }
    cv2.putText(
        canvas,
        f"{frame_id}   Frame {index + 1}/{total}   Decision: {decision_text}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        colours[decision_text],
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "Space=Play/Pause   R=Replay   B=Save BEST   D=Remove   Left/Right=1   "
        f"Up/Down={jump}   1/2/3/4=Speed   Esc=Exit",
        (20, 69),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        (235, 235, 235),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        (
            f"Mode {'PLAYING' if playing else 'PAUSED'}   "
            f"Playback {play_fps:.1f} FPS "
            f"({play_fps / source_sample_fps:.1f}x)   "
            f"BEST selected {counts['BEST']}"
        ),
        (20, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (190, 220, 255),
        1,
        cv2.LINE_AA,
    )
    return canvas


def main() -> int:
    args = parse_args()
    if args.window_width < 640 or args.window_height < 480:
        raise ValueError("Selection window must be at least 640 x 480")
    if args.jump < 1:
        raise ValueError("--jump must be at least 1")
    if args.source_sample_fps <= 0:
        raise ValueError("--source-sample-fps must be greater than zero")
    if args.play_fps <= 0:
        raise ValueError("--play-fps must be greater than zero")

    frames_dir = Path(args.frames_dir).expanduser().resolve()
    selected_dir = Path(args.selected_dir).expanduser().resolve()
    csv_dir = Path(args.csv_dir).expanduser().resolve()
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"Frames folder not found: {frames_dir}")

    video_id = frames_dir.name
    if not re.fullmatch(r"v\d+", video_id, flags=re.IGNORECASE):
        raise ValueError(f"Expected a video folder name such as v29: {video_id}")

    frames = find_frames(frames_dir)
    if not frames:
        raise FileNotFoundError(f"No JPG/PNG frames found in {frames_dir}")

    csv_path = csv_dir / f"{video_id}_best_selections.csv"
    state_path = csv_dir / f"{video_id}_player_state.json"
    decisions = load_decisions(csv_path, video_id)
    frame_ids = {path.stem for path in frames}
    unknown_ids = sorted(set(decisions) - frame_ids)
    if unknown_ids:
        raise ValueError(
            f"CSV contains {len(unknown_ids)} frame IDs not found in {frames_dir}"
        )

    # Restore any BEST copies referenced by an existing CSV.
    selected_dir.mkdir(parents=True, exist_ok=True)
    for frame_path in frames:
        if decisions.get(frame_path.stem) == "BEST":
            selected_path = selected_dir / frame_path.name
            if not selected_path.exists():
                shutil.copy2(frame_path, selected_path)

    index = load_player_index(state_path, len(frames))
    play_fps = args.play_fps
    playing = True
    window_name = f"Manual Best Frame Selection - {video_id}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, args.window_width, args.window_height)

    print(f"Video: {video_id}")
    print(f"Frames: {len(frames)}")
    print(f"Existing BEST selections: {Counter(decisions.values())['BEST']}")
    print(f"Starting at: {frames[index].name}")
    print(
        f"Auto-play: {play_fps:.1f} FPS "
        f"({play_fps / args.source_sample_fps:.1f}x video speed)"
    )
    print("Space pauses. Select one sharp, fully visible, hand-free BEST frame per event.")

    try:
        while True:
            frame_path = frames[index]
            image = cv2.imread(str(frame_path))
            if image is None:
                raise OSError(f"Could not read image: {frame_path}")

            current_decision = decisions.get(frame_path.stem, "")
            display = create_display(
                image=image,
                frame_id=frame_path.stem,
                decision=current_decision,
                index=index,
                total=len(frames),
                decisions=decisions,
                window_width=args.window_width,
                window_height=args.window_height,
                jump=args.jump,
                playing=playing,
                play_fps=play_fps,
                source_sample_fps=args.source_sample_fps,
            )
            cv2.imshow(window_name, display)
            wait_milliseconds = max(1, round(1000 / play_fps)) if playing else 0
            key = cv2.waitKeyEx(wait_milliseconds)

            if key == -1:
                if playing:
                    if index < len(frames) - 1:
                        index += 1
                    else:
                        playing = False
                continue

            if key in (27, ord("q"), ord("Q")):
                save_decisions(csv_path, video_id, frames, decisions, selected_dir)
                save_player_state(state_path, video_id, index, play_fps)
                break
            if key == ord(" "):
                playing = not playing
                continue
            if key in (ord("r"), ord("R")):
                index = 0
                playing = True
                save_player_state(state_path, video_id, index, play_fps)
                continue
            if key in LEFT_KEYS:
                playing = False
                index = max(0, index - 1)
                continue
            if key in RIGHT_KEYS:
                playing = False
                index = min(len(frames) - 1, index + 1)
                continue
            if key in UP_KEYS:
                playing = False
                index = max(0, index - args.jump)
                continue
            if key in DOWN_KEYS:
                playing = False
                index = min(len(frames) - 1, index + args.jump)
                continue
            if key in (ord("1"), ord("2"), ord("3"), ord("4")):
                speed_multiplier = {
                    ord("1"): 1,
                    ord("2"): 2,
                    ord("3"): 4,
                    ord("4"): 8,
                }[key]
                play_fps = args.source_sample_fps * speed_multiplier
                continue
            if key in (ord("b"), ord("B")):
                apply_decision(frame_path, "BEST", decisions, selected_dir)
                print(f"BEST saved: {frame_path.name}")
            elif key in (ord("d"), ord("D")):
                clear_decision(frame_path, decisions, selected_dir)
                save_decisions(csv_path, video_id, frames, decisions, selected_dir)
                continue
            else:
                continue

            save_decisions(csv_path, video_id, frames, decisions, selected_dir)
            save_player_state(state_path, video_id, index, play_fps)
    finally:
        cv2.destroyAllWindows()

    counts = Counter(decisions.values())
    print(f"\nVideo: {video_id}")
    print(f"BEST selected: {counts['BEST']}")
    print(f"Last frame position: {index + 1}/{len(frames)}")
    print(f"Selected images: {selected_dir}")
    print(f"Decision CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
