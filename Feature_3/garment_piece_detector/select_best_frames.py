


from __future__ import annotations

import argparse
import csv
import shutil
import time
from pathlib import Path

import cv2


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast manual selector for one or more BEST frames per video."
    )
    parser.add_argument("--frames", required=True, help="Extracted-frame folder")
    parser.add_argument("--output", required=True, help="Selected image folder")
    parser.add_argument("--csv-dir", required=True, help="Decision CSV folder")
    parser.add_argument("--play-fps", type=float, default=12.0)
    parser.add_argument("--max-width", type=int, default=1280)
    parser.add_argument("--max-height", type=int, default=780)
    return parser.parse_args()


def load_existing(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        return []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(csv_path: Path, video_id: str, selected: list[Path]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file, fieldnames=["video_id", "selection_number", "frame_id", "image_path"]
        )
        writer.writeheader()
        for number, path in enumerate(selected, start=1):
            writer.writerow(
                {
                    "video_id": video_id,
                    "selection_number": number,
                    "frame_id": path.stem,
                    "image_path": str(path.resolve()),
                }
            )


def fit_for_display(image, max_width: int, max_height: int):
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale >= 1.0:
        return image.copy()
    return cv2.resize(
        image,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def add_overlay(
    image,
    video_id: str,
    frame_name: str,
    position: int,
    total: int,
    selected_count: int,
    playing: bool,
    message: str,
):
    # Put the status panel outside the camera image. The previous version drew
    # this panel on top of the first 112 image rows and visually hid part of the
    # original frame.
    height, width = image.shape[:2]
    bar_height = 128
    canvas = cv2.copyMakeBorder(
        image,
        bar_height,
        0,
        0,
        0,
        cv2.BORDER_CONSTANT,
        value=(20, 20, 20),
    )
    state = "PLAYING" if playing else "PAUSED"
    colour = (80, 220, 80) if playing else (0, 220, 255)
    cv2.putText(
        canvas,
        f"{video_id}  |  {frame_name}  |  {position + 1}/{total}",
        (18, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        f"{state}   BEST selected: {selected_count}",
        (18, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        colour,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "SPACE play/pause | LEFT/RIGHT frame | B select BEST | U undo | ESC save & exit",
        (18, 91),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (230, 230, 230),
        1,
        cv2.LINE_AA,
    )
    if message:
        cv2.putText(
            canvas,
            message,
            (18, 118),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def main() -> None:
    args = parse_args()
    if args.play_fps <= 0:
        raise ValueError("--play-fps must be greater than 0")

    frames_dir = Path(args.frames).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    csv_dir = Path(args.csv_dir).expanduser().resolve()
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"Frame folder not found: {frames_dir}")

    frames = sorted(
        path
        for path in frames_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not frames:
        raise FileNotFoundError(f"No images found in: {frames_dir}")

    video_id = frames_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / f"{video_id}_best_selections.csv"

    existing_rows = load_existing(csv_path)
    selected: list[Path] = []
    for row in existing_rows:
        candidate = output_dir / Path(row.get("image_path", "")).name
        if candidate.is_file() and candidate not in selected:
            selected.append(candidate)

    index = 0
    playing = True
    message = ""
    message_until = 0.0
    delay = max(1, int(1000 / args.play_fps))
    window_name = "Manual BEST Frame Selector"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            image = cv2.imread(str(frames[index]))
            if image is None:
                raise RuntimeError(f"Could not read image: {frames[index]}")

            if time.monotonic() > message_until:
                message = ""
            display = fit_for_display(image, args.max_width, args.max_height)
            display = add_overlay(
                display,
                video_id,
                frames[index].name,
                index,
                len(frames),
                len(selected),
                playing,
                message,
            )
            cv2.imshow(window_name, display)
            key = cv2.waitKeyEx(delay if playing else 0)

            if key in (27, ord("q"), ord("Q")):
                break
            if key == ord(" "):
                playing = not playing
            elif key in (2424832, 81, ord("a"), ord("A")):
                playing = False
                index = max(0, index - 1)
            elif key in (2555904, 83, ord("d"), ord("D")):
                playing = False
                index = min(len(frames) - 1, index + 1)
            elif key in (ord("b"), ord("B")):
                destination = output_dir / frames[index].name
                if destination in selected:
                    message = "This frame is already selected"
                else:
                    shutil.copy2(frames[index], destination)
                    selected.append(destination)
                    write_csv(csv_path, video_id, selected)
                    message = f"BEST saved: {destination.name}"
                message_until = time.monotonic() + 2.5
            elif key in (ord("u"), ord("U")):
                if selected:
                    removed = selected.pop()
                    if removed.is_file():
                        removed.unlink()
                    write_csv(csv_path, video_id, selected)
                    message = f"Removed: {removed.name}"
                else:
                    message = "No selection to undo"
                message_until = time.monotonic() + 2.5
            elif playing:
                if index < len(frames) - 1:
                    index += 1
                else:
                    playing = False
                    message = "End reached"
                    message_until = time.monotonic() + 3.0
    finally:
        write_csv(csv_path, video_id, selected)
        cv2.destroyAllWindows()

    print(f"Video: {video_id}")
    print(f"BEST selected: {len(selected)}")
    print(f"Selected images: {output_dir}")
    print(f"Decision CSV: {csv_path}")


if __name__ == "__main__":
    main()
