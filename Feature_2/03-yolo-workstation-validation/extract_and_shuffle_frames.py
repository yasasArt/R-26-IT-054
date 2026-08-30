import argparse
import random
import shutil
from pathlib import Path

import cv2

VIDEO_INPUT = "./raw_videos"
OUTPUT_DIR = "./shuffled_frames"
TARGET_FPS = 3.0
IMAGE_FORMAT = "jpg"
RANDOM_SEED = 42
CLEAN_OUTPUT_DIR = True

SUPPORTED_VIDEO_EXTENSIONS = {".mp4"}
SUPPORTED_IMAGE_FORMATS = {"jpg", "png"}


def is_video_file(path: Path) -> bool:
    
    return path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def collect_video_files(video_path: Path) -> list[Path]:
    
    if is_video_file(video_path):
        return [video_path]

    if video_path.is_dir():
        videos: list[Path] = []
        for ext in SUPPORTED_VIDEO_EXTENSIONS:
            videos.extend(video_path.rglob(f"*{ext}"))
        return sorted(videos)

    raise FileNotFoundError(
        f"Video path not found or unsupported: {video_path}\n"
        "Place videos inside ./videos or pass a custom path using --video."
    )


def prepare_output_dir(output_dir: Path, clean_output: bool) -> None:
    
    if clean_output and output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)


def get_frame_interval(original_fps: float, target_fps: float, video_name: str) -> int:
    
    if original_fps <= 0:
        print(f"[WARNING] Could not read FPS for {video_name}. Using 30 FPS as fallback.")
        original_fps = 30.0

    return max(int(round(original_fps / target_fps)), 1)


def extract_frames_from_video(
    video_path: Path,
    target_fps: float,
    image_format: str,
) -> list[tuple[str, object]]:
    
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(f"[FAILED] Could not open video: {video_path}")
        return []

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = get_frame_interval(original_fps, target_fps, video_path.name)

    frame_index = 0
    saved_count = 0
    extracted_frames: list[tuple[str, object]] = []
    video_stem = video_path.stem

    while True:
        success, frame = cap.read()

        if not success:
            break

        if frame_index % frame_interval == 0:
            frame_name = f"{video_stem}_frame_{saved_count:06d}.{image_format}"
            extracted_frames.append((frame_name, frame.copy()))
            saved_count += 1

        frame_index += 1

    cap.release()

    print(f"[DONE] {video_path.name} -> {saved_count} frames extracted")
    return extracted_frames


def save_shuffled_frames(
    frames: list[tuple[str, object]],
    output_dir: Path,
    seed: int,
    image_format: str,
) -> None:
    
    random.seed(seed)
    random.shuffle(frames)

    for index, (original_name, frame) in enumerate(frames):
        output_name = f"frame_{index:06d}_{Path(original_name).stem}.{image_format}"
        output_path = output_dir / output_name
        cv2.imwrite(str(output_path), frame) # type: ignore

    print(f"[DONE] Shuffled frames saved: {len(frames)}")
    print(f"[INFO] Output folder: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract frames from videos and save shuffled frames into one folder."
    )

    parser.add_argument(
        "--video",
        default=VIDEO_INPUT,
        help=f"Path to one video file or folder containing videos. Default: {VIDEO_INPUT}",
    )

    parser.add_argument(
        "--output",
        default=OUTPUT_DIR,
        help=f"Output folder for shuffled frames. Default: {OUTPUT_DIR}",
    )

    parser.add_argument(
        "--fps",
        type=float,
        default=TARGET_FPS,
        help=f"Target extraction FPS. Default: {TARGET_FPS}",
    )

    parser.add_argument(
        "--format",
        choices=sorted(SUPPORTED_IMAGE_FORMATS),
        default=IMAGE_FORMAT,
        help=f"Output image format. Default: {IMAGE_FORMAT}",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Random seed for reproducible shuffle. Default: {RANDOM_SEED}",
    )

    parser.add_argument(
        "--keep-old-output",
        action="store_true",
        help="Do not delete existing files in the output folder before saving new frames.",
    )

    args = parser.parse_args()

    if args.fps <= 0:
        raise ValueError("--fps must be greater than 0")

    video_path = Path(args.video).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    videos = collect_video_files(video_path)
    prepare_output_dir(output_dir, clean_output=not args.keep_old_output)

    print("====================================")
    print("Extract and Shuffle Frames for YOLO")
    print("====================================")
    print(f"Videos found: {len(videos)}")
    print(f"Video input: {video_path}")
    print(f"Target FPS: {args.fps}")
    print(f"Image format: {args.format}")
    print(f"Random seed: {args.seed}")
    print(f"Output folder: {output_dir}")
    print("====================================\n")

    all_frames: list[tuple[str, object]] = []

    for video in videos:
        frames = extract_frames_from_video(
            video_path=video,
            target_fps=args.fps,
            image_format=args.format,
        )
        all_frames.extend(frames)

    if not all_frames:
        print("[INFO] No frames extracted.")
        return

    save_shuffled_frames(
        frames=all_frames,
        output_dir=output_dir,
        seed=args.seed,
        image_format=args.format,
    )

    print("\n[FINISHED] Frame extraction and shuffle completed successfully.")


if __name__ == "__main__":
    main()