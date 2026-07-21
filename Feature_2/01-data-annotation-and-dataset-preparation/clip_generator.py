from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


IDLE_SETUP = "IDLE_SETUP"
SEWING = "SEWING"
VALID_STATES = {IDLE_SETUP, SEWING}
SPLITS = ("train", "validation", "test")
REQUIRED_COLUMNS = {"video_name", "start_time_sec", "end_time_sec", "state"}
TIME_QUANTUM = Decimal("0.001")
EPSILON = Decimal("0.000001")


@dataclass(frozen=True)
class Segment:
    split: str
    video_name: str
    start_sec: Decimal
    end_sec: Decimal
    state: str
    segment_index: int
    source_row: int


@dataclass(frozen=True)
class ClipPlan:
    split: str
    clip_name: str
    relative_path: Path
    video_name: str
    segment_index: int
    clip_index_in_segment: int
    start_sec: Decimal
    end_sec: Decimal
    duration_sec: Decimal
    state: str
    segment_start_sec: Decimal
    segment_end_sec: Decimal


def positive_decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"Invalid number: {value}") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero")
    return number


def non_negative_decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"Invalid number: {value}") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("Value cannot be negative")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate final train, validation, and test clips without crossing "
            "annotation or video-split boundaries."
        )
    )
    parser.add_argument(
        "--videos-dir",
        type=Path,
        required=True,
        help="Directory containing the source videos",
    )
    parser.add_argument(
        "--splits-dir",
        type=Path,
        required=True,
        help=(
            "Directory containing train/, validation/, and test/ folders "
            "created by create_dataset_splits.py"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for class folders and clip_manifest.csv",
    )
    parser.add_argument(
        "--clip-duration-sec",
        type=positive_decimal,
        default=Decimal("1.5"),
        help="Duration of each clip in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--train-idle-stride-sec",
        type=positive_decimal,
        default=Decimal("1.0"),
        help="Training stride for IDLE_SETUP clips (default: 1.0)",
    )
    parser.add_argument(
        "--train-sewing-stride-sec",
        type=positive_decimal,
        default=Decimal("2.5"),
        help="Training stride for SEWING clips (default: 2.5)",
    )
    parser.add_argument(
        "--evaluation-stride-sec",
        type=positive_decimal,
        default=Decimal("1.5"),
        help="Validation and test stride for both states (default: 1.5)",
    )
    parser.add_argument(
        "--boundary-margin-sec",
        type=non_negative_decimal,
        default=Decimal("0.0"),
        help="Exclude this many seconds from both ends of each segment (default: 0)",
    )
    parser.add_argument(
        "--fps",
        type=positive_decimal,
        help="Optional output FPS; omitted to preserve source FPS",
    )
    parser.add_argument(
        "--width",
        type=positive_int,
        help="Optional output width; requires --height",
    )
    parser.add_argument(
        "--height",
        type=positive_int,
        help="Optional output height; requires --width",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="H.264 quality value, 0-51; lower is higher quality (default: 18)",
    )
    parser.add_argument(
        "--preset",
        default="medium",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
        help="FFmpeg x264 encoding preset (default: medium)",
    )
    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="FFmpeg executable name or path (default: ffmpeg)",
    )
    parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="FFprobe executable name or path (default: ffprobe)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Keep valid existing clips and generate only missing clips",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and write a planned manifest without encoding video",
    )
    parser.add_argument(
        "--skip-output-verification",
        action="store_true",
        help="Skip FFprobe duration verification after encoding",
    )
    args = parser.parse_args()

    if (args.width is None) != (args.height is None):
        parser.error("--width and --height must be provided together")
    if not 0 <= args.crf <= 51:
        parser.error("--crf must be between 0 and 51")
    return args


def decimal_from_csv(value: str, row_number: int, column: str) -> Decimal:
    try:
        number = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(
            f"Row {row_number}: {column} must be a valid number, found {value!r}"
        ) from exc
    if not number.is_finite():
        raise ValueError(f"Row {row_number}: {column} must be finite")
    return number


def load_segments(annotation_path: Path, split: str) -> list[Segment]:
    with annotation_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                f"Annotation CSV is missing columns: {', '.join(sorted(missing))}"
            )

        raw_rows: list[tuple[str, Decimal, Decimal, str, int]] = []
        for row_number, row in enumerate(reader, start=2):
            video_name = (row["video_name"] or "").strip()
            state = (row["state"] or "").strip().upper()
            start = decimal_from_csv(row["start_time_sec"] or "", row_number, "start_time_sec")
            end = decimal_from_csv(row["end_time_sec"] or "", row_number, "end_time_sec")
            if not video_name or Path(video_name).name != video_name:
                raise ValueError(
                    f"Row {row_number}: video_name must be a filename, found {video_name!r}"
                )
            if state not in VALID_STATES:
                raise ValueError(
                    f"Row {row_number}: unsupported state {state!r}; "
                    f"expected one of {sorted(VALID_STATES)}"
                )
            if start < 0 or end <= start:
                raise ValueError(
                    f"Row {row_number}: invalid interval {start} to {end}"
                )
            raw_rows.append((video_name, start, end, state, row_number))

    raw_rows.sort(key=lambda row: (natural_video_key(row[0]), row[1], row[2]))
    segments: list[Segment] = []
    current_video = None
    segment_index = 0
    previous_end: Decimal | None = None
    for video_name, start, end, state, row_number in raw_rows:
        if video_name != current_video:
            current_video = video_name
            segment_index = 1
            previous_end = None
        else:
            segment_index += 1
        if previous_end is not None and start < previous_end - EPSILON:
            raise ValueError(
                f"Row {row_number}: segment overlaps the previous {video_name} segment"
            )
        segments.append(
            Segment(split, video_name, start, end, state, segment_index, row_number)
        )
        previous_end = end

    if not segments:
        raise ValueError("Annotation CSV contains no segment rows")
    return segments


def natural_video_key(video_name: str) -> tuple[str, int, str]:
    stem = Path(video_name).stem
    prefix = stem.rstrip("0123456789")
    number_text = stem[len(prefix) :]
    number = int(number_text) if number_text else -1
    return prefix.lower(), number, video_name.lower()


def milliseconds_token(seconds: Decimal) -> str:
    milliseconds = (seconds * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(milliseconds):09d}"


def build_clip_plans(
    segments: list[Segment],
    clip_duration: Decimal,
    train_idle_stride: Decimal,
    train_sewing_stride: Decimal,
    evaluation_stride: Decimal,
    margin: Decimal,
) -> tuple[list[ClipPlan], list[Segment]]:
    plans: list[ClipPlan] = []
    skipped_segments: list[Segment] = []
    for segment in segments:
        if segment.split == "train":
            stride = (
                train_idle_stride
                if segment.state == IDLE_SETUP
                else train_sewing_stride
            )
        else:
            stride = evaluation_stride
        usable_start = segment.start_sec + margin
        usable_end = segment.end_sec - margin
        if usable_end - usable_start + EPSILON < clip_duration:
            skipped_segments.append(segment)
            continue

        clip_index = 1
        clip_start = usable_start
        while clip_start + clip_duration <= usable_end + EPSILON:
            clip_end = clip_start + clip_duration
            state_folder = segment.state.lower()
            clip_name = (
                f"{Path(segment.video_name).stem}"
                f"_s{segment.segment_index:04d}"
                f"_c{clip_index:03d}"
                f"_{state_folder}"
                f"_{milliseconds_token(clip_start)}"
                f"_{milliseconds_token(clip_end)}.mp4"
            )
            plans.append(
                ClipPlan(
                    split=segment.split,
                    clip_name=clip_name,
                    relative_path=Path(segment.split) / state_folder / clip_name,
                    video_name=segment.video_name,
                    segment_index=segment.segment_index,
                    clip_index_in_segment=clip_index,
                    start_sec=clip_start,
                    end_sec=clip_end,
                    duration_sec=clip_duration,
                    state=segment.state,
                    segment_start_sec=segment.start_sec,
                    segment_end_sec=segment.end_sec,
                )
            )
            clip_index += 1
            clip_start = usable_start + (clip_index - 1) * stride
    return plans, skipped_segments


def resolve_executable(value: str) -> str | None:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        return str(candidate.resolve()) if candidate.is_file() else None
    return shutil.which(value)


def ffmpeg_command(
    ffmpeg: str,
    source_path: Path,
    output_path: Path,
    plan: ClipPlan,
    fps: Decimal | None,
    width: int | None,
    height: int | None,
    crf: int,
    preset: str,
) -> list[str]:
    filters: list[str] = []
    if fps is not None:
        filters.append(f"fps={fps}")
    if width is not None and height is not None:
        filters.extend(
            [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                "setsar=1",
            ]
        )

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        str(plan.start_sec),
        "-i",
        str(source_path),
        "-t",
        str(plan.duration_sec),
        "-map",
        "0:v:0",
        "-an",
    ]
    if filters:
        command.extend(["-vf", ",".join(filters)])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]
    )
    return command


def probe_duration(ffprobe: str, video_path: Path) -> Decimal:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    return Decimal(payload["format"]["duration"])


def verify_clip(ffprobe: str, video_path: Path, expected_duration: Decimal) -> None:
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise RuntimeError(f"Clip was not created correctly: {video_path}")
    actual_duration = probe_duration(ffprobe, video_path)
    tolerance = max(Decimal("0.100"), expected_duration * Decimal("0.02"))
    if abs(actual_duration - expected_duration) > tolerance:
        raise RuntimeError(
            f"Unexpected duration for {video_path.name}: "
            f"expected {expected_duration}s, found {actual_duration}s"
        )


def format_decimal(value: Decimal) -> str:
    return str(value.quantize(TIME_QUANTUM, rounding=ROUND_HALF_UP))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_video_list(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if "video_name" not in (reader.fieldnames or []):
            raise ValueError(f"{path} is missing the video_name column")
        videos = [(row["video_name"] or "").strip() for row in reader]
    if not videos or any(not video for video in videos):
        raise ValueError(f"{path} contains an empty or invalid video list")
    if len(videos) != len(set(videos)):
        raise ValueError(f"{path} contains duplicate video names")
    return sorted(videos, key=natural_video_key)


def load_split_segments(splits_dir: Path) -> list[Segment]:
    all_segments: list[Segment] = []
    assigned_videos: dict[str, str] = {}
    for split in SPLITS:
        split_dir = splits_dir / split
        videos_path = split_dir / "videos.csv"
        annotations_path = split_dir / "segment_annotation.csv"
        if not videos_path.is_file():
            raise FileNotFoundError(f"Split video list not found: {videos_path}")
        if not annotations_path.is_file():
            raise FileNotFoundError(f"Split annotations not found: {annotations_path}")

        expected_videos = set(load_video_list(videos_path))
        for video_name in expected_videos:
            if video_name in assigned_videos:
                raise ValueError(
                    f"Video leakage: {video_name} occurs in both "
                    f"{assigned_videos[video_name]} and {split}"
                )
            assigned_videos[video_name] = split

        split_segments = load_segments(annotations_path, split)
        annotation_videos = {segment.video_name for segment in split_segments}
        missing_annotations = expected_videos - annotation_videos
        unexpected_annotations = annotation_videos - expected_videos
        if missing_annotations or unexpected_annotations:
            raise ValueError(
                f"{split} video-list/annotation mismatch. "
                f"Missing annotations: {sorted(missing_annotations)}; "
                f"unexpected annotations: {sorted(unexpected_annotations)}"
            )
        all_segments.extend(split_segments)

    if not all_segments:
        raise ValueError("No split annotations were loaded")
    return all_segments


def write_manifest(
    manifest_path: Path,
    plans: list[ClipPlan],
    statuses: dict[str, str],
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "split",
        "clip_name",
        "relative_clip_path",
        "video_name",
        "segment_index",
        "clip_index_in_segment",
        "start_time_sec",
        "end_time_sec",
        "duration_sec",
        "state",
        "source_segment_start_sec",
        "source_segment_end_sec",
        "status",
    ]
    temporary_path = manifest_path.with_suffix(".csv.tmp")
    with temporary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for plan in plans:
            writer.writerow(
                {
                    "split": plan.split,
                    "clip_name": plan.clip_name,
                    "relative_clip_path": plan.relative_path.as_posix(),
                    "video_name": plan.video_name,
                    "segment_index": plan.segment_index,
                    "clip_index_in_segment": plan.clip_index_in_segment,
                    "start_time_sec": format_decimal(plan.start_sec),
                    "end_time_sec": format_decimal(plan.end_sec),
                    "duration_sec": format_decimal(plan.duration_sec),
                    "state": plan.state,
                    "source_segment_start_sec": format_decimal(
                        plan.segment_start_sec
                    ),
                    "source_segment_end_sec": format_decimal(plan.segment_end_sec),
                    "status": statuses[plan.clip_name],
                }
            )
    os.replace(temporary_path, manifest_path)


def write_generation_config(
    output_dir: Path,
    splits_dir: Path,
    plans: list[ClipPlan],
    statuses: dict[str, str],
    args: argparse.Namespace,
) -> None:
    counts = Counter((plan.split, plan.state) for plan in plans)
    sources = {}
    for split in SPLITS:
        sources[split] = {}
        for filename in ("videos.csv", "segment_annotation.csv", "events.csv"):
            source_path = splits_dir / split / filename
            sources[split][filename] = {
                "path_relative_to_splits_dir": f"{split}/{filename}",
                "sha256": sha256_file(source_path),
            }
    config = {
        "mode": "dry_run" if args.dry_run else "generation",
        "parameters": {
            "clip_duration_sec": str(args.clip_duration_sec),
            "train_idle_stride_sec": str(args.train_idle_stride_sec),
            "train_sewing_stride_sec": str(args.train_sewing_stride_sec),
            "evaluation_stride_sec": str(args.evaluation_stride_sec),
            "boundary_margin_sec": str(args.boundary_margin_sec),
            "fps": str(args.fps) if args.fps is not None else "preserve_source",
            "width": args.width,
            "height": args.height,
            "codec": "libx264",
            "crf": args.crf,
            "preset": args.preset,
            "pixel_format": "yuv420p",
            "audio": "removed",
        },
        "planned_clip_count": len(plans),
        "counts": {
            split: {
                state: counts[split, state]
                for state in (IDLE_SETUP, SEWING)
            }
            for split in SPLITS
        },
        "status_counts": dict(sorted(Counter(statuses.values()).items())),
        "sources": sources,
    }
    config_path = output_dir / "generation_config.json"
    temporary_path = config_path.with_name(f".{config_path.name}.tmp")
    temporary_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, config_path)


def validate_source_videos(segments: list[Segment], videos_dir: Path) -> None:
    missing = sorted(
        {
            segment.video_name
            for segment in segments
            if not (videos_dir / segment.video_name).is_file()
        },
        key=natural_video_key,
    )
    if missing:
        preview = ", ".join(missing[:10])
        suffix = "..." if len(missing) > 10 else ""
        raise FileNotFoundError(
            f"Missing {len(missing)} source video(s): {preview}{suffix}"
        )


def ensure_output_is_safe(
    output_dir: Path,
    plans: list[ClipPlan],
    resume: bool,
    dry_run: bool,
) -> None:
    if resume or dry_run:
        return
    existing = [output_dir / plan.relative_path for plan in plans]
    first_existing = next((path for path in existing if path.exists()), None)
    if first_existing is not None:
        raise FileExistsError(
            f"Output clip already exists: {first_existing}. "
            "Use a new output directory or pass --resume."
        )


def print_summary(
    plans: list[ClipPlan],
    skipped_segments: list[Segment],
    statuses: dict[str, str],
    manifest_path: Path,
) -> None:
    state_counts = Counter(plan.state for plan in plans)
    split_state_counts = Counter((plan.split, plan.state) for plan in plans)
    status_counts = Counter(statuses.values())
    print("Clip generation complete")
    print(f"  Planned clips: {len(plans)}")
    print(f"  {IDLE_SETUP}: {state_counts[IDLE_SETUP]}")
    print(f"  {SEWING}: {state_counts[SEWING]}")
    print(f"  Segments shorter than the usable clip window: {len(skipped_segments)}")
    for split in SPLITS:
        split_total = sum(split_state_counts[split, state] for state in VALID_STATES)
        print(
            f"  {split}: {split_total} clips "
            f"({IDLE_SETUP}={split_state_counts[split, IDLE_SETUP]}, "
            f"{SEWING}={split_state_counts[split, SEWING]})"
        )
    for status in sorted(status_counts):
        print(f"  {status}: {status_counts[status]}")
    print(f"  Manifest: {manifest_path}")


def main() -> int:
    args = parse_args()
    videos_dir = args.videos_dir.expanduser().resolve()
    splits_dir = args.splits_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    try:
        if not videos_dir.is_dir():
            raise FileNotFoundError(f"Videos directory not found: {videos_dir}")
        if not splits_dir.is_dir():
            raise FileNotFoundError(f"Dataset splits directory not found: {splits_dir}")

        segments = load_split_segments(splits_dir)
        validate_source_videos(segments, videos_dir)
        plans, skipped_segments = build_clip_plans(
            segments,
            args.clip_duration_sec,
            args.train_idle_stride_sec,
            args.train_sewing_stride_sec,
            args.evaluation_stride_sec,
            args.boundary_margin_sec,
        )
        clip_names = [plan.clip_name for plan in plans]
        if len(clip_names) != len(set(clip_names)):
            raise ValueError("Duplicate clip names were generated")
        if not plans:
            raise ValueError(
                "No clips can be generated with the selected duration and margin"
            )
        ensure_output_is_safe(output_dir, plans, args.resume, args.dry_run)
        output_dir.mkdir(parents=True, exist_ok=True)

        statuses: dict[str, str] = {}
        if args.dry_run:
            statuses = {plan.clip_name: "PLANNED" for plan in plans}
        else:
            ffmpeg = resolve_executable(args.ffmpeg)
            if ffmpeg is None:
                raise FileNotFoundError(
                    "FFmpeg was not found. Install FFmpeg or pass its path with --ffmpeg."
                )
            ffprobe = resolve_executable(args.ffprobe)
            if not args.skip_output_verification and ffprobe is None:
                raise FileNotFoundError(
                    "FFprobe was not found. Install FFmpeg/FFprobe, pass --ffprobe, "
                    "or use --skip-output-verification."
                )

            for index, plan in enumerate(plans, start=1):
                source_path = videos_dir / plan.video_name
                output_path = output_dir / plan.relative_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.exists() and args.resume:
                    if not args.skip_output_verification:
                        verify_clip(ffprobe, output_path, plan.duration_sec) # type: ignore
                    statuses[plan.clip_name] = "EXISTING"
                    continue

                command = ffmpeg_command(
                    ffmpeg,
                    source_path,
                    output_path,
                    plan,
                    args.fps,
                    args.width,
                    args.height,
                    args.crf,
                    args.preset,
                )
                try:
                    subprocess.run(command, check=True)
                    if not args.skip_output_verification:
                        verify_clip(ffprobe, output_path, plan.duration_sec) # type: ignore
                except Exception:
                    output_path.unlink(missing_ok=True)
                    raise
                statuses[plan.clip_name] = "GENERATED"
                if index == 1 or index % 100 == 0 or index == len(plans):
                    print(f"Generated {index}/{len(plans)} clips", flush=True)

        manifest_path = output_dir / "clip_manifest.csv"
        write_manifest(manifest_path, plans, statuses)
        for split in SPLITS:
            split_plans = [plan for plan in plans if plan.split == split]
            write_manifest(
                output_dir / split / "clip_manifest.csv",
                split_plans,
                statuses,
            )
        write_generation_config(output_dir, splits_dir, plans, statuses, args)
        print_summary(plans, skipped_segments, statuses, manifest_path)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())