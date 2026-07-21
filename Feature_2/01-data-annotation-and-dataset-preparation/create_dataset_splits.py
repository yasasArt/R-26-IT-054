from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SPLITS = ("train", "validation", "test")
STATES = ("IDLE_SETUP", "SEWING")
SEGMENT_COLUMNS = ("video_name", "start_time_sec", "end_time_sec", "state")
EVENT_COLUMNS = ("video_name", "piece_no", "event_time_sec", "event_type")
METRIC_WEIGHTS = {
    "idle_setup_duration_sec": 1.0,
    "sewing_duration_sec": 1.0,
    "event_count": 1.0,
    "segment_count": 0.25,
}


@dataclass(frozen=True)
class VideoStats:
    video_name: str
    segment_count: int
    event_count: int
    idle_setup_duration_sec: float
    sewing_duration_sec: float

    @property
    def total_annotated_duration_sec(self) -> float:
        return self.idle_setup_duration_sec + self.sewing_duration_sec


def ratio(value: str) -> float:
    number = float(value)
    if not 0 < number < 1:
        raise argparse.ArgumentTypeError("Ratios must be greater than 0 and less than 1")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create video-level train, validation, and test splits balanced "
            "by state duration and event count."
        )
    )
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-ratio", type=ratio, default=0.70)
    parser.add_argument("--validation-ratio", type=ratio, default=0.15)
    parser.add_argument("--test-ratio", type=ratio, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--random-candidates",
        type=positive_int,
        default=5000,
        help="Random fixed-size assignments evaluated before local optimization",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacement of split files in an existing output directory",
    )
    args = parser.parse_args()
    total = args.train_ratio + args.validation_ratio + args.test_ratio
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        parser.error(f"Split ratios must sum to 1.0; found {total:.6f}")
    return args


def read_csv(path: Path, required_columns: Iterable[str]) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        missing = set(required_columns) - set(fieldnames)
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            clean_row = {key: value if value is not None else "" for key, value in row.items()}
            clean_row["__row_number"] = str(row_number)
            rows.append(clean_row)
    if not rows:
        raise ValueError(f"{path} contains no data rows")
    return fieldnames, rows # type: ignore


def parse_nonnegative_float(value: str, path: Path, row_number: str, column: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{path}:{row_number} has invalid {column}: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{path}:{row_number} has invalid {column}: {value!r}")
    return number


def natural_video_key(video_name: str) -> tuple[str, int, str]:
    stem = Path(video_name).stem
    prefix = stem.rstrip("0123456789")
    number_text = stem[len(prefix) :]
    number = int(number_text) if number_text else -1
    return prefix.lower(), number, video_name.lower()


def build_video_stats(
    segment_path: Path,
    segment_rows: list[dict[str, str]],
    event_path: Path,
    event_rows: list[dict[str, str]],
) -> list[VideoStats]:
    segment_counts: Counter[str] = Counter()
    durations: dict[str, Counter[str]] = defaultdict(Counter)
    previous_end: dict[str, float] = {}
    previous_start: dict[str, float] = {}

    ordered_segments = sorted(
        segment_rows,
        key=lambda row: (
            natural_video_key(row["video_name"].strip()),
            float(row["start_time_sec"]),
        ),
    )
    for row in ordered_segments:
        row_number = row["__row_number"]
        video_name = row["video_name"].strip()
        state = row["state"].strip().upper()
        if not video_name or Path(video_name).name != video_name:
            raise ValueError(f"{segment_path}:{row_number} has invalid video_name")
        if state not in STATES:
            raise ValueError(f"{segment_path}:{row_number} has invalid state {state!r}")
        start = parse_nonnegative_float(
            row["start_time_sec"], segment_path, row_number, "start_time_sec"
        )
        end = parse_nonnegative_float(
            row["end_time_sec"], segment_path, row_number, "end_time_sec"
        )
        if end <= start:
            raise ValueError(f"{segment_path}:{row_number} has a non-positive duration")
        if video_name in previous_start and start < previous_start[video_name]:
            raise ValueError(f"{segment_path}:{row_number} is not chronological")
        if video_name in previous_end and start < previous_end[video_name] - 1e-6:
            raise ValueError(f"{segment_path}:{row_number} overlaps the previous segment")
        previous_start[video_name] = start
        previous_end[video_name] = end
        segment_counts[video_name] += 1
        durations[video_name][state] += end - start # type: ignore

    event_counts: Counter[str] = Counter()
    last_piece: dict[str, int] = {}
    last_event_time: dict[str, float] = {}
    for row in sorted(
        event_rows,
        key=lambda item: (
            natural_video_key(item["video_name"].strip()),
            int(item["piece_no"]),
        ),
    ):
        row_number = row["__row_number"]
        video_name = row["video_name"].strip()
        if video_name not in segment_counts:
            raise ValueError(
                f"{event_path}:{row_number} references unknown video {video_name!r}"
            )
        try:
            piece_no = int(row["piece_no"])
        except ValueError as exc:
            raise ValueError(f"{event_path}:{row_number} has invalid piece_no") from exc
        event_time = parse_nonnegative_float(
            row["event_time_sec"], event_path, row_number, "event_time_sec"
        )
        if row["event_type"].strip() != "NORMAL_PIECE":
            raise ValueError(f"{event_path}:{row_number} has unsupported event_type")
        expected_piece = last_piece.get(video_name, 0) + 1
        if piece_no != expected_piece:
            raise ValueError(
                f"{event_path}:{row_number} expected piece_no {expected_piece}, found {piece_no}"
            )
        if event_time < last_event_time.get(video_name, -1.0):
            raise ValueError(f"{event_path}:{row_number} is not chronological")
        last_piece[video_name] = piece_no
        last_event_time[video_name] = event_time
        event_counts[video_name] += 1

    stats = [
        VideoStats(
            video_name=video_name,
            segment_count=segment_counts[video_name],
            event_count=event_counts[video_name],
            idle_setup_duration_sec=durations[video_name]["IDLE_SETUP"],
            sewing_duration_sec=durations[video_name]["SEWING"],
        )
        for video_name in sorted(segment_counts, key=natural_video_key)
    ]
    if len(stats) < 3:
        raise ValueError("At least three videos are required")
    for item in stats:
        if item.idle_setup_duration_sec <= 0 or item.sewing_duration_sec <= 0:
            raise ValueError(f"{item.video_name} does not contain both required states")
    return stats


def allocate_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    exact = {split: total * ratios[split] for split in SPLITS}
    counts = {split: math.floor(exact[split]) for split in SPLITS}
    remainder = total - sum(counts.values())
    order = sorted(
        SPLITS,
        key=lambda split: (exact[split] - counts[split], -SPLITS.index(split)),
        reverse=True,
    )
    for split in order[:remainder]:
        counts[split] += 1
    if any(counts[split] == 0 for split in SPLITS):
        raise ValueError(f"The requested ratios produce an empty split: {counts}")
    return counts


def metrics_for_videos(videos: Iterable[str], lookup: dict[str, VideoStats]) -> dict[str, float]:
    selected = [lookup[video] for video in videos]
    return {
        "segment_count": float(sum(item.segment_count for item in selected)),
        "event_count": float(sum(item.event_count for item in selected)),
        "idle_setup_duration_sec": sum(item.idle_setup_duration_sec for item in selected),
        "sewing_duration_sec": sum(item.sewing_duration_sec for item in selected),
    }


def assignment_score(
    assignment: dict[str, list[str]],
    lookup: dict[str, VideoStats],
    ratios: dict[str, float],
    global_metrics: dict[str, float],
) -> float:
    score = 0.0
    for split in SPLITS:
        metrics = metrics_for_videos(assignment[split], lookup)
        for metric, weight in METRIC_WEIGHTS.items():
            target = global_metrics[metric] * ratios[split]
            if target > 0:
                relative_error = (metrics[metric] - target) / target
                score += weight * relative_error * relative_error
    return score


def assignment_from_order(order: list[str], counts: dict[str, int]) -> dict[str, list[str]]:
    assignment: dict[str, list[str]] = {}
    position = 0
    for split in SPLITS:
        assignment[split] = order[position : position + counts[split]]
        position += counts[split]
    return assignment


def copy_assignment(assignment: dict[str, list[str]]) -> dict[str, list[str]]:
    return {split: list(assignment[split]) for split in SPLITS}


def optimize_assignment(
    stats: list[VideoStats],
    counts: dict[str, int],
    ratios: dict[str, float],
    seed: int,
    random_candidates: int,
) -> tuple[dict[str, list[str]], float]:
    lookup = {item.video_name: item for item in stats}
    global_metrics = metrics_for_videos(lookup, lookup)
    rng = random.Random(seed)
    video_names = list(lookup)
    best_assignment: dict[str, list[str]] | None = None
    best_score = math.inf

    for _ in range(random_candidates):
        order = list(video_names)
        rng.shuffle(order)
        candidate = assignment_from_order(order, counts)
        score = assignment_score(candidate, lookup, ratios, global_metrics)
        if score < best_score:
            best_assignment = candidate
            best_score = score

    assert best_assignment is not None

    # Deterministic best-improvement swaps retain exact video counts.
    while True:
        improved_assignment = None
        improved_score = best_score
        for first_index, first_split in enumerate(SPLITS):
            for second_split in SPLITS[first_index + 1 :]:
                for first_video in sorted(
                    best_assignment[first_split], key=natural_video_key
                ):
                    for second_video in sorted(
                        best_assignment[second_split], key=natural_video_key
                    ):
                        candidate = copy_assignment(best_assignment)
                        first_position = candidate[first_split].index(first_video)
                        second_position = candidate[second_split].index(second_video)
                        candidate[first_split][first_position] = second_video
                        candidate[second_split][second_position] = first_video
                        score = assignment_score(
                            candidate, lookup, ratios, global_metrics
                        )
                        if score < improved_score - 1e-15:
                            improved_assignment = candidate
                            improved_score = score
        if improved_assignment is None:
            break
        best_assignment = improved_assignment
        best_score = improved_score

    for split in SPLITS:
        best_assignment[split].sort(key=natural_video_key)
    return best_assignment, best_score


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv_atomic(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def without_internal_columns(row: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in row.items() if not key.startswith("__")}


def ensure_output_safe(output_dir: Path, overwrite: bool) -> None:
    known_output = output_dir / "split_manifest.csv"
    if known_output.exists() and not overwrite:
        raise FileExistsError(
            f"Split output already exists: {known_output}. Use --overwrite to replace it."
        )


def create_outputs(
    output_dir: Path,
    assignment: dict[str, list[str]],
    stats: list[VideoStats],
    segment_headers: list[str],
    segment_rows: list[dict[str, str]],
    event_headers: list[str],
    event_rows: list[dict[str, str]],
    ratios: dict[str, float],
    counts: dict[str, int],
    seed: int,
    objective_score: float,
    segment_path: Path,
    event_path: Path,
) -> None:
    lookup = {item.video_name: item for item in stats}
    split_by_video = {
        video: split for split in SPLITS for video in assignment[split]
    }
    manifest_rows = []
    for item in stats:
        manifest_rows.append(
            {
                "video_name": item.video_name,
                "split": split_by_video[item.video_name],
                "segment_count": item.segment_count,
                "event_count": item.event_count,
                "idle_setup_duration_sec": f"{item.idle_setup_duration_sec:.3f}",
                "sewing_duration_sec": f"{item.sewing_duration_sec:.3f}",
                "total_annotated_duration_sec": f"{item.total_annotated_duration_sec:.3f}",
            }
        )
    write_csv_atomic(
        output_dir / "split_manifest.csv",
        [
            "video_name",
            "split",
            "segment_count",
            "event_count",
            "idle_setup_duration_sec",
            "sewing_duration_sec",
            "total_annotated_duration_sec",
        ],
        manifest_rows,
    )

    global_metrics = metrics_for_videos(lookup, lookup)
    summary_rows = []
    for split in SPLITS:
        metrics = metrics_for_videos(assignment[split], lookup)
        summary_rows.append(
            {
                "split": split,
                "video_count": len(assignment[split]),
                "video_percentage": f"{len(assignment[split]) / len(stats) * 100:.3f}",
                "segment_count": int(metrics["segment_count"]),
                "event_count": int(metrics["event_count"]),
                "event_percentage": f"{metrics['event_count'] / global_metrics['event_count'] * 100:.3f}",
                "idle_setup_duration_sec": f"{metrics['idle_setup_duration_sec']:.3f}",
                "idle_setup_percentage": f"{metrics['idle_setup_duration_sec'] / global_metrics['idle_setup_duration_sec'] * 100:.3f}",
                "sewing_duration_sec": f"{metrics['sewing_duration_sec']:.3f}",
                "sewing_percentage": f"{metrics['sewing_duration_sec'] / global_metrics['sewing_duration_sec'] * 100:.3f}",
                "total_annotated_duration_sec": f"{metrics['idle_setup_duration_sec'] + metrics['sewing_duration_sec']:.3f}",
            }
        )
    write_csv_atomic(
        output_dir / "split_summary.csv",
        [
            "split",
            "video_count",
            "video_percentage",
            "segment_count",
            "event_count",
            "event_percentage",
            "idle_setup_duration_sec",
            "idle_setup_percentage",
            "sewing_duration_sec",
            "sewing_percentage",
            "total_annotated_duration_sec",
        ],
        summary_rows,
    )

    for split in SPLITS:
        selected = set(assignment[split])
        write_csv_atomic(
            output_dir / split / "videos.csv",
            ["video_name"],
            ({"video_name": video} for video in assignment[split]),
        )
        write_csv_atomic(
            output_dir / split / "segment_annotation.csv",
            segment_headers,
            (
                without_internal_columns(row)
                for row in segment_rows
                if row["video_name"].strip() in selected
            ), # type: ignore
        )
        write_csv_atomic(
            output_dir / split / "events.csv",
            event_headers,
            (
                without_internal_columns(row)
                for row in event_rows
                if row["video_name"].strip() in selected
            ), # type: ignore
        )

    config = {
        "seed": seed,
        "strategy": "fixed-count random search followed by deterministic cross-split swap optimization",
        "ratios": ratios,
        "video_counts": counts,
        "balanced_metrics": METRIC_WEIGHTS,
        "objective_score": objective_score,
        "sources": {
            "segments": {
                "path": str(segment_path),
                "sha256": sha256(segment_path),
            },
            "events": {"path": str(event_path), "sha256": sha256(event_path)},
        },
    }
    config_path = output_dir / "split_config.json"
    temporary_config = config_path.with_name(f".{config_path.name}.tmp")
    temporary_config.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_config, config_path)


def validate_outputs(
    output_dir: Path,
    total_videos: int,
    total_segments: int,
    total_events: int,
    expected_counts: dict[str, int],
) -> None:
    all_videos: list[str] = []
    segment_total = 0
    event_total = 0
    for split in SPLITS:
        _, videos = read_csv(output_dir / split / "videos.csv", ("video_name",))
        all_videos.extend(row["video_name"] for row in videos)
        if len(videos) != expected_counts[split]:
            raise RuntimeError(f"{split} video count does not match the target")
        _, segments = read_csv(
            output_dir / split / "segment_annotation.csv", SEGMENT_COLUMNS
        )
        _, events = read_csv(output_dir / split / "events.csv", EVENT_COLUMNS)
        segment_total += len(segments)
        event_total += len(events)
        selected = {row["video_name"] for row in videos}
        if {row["video_name"] for row in segments} - selected:
            raise RuntimeError(f"{split} contains leaked segment rows")
        if {row["video_name"] for row in events} - selected:
            raise RuntimeError(f"{split} contains leaked event rows")
    if len(all_videos) != total_videos or len(set(all_videos)) != total_videos:
        raise RuntimeError("Video leakage or missing videos detected")
    if segment_total != total_segments:
        raise RuntimeError("Split segment rows do not reconcile to the source")
    if event_total != total_events:
        raise RuntimeError("Split event rows do not reconcile to the source")


def main() -> int:
    args = parse_args()
    segment_path = args.segments.expanduser().resolve()
    event_path = args.events.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    ratios = {
        "train": args.train_ratio,
        "validation": args.validation_ratio,
        "test": args.test_ratio,
    }
    try:
        if not segment_path.is_file():
            raise FileNotFoundError(f"Segment annotations not found: {segment_path}")
        if not event_path.is_file():
            raise FileNotFoundError(f"Events not found: {event_path}")
        ensure_output_safe(output_dir, args.overwrite)
        segment_headers, segment_rows = read_csv(segment_path, SEGMENT_COLUMNS)
        event_headers, event_rows = read_csv(event_path, EVENT_COLUMNS)
        stats = build_video_stats(
            segment_path, segment_rows, event_path, event_rows
        )
        counts = allocate_counts(len(stats), ratios)
        assignment, objective_score = optimize_assignment(
            stats,
            counts,
            ratios,
            args.seed,
            args.random_candidates,
        )
        create_outputs(
            output_dir,
            assignment,
            stats,
            segment_headers,
            segment_rows,
            event_headers,
            event_rows,
            ratios,
            counts,
            args.seed,
            objective_score,
            segment_path,
            event_path,
        )
        validate_outputs(
            output_dir,
            len(stats),
            len(segment_rows),
            len(event_rows),
            counts,
        )
        print(f"Created video-level splits in: {output_dir}")
        print(f"Seed: {args.seed}")
        print(f"Objective score: {objective_score:.10f}")
        for split in SPLITS:
            print(f"{split}: {len(assignment[split])} videos")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
