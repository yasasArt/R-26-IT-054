from pathlib import Path
import cv2
import re

# Change these paths
video_folder = Path("./shuffled videos")
output_folder = Path("./extracted_frames")

# Required extraction rate
TARGET_FPS = 3

# JPEG quality: 0–100
JPEG_QUALITY = 95

video_extensions = {
    ".mp4", ".mkv", ".avi", ".mov",
    ".wmv", ".flv", ".webm", ".m4v"
}


def natural_sort_key(path):
    """
    Sort v01, v02, v10 correctly.
    """
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


if not video_folder.exists():
    raise FileNotFoundError(f"Video folder not found: {video_folder}")

output_folder.mkdir(parents=True, exist_ok=True)

# Find all supported videos
videos = sorted(
    [
        path for path in video_folder.iterdir()
        if path.is_file() and path.suffix.lower() in video_extensions
    ],
    key=natural_sort_key
)

if not videos:
    raise RuntimeError(f"No supported videos found in: {video_folder}")

print(f"Found {len(videos)} videos.")
print(f"Extracting frames at {TARGET_FPS} FPS.\n")

for video_number, video_path in enumerate(videos, start=1):

    # Example: v01.mp4 -> v01
    video_id = video_path.stem

    # Create an individual folder for the video
    video_output_folder = output_folder / video_id

    # Prevent mixing newly extracted frames with old frames
    if video_output_folder.exists() and any(video_output_folder.iterdir()):
        print(
            f"Skipped {video_path.name}: "
            f"output folder is not empty: {video_output_folder}"
        )
        continue

    video_output_folder.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        print(f"Could not open video: {video_path.name}")
        continue

    source_fps = capture.get(cv2.CAP_PROP_FPS)
    total_source_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = (
        total_source_frames / source_fps
        if source_fps > 0
        else 0
    )

    if source_fps <= 0:
        print(f"Invalid FPS detected for: {video_path.name}")
        capture.release()
        continue

    print(f"Processing: {video_path.name}")
    print(f"  Original FPS: {source_fps:.2f}")
    print(f"  Duration: {duration:.2f} seconds")

    source_frame_index = 0
    extracted_frame_index = 0

    # Index of the next source frame that should be saved
    next_target_frame = 0.0

    while True:
        success, frame = capture.read()

        if not success:
            break

        # Save a frame whenever the next 3 FPS sampling point is reached
        if source_frame_index >= round(next_target_frame):

            extracted_frame_index += 1

            frame_name = (
                f"{video_id}_{extracted_frame_index:03d}.jpg"
            )

            frame_path = video_output_folder / frame_name

            saved = cv2.imwrite(
                str(frame_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )

            if not saved:
                print(f"  Failed to save: {frame_path}")

            # Move to the next sampling position
            next_target_frame += source_fps / TARGET_FPS

        source_frame_index += 1

    capture.release()

    print(f"  Extracted frames: {extracted_frame_index}")
    print(f"  Saved to: {video_output_folder}\n")

print("Frame extraction completed successfully.")
print(f"Main output folder: {output_folder}")