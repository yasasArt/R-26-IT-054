from pathlib import Path
import argparse
import csv
import os
import re
import time

import cv2
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

AUTO_ADVANCE = True

MAX_DISPLAY_WIDTH = 1400
MAX_DISPLAY_HEIGHT = 850

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp"
}

VALID_STATES = {
    "INVALID",
    "READY",
    "NOT_READY"
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def natural_sort_key(path):
    """
    Sort frame names correctly:
    v01_001, v01_002, v01_010, etc.
    """
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def find_frames(video_folder):
    """Find and naturally sort all image frames."""

    frames = [
        path
        for path in video_folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
    ]

    return sorted(frames, key=natural_sort_key)


def load_existing_annotations(csv_path):
    """
    Load existing annotations so annotation can resume.
    """

    annotations = {}

    if not csv_path.exists():
        return annotations

    try:
        with csv_path.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as csv_file:

            reader = csv.DictReader(csv_file)

            for row in reader:
                frame_id = row.get("frame_id", "").strip()
                state = row.get("state", "").strip().upper()

                if frame_id and state in VALID_STATES:
                    annotations[frame_id] = state

        print(f"Loaded existing annotations: {csv_path}")

    except PermissionError:
        raise PermissionError(
            f"\nCannot read this CSV:\n{csv_path}\n\n"
            "Close it in Excel, VS Code, Notepad, or another "
            "application before running the annotation program."
        )

    except Exception as error:
        print(f"Warning: Could not load {csv_path}")
        print(f"Reason: {error}")

    return annotations


def save_annotations(
    csv_path,
    video_id,
    frames,
    annotations
):
    """
    Save annotations safely.

    Every frame is included in the CSV. Frames that have not been
    annotated have an empty state.
    """

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = csv_path.with_suffix(".tmp")

    with temporary_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "video_id",
                "frame_id",
                "state"
            ]
        )

        writer.writeheader()

        for frame_path in frames:
            frame_id = frame_path.stem

            writer.writerow({
                "video_id": video_id,
                "frame_id": frame_id,
                "state": annotations.get(frame_id, "")
            })

        csv_file.flush()
        os.fsync(csv_file.fileno())

    # Retry if Windows temporarily locks the CSV
    for attempt in range(5):
        try:
            os.replace(temporary_path, csv_path)
            return

        except PermissionError:
            if attempt < 4:
                time.sleep(0.5)
            else:
                raise PermissionError(
                    f"\nCould not update this CSV:\n{csv_path}\n\n"
                    "Close the CSV in Excel, VS Code, Notepad, "
                    "or another application and run the program again."
                )


def calculate_progress(frames, annotations):
    """Count how many frames have annotations."""

    return sum(
        frame_path.stem in annotations
        for frame_path in frames
    )


def first_unannotated_index(frames, annotations):
    """Find the first frame that has not been annotated."""

    for index, frame_path in enumerate(frames):
        if frame_path.stem not in annotations:
            return index

    return 0


def create_display(
    image,
    video_id,
    frame_path,
    current_index,
    frames,
    annotations
):
    """
    Resize the image and add annotation details and controls.
    """

    frame_id = frame_path.stem
    current_state = annotations.get(
        frame_id,
        "UNANNOTATED"
    )

    panel_height = 160
    available_height = MAX_DISPLAY_HEIGHT - panel_height

    original_height, original_width = image.shape[:2]

    scale = min(
        MAX_DISPLAY_WIDTH / original_width,
        available_height / original_height,
        1.0
    )

    resized_width = max(
        1,
        int(original_width * scale)
    )

    resized_height = max(
        1,
        int(original_height * scale)
    )

    resized_image = cv2.resize(
        image,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA
    )

    canvas_width = max(resized_width, 950)
    canvas_height = resized_height + panel_height

    canvas = np.zeros(
        (canvas_height, canvas_width, 3),
        dtype=np.uint8
    )

    x_offset = (
        canvas_width - resized_width
    ) // 2

    canvas[
        0:resized_height,
        x_offset:x_offset + resized_width
    ] = resized_image

    annotated_count = calculate_progress(
        frames,
        annotations
    )

    state_colors = {
        "READY": (0, 220, 0),
        "NOT_READY": (0, 180, 255),
        "INVALID": (0, 0, 255),
        "UNANNOTATED": (200, 200, 200)
    }

    state_color = state_colors.get(
        current_state,
        (200, 200, 200)
    )

    first_line = (
        f"Video: {video_id} | "
        f"Frame: {frame_id} | "
        f"{current_index + 1}/{len(frames)}"
    )

    second_line = (
        f"State: {current_state} | "
        f"Progress: {annotated_count}/{len(frames)}"
    )

    third_line = (
        "I: INVALID | R: READY | N: NOT_READY | "
        "X/Backspace/Delete: Reset"
    )

    fourth_line = (
        "Left/Right arrows: Navigate | "
        "Esc: Save and exit"
    )

    text_y = resized_height + 30

    cv2.putText(
        canvas,
        first_line,
        (20, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        second_line,
        (20, text_y + 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        state_color,
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        third_line,
        (20, text_y + 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.57,
        (220, 220, 220),
        1,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        fourth_line,
        (20, text_y + 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.57,
        (220, 220, 220),
        1,
        cv2.LINE_AA
    )

    return canvas


# ============================================================
# ANNOTATION FUNCTION
# ============================================================

def annotate_folder(video_folder, csv_output_folder):
    """
    Annotate frames from one selected video folder.
    """

    video_id = video_folder.name
    frames = find_frames(video_folder)

    if not frames:
        raise RuntimeError(
            f"No image frames were found inside:\n{video_folder}"
        )

    # CSV is saved outside the video frame folder
    csv_output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    csv_path = (
        csv_output_folder /
        f"{video_id}_annotator.csv"
    )

    annotations = load_existing_annotations(
        csv_path
    )

    annotated_count = calculate_progress(
        frames,
        annotations
    )

    print("\n========================================")
    print(f"Selected video folder: {video_folder}")
    print(f"Video ID: {video_id}")
    print(f"Frames: {len(frames)}")
    print(f"Already annotated: {annotated_count}")
    print(f"Annotation CSV: {csv_path}")
    print("========================================\n")

    if annotated_count == len(frames):
        print(
            f"All {len(frames)} frames in {video_id} "
            "are already annotated."
        )
        return

    current_index = first_unannotated_index(
        frames,
        annotations
    )

    window_name = f"Frame Annotator - {video_id}"

    cv2.namedWindow(
        window_name,
        cv2.WINDOW_NORMAL
    )

    print(
        f"Starting from: "
        f"{frames[current_index].name}"
    )

    while True:
        frame_path = frames[current_index]
        frame_id = frame_path.stem

        image = cv2.imread(str(frame_path))

        if image is None:
            print(
                f"Could not read {frame_path.name}. "
                "It was marked INVALID."
            )

            annotations[frame_id] = "INVALID"

            save_annotations(
                csv_path,
                video_id,
                frames,
                annotations
            )

            if current_index < len(frames) - 1:
                current_index += 1
                continue

            break

        display = create_display(
            image=image,
            video_id=video_id,
            frame_path=frame_path,
            current_index=current_index,
            frames=frames,
            annotations=annotations
        )

        cv2.imshow(window_name, display)

        # waitKeyEx supports special keys such as arrow keys
        key = cv2.waitKeyEx(0)

        # Remove additional OpenCV key information when present
        basic_key = key & 0xFF

        # Esc: save and exit
        if key == 27 or basic_key == 27:
            save_annotations(
                csv_path,
                video_id,
                frames,
                annotations
            )

            print("\nAnnotations saved successfully.")
            print(f"CSV: {csv_path}")
            break

        # Left arrow
        elif key in (
            2424832,  # Windows
            65361,    # Linux
            81,       # Some OpenCV builds
            2
        ):
            current_index = max(
                0,
                current_index - 1
            )

        # Right arrow
        elif key in (
            2555904,  # Windows
            65363,    # Linux
            83,       # Some OpenCV builds
            3
        ):
            current_index = min(
                len(frames) - 1,
                current_index + 1
            )

        # I: INVALID
        elif basic_key in (
            ord("i"),
            ord("I")
        ):
            annotations[frame_id] = "INVALID"

            save_annotations(
                csv_path,
                video_id,
                frames,
                annotations
            )

            print(
                f"{frame_path.name} -> INVALID"
            )

            if AUTO_ADVANCE:
                if current_index < len(frames) - 1:
                    current_index += 1
                else:
                    break

        # R: READY
        elif basic_key in (
            ord("r"),
            ord("R")
        ):
            annotations[frame_id] = "READY"

            save_annotations(
                csv_path,
                video_id,
                frames,
                annotations
            )

            print(
                f"{frame_path.name} -> READY"
            )

            if AUTO_ADVANCE:
                if current_index < len(frames) - 1:
                    current_index += 1
                else:
                    break

        # N: NOT_READY
        elif basic_key in (
            ord("n"),
            ord("N")
        ):
            annotations[frame_id] = "NOT_READY"

            save_annotations(
                csv_path,
                video_id,
                frames,
                annotations
            )

            print(
                f"{frame_path.name} -> NOT_READY"
            )

            if AUTO_ADVANCE:
                if current_index < len(frames) - 1:
                    current_index += 1
                else:
                    break

        # X, Backspace or Delete: reset annotation
        elif (
            basic_key in (
                ord("x"),
                ord("X"),
                8,
                127
            )
            or key == 3014656
        ):
            if frame_id in annotations:
                annotations.pop(frame_id)

                save_annotations(
                    csv_path,
                    video_id,
                    frames,
                    annotations
                )

                print(
                    f"{frame_path.name} -> RESET"
                )

    # Final save, including when the final frame was annotated
    save_annotations(
        csv_path,
        video_id,
        frames,
        annotations
    )

    cv2.destroyAllWindows()

    annotated_count = calculate_progress(
        frames,
        annotations
    )

    print(
        f"\nProgress: {annotated_count}/{len(frames)}"
    )
    print(f"Saved: {csv_path}")


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Annotate frames from one selected video folder."
        )
    )

    parser.add_argument(
        "video_folder",
        type=Path,
        help=(
            "Frame folder to annotate, for example "
            "./extracted_frames/v01"
        )
    )

    parser.add_argument(
        "--csv-folder",
        type=Path,
        default=None,
        help=(
            "Optional CSV output folder. By default, CSVs are "
            "saved in extracted_frames/annotated csvs."
        )
    )

    args = parser.parse_args()

    video_folder = (
        args.video_folder
        .expanduser()
        .resolve()
    )

    if not video_folder.exists():
        raise FileNotFoundError(
            f"Selected folder does not exist:\n{video_folder}"
        )

    if not video_folder.is_dir():
        raise NotADirectoryError(
            f"Selected path is not a folder:\n{video_folder}"
        )

    if args.csv_folder is not None:
        csv_output_folder = (
            args.csv_folder
            .expanduser()
            .resolve()
        )
    else:
        # For extracted_frames/v01, this creates:
        # extracted_frames/annotated csvs/
        csv_output_folder = (
            video_folder.parent /
            "annotated csvs"
        )

    annotate_folder(
        video_folder,
        csv_output_folder
    )


if __name__ == "__main__":
    main()