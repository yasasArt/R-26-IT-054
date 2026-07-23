from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path


SPLITS = ("train", "validation", "test")
STATES = ("IDLE_SETUP", "SEWING")
STATE_FOLDERS = {"IDLE_SETUP": "idle_setup", "SEWING": "sewing"}
REQUIRED_COLUMNS = {
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
}


@dataclass(frozen=True)
class ProbeResult:
    clip_name: str
    relative_path: str
    duration_sec: float
    width: int
    height: int
    fps: float
    codec: str
    pixel_format: str
    file_size_bytes: int


@dataclass(frozen=True)
class ValidationIssue:
    category: str
    clip_name: str
    relative_path: str
    detail: str


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate final clip files and manifests before model training."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Generated clip dataset containing clip_manifest.csv",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        required=True,
        help="Directory for validation reports",
    )
    parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="FFprobe executable name or path (default: ffprobe)",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=min(8, os.cpu_count() or 1),
        help="Number of parallel FFprobe processes (default: up to 8)",
    )
    parser.add_argument(
        "--duration-tolerance-sec",
        type=positive_float,
        default=0.10,
        help="Maximum allowed duration difference in seconds (default: 0.10)",
    )
    parser.add_argument(
        "--progress-every",
        type=positive_int,
        default=500,
        help="Print progress after this many probes (default: 500)",
    )
    return parser.parse_args()


def resolve_executable(value: str) -> str | None:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        return str(candidate.resolve()) if candidate.is_file() else None
    return shutil.which(value)


def read_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        missing = REQUIRED_COLUMNS - set(fieldnames)
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")
        rows = [
            {key: value if value is not None else "" for key, value in row.items()}
            for row in reader
        ]
    if not rows:
        raise ValueError(f"{path} contains no clip rows")
    return fieldnames, rows # type: ignore


def finite_float(value: str, column: str, clip_name: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{clip_name}: invalid {column}={value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{clip_name}: non-finite {column}")
    return number


def validate_manifest_rows(
    dataset_dir: Path, rows: list[dict[str, str]]
) -> tuple[list[ValidationIssue], dict[str, Path]]:
    issues: list[ValidationIssue] = []
    paths: dict[str, Path] = {}
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    video_splits: dict[str, str] = {}
    dataset_root = dataset_dir.resolve()

    for row in rows:
        clip_name = row["clip_name"].strip()
        relative_path = row["relative_clip_path"].strip()
        split = row["split"].strip()
        state = row["state"].strip()
        video_name = row["video_name"].strip()

        def issue(category: str, detail: str) -> None:
            issues.append(
                ValidationIssue(category, clip_name, relative_path, detail)
            )

        if not clip_name or Path(clip_name).name != clip_name:
            issue("manifest", "Invalid clip_name")
        if clip_name in seen_names:
            issue("duplicate", "Duplicate clip_name")
        seen_names.add(clip_name)
        if relative_path in seen_paths:
            issue("duplicate", "Duplicate relative_clip_path")
        seen_paths.add(relative_path)

        resolved_path = (dataset_dir / relative_path).resolve()
        try:
            resolved_path.relative_to(dataset_root)
        except ValueError:
            issue("path", "Path escapes the dataset directory")
        paths[clip_name] = resolved_path

        if split not in SPLITS:
            issue("manifest", f"Unsupported split {split!r}")
        if state not in STATES:
            issue("manifest", f"Unsupported state {state!r}")
        if split in SPLITS and state in STATES:
            expected_prefix = f"{split}/{STATE_FOLDERS[state]}/"
            if not relative_path.startswith(expected_prefix):
                issue("path", f"Expected path prefix {expected_prefix!r}")
        if Path(relative_path).name != clip_name:
            issue("path", "clip_name does not match relative path filename")

        previous_split = video_splits.setdefault(video_name, split)
        if previous_split != split:
            issue(
                "leakage",
                f"{video_name} occurs in both {previous_split} and {split}",
            )

        try:
            start = finite_float(row["start_time_sec"], "start_time_sec", clip_name)
            end = finite_float(row["end_time_sec"], "end_time_sec", clip_name)
            duration = finite_float(row["duration_sec"], "duration_sec", clip_name)
            segment_start = finite_float(
                row["source_segment_start_sec"],
                "source_segment_start_sec",
                clip_name,
            )
            segment_end = finite_float(
                row["source_segment_end_sec"],
                "source_segment_end_sec",
                clip_name,
            )
            if start < segment_start - 0.001 or end > segment_end + 0.001:
                issue("boundary", "Clip extends outside its source segment")
            if end <= start or duration <= 0:
                issue("duration", "Non-positive clip interval")
            if abs((end - start) - duration) > 0.0015:
                issue("duration", "Manifest interval does not match duration_sec")
        except ValueError as exc:
            issue("manifest", str(exc))

        if row["status"].strip() not in {"GENERATED", "EXISTING"}:
            issue("status", f"Unexpected final status {row['status']!r}")

    return issues, paths


def validate_split_manifests(
    dataset_dir: Path, combined_rows: list[dict[str, str]]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    combined_by_name = {row["clip_name"]: row for row in combined_rows}
    for split in SPLITS:
        split_path = dataset_dir / split / "clip_manifest.csv"
        if not split_path.is_file():
            issues.append(
                ValidationIssue(
                    "split_manifest", "", str(split_path), "Missing split manifest"
                )
            )
            continue
        _, split_rows = read_manifest(split_path)
        expected_names = {
            row["clip_name"] for row in combined_rows if row["split"] == split
        }
        actual_names = {row["clip_name"] for row in split_rows}
        if expected_names != actual_names:
            issues.append(
                ValidationIssue(
                    "split_manifest",
                    "",
                    str(split_path),
                    f"Name mismatch: expected {len(expected_names)}, found {len(actual_names)}",
                )
            )
        for row in split_rows:
            combined = combined_by_name.get(row["clip_name"])
            if combined is not None and row != combined:
                issues.append(
                    ValidationIssue(
                        "split_manifest",
                        row["clip_name"],
                        row["relative_clip_path"],
                        "Row differs from combined manifest",
                    )
                )
    return issues


def parse_fps(value: str) -> float:
    if not value or value == "0/0":
        return 0.0
    return float(Fraction(value))


def probe_clip(
    ffprobe: str,
    dataset_dir: Path,
    row: dict[str, str],
    tolerance: float,
) -> tuple[ProbeResult | None, ValidationIssue | None]:
    clip_name = row["clip_name"]
    relative_path = row["relative_clip_path"]
    clip_path = dataset_dir / relative_path
    if not clip_path.is_file():
        return None, ValidationIssue(
            "missing_file", clip_name, relative_path, "Clip file does not exist"
        )
    if clip_path.stat().st_size == 0:
        return None, ValidationIssue(
            "empty_file", clip_name, relative_path, "Clip file is empty"
        )
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,width,height,avg_frame_rate,pix_fmt:format=duration",
                "-of",
                "json",
                str(clip_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        if len(streams) != 1:
            raise ValueError(f"Expected one video stream, found {len(streams)}")
        stream = streams[0]
        actual_duration = float(payload["format"]["duration"])
        expected_duration = float(row["duration_sec"])
        if abs(actual_duration - expected_duration) > tolerance:
            return None, ValidationIssue(
                "duration",
                clip_name,
                relative_path,
                f"Expected {expected_duration:.3f}s, found {actual_duration:.3f}s",
            )
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        fps = parse_fps(stream.get("avg_frame_rate", "0/0"))
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError(
                f"Invalid stream metadata: width={width}, height={height}, fps={fps}"
            )
        return (
            ProbeResult(
                clip_name=clip_name,
                relative_path=relative_path,
                duration_sec=actual_duration,
                width=width,
                height=height,
                fps=fps,
                codec=str(stream.get("codec_name", "")),
                pixel_format=str(stream.get("pix_fmt", "")),
                file_size_bytes=clip_path.stat().st_size,
            ),
            None,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        return None, ValidationIssue(
            "probe", clip_name, relative_path, f"FFprobe failed: {exc}"
        )


def write_csv_atomic(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def summarize(
    rows: list[dict[str, str]], results: list[ProbeResult], issues: list[ValidationIssue]
) -> dict[str, object]:
    split_state_counts = Counter((row["split"], row["state"]) for row in rows)
    status_counts = Counter(row["status"] for row in rows)
    resolution_counts = Counter(f"{r.width}x{r.height}" for r in results)
    fps_counts = Counter(f"{r.fps:.3f}" for r in results)
    codec_counts = Counter(r.codec for r in results)
    pixel_format_counts = Counter(r.pixel_format for r in results)
    issue_counts = Counter(issue.category for issue in issues)
    video_sets = defaultdict(set)
    for row in rows:
        video_sets[row["split"]].add(row["video_name"])
    durations = [result.duration_sec for result in results]
    file_sizes = [result.file_size_bytes for result in results]
    return {
        "passed": not issues and len(results) == len(rows),
        "manifest_clip_count": len(rows),
        "successfully_probed_clip_count": len(results),
        "issue_count": len(issues),
        "issue_counts": dict(sorted(issue_counts.items())),
        "video_counts": {split: len(video_sets[split]) for split in SPLITS},
        "clip_counts": {
            split: {
                state: split_state_counts[split, state] for state in STATES
            }
            for split in SPLITS
        },
        "status_counts": dict(sorted(status_counts.items())),
        "duration_sec": {
            "minimum": min(durations) if durations else None,
            "maximum": max(durations) if durations else None,
            "mean": sum(durations) / len(durations) if durations else None,
        },
        "file_size_bytes": {
            "minimum": min(file_sizes) if file_sizes else None,
            "maximum": max(file_sizes) if file_sizes else None,
            "mean": sum(file_sizes) / len(file_sizes) if file_sizes else None,
            "total": sum(file_sizes),
        },
        "resolution_counts": dict(sorted(resolution_counts.items())),
        "fps_counts": dict(sorted(fps_counts.items())),
        "codec_counts": dict(sorted(codec_counts.items())),
        "pixel_format_counts": dict(sorted(pixel_format_counts.items())),
    }


def write_reports(
    report_dir: Path,
    summary: dict[str, object],
    issues: list[ValidationIssue],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "clip_validation_report.json"
    temporary_json = json_path.with_name(f".{json_path.name}.tmp")
    temporary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_json, json_path)

    summary_rows = [
        {"metric": "passed", "value": summary["passed"]},
        {"metric": "manifest_clip_count", "value": summary["manifest_clip_count"]},
        {
            "metric": "successfully_probed_clip_count",
            "value": summary["successfully_probed_clip_count"],
        },
        {"metric": "issue_count", "value": summary["issue_count"]},
    ]
    for split in SPLITS:
        summary_rows.append(
            {"metric": f"{split}_video_count", "value": summary["video_counts"][split]} # type: ignore
        )
        for state in STATES:
            summary_rows.append(
                {
                    "metric": f"{split}_{state.lower()}_clip_count",
                    "value": summary["clip_counts"][split][state], # type: ignore
                }
            )
    write_csv_atomic(
        report_dir / "clip_validation_summary.csv",
        ["metric", "value"],
        summary_rows,
    )
    write_csv_atomic(
        report_dir / "clip_validation_issues.csv",
        ["category", "clip_name", "relative_path", "detail"],
        [asdict(issue) for issue in issues],
    )


def main() -> int:
    args = parse_args()
    dataset_dir = args.dataset_dir.expanduser().resolve()
    report_dir = args.report_dir.expanduser().resolve()
    manifest_path = dataset_dir / "clip_manifest.csv"
    try:
        if not dataset_dir.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Combined manifest not found: {manifest_path}")
        ffprobe = resolve_executable(args.ffprobe)
        if ffprobe is None:
            raise FileNotFoundError(
                "FFprobe was not found. Install FFmpeg or pass --ffprobe."
            )

        _, rows = read_manifest(manifest_path)
        issues, expected_paths = validate_manifest_rows(dataset_dir, rows)
        issues.extend(validate_split_manifests(dataset_dir, rows))

        actual_paths = {
            path.resolve()
            for path in dataset_dir.rglob("*.mp4")
            if path.is_file()
        }
        expected_path_set = set(expected_paths.values())
        for orphan in sorted(actual_paths - expected_path_set):
            issues.append(
                ValidationIssue(
                    "orphan_file",
                    orphan.name,
                    str(orphan.relative_to(dataset_dir)),
                    "MP4 file is not listed in the combined manifest",
                )
            )

        results: list[ProbeResult] = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    probe_clip,
                    ffprobe,
                    dataset_dir,
                    row,
                    args.duration_tolerance_sec,
                ): row["clip_name"]
                for row in rows
            }
            completed = 0
            for future in as_completed(futures):
                result, issue = future.result()
                if result is not None:
                    results.append(result)
                if issue is not None:
                    issues.append(issue)
                completed += 1
                if completed % args.progress_every == 0 or completed == len(rows):
                    print(f"Probed {completed}/{len(rows)} clips", flush=True)

        results.sort(key=lambda result: result.relative_path)
        issues.sort(key=lambda issue: (issue.category, issue.relative_path, issue.detail))
        summary = summarize(rows, results, issues)
        write_reports(report_dir, summary, issues)
        print(json.dumps(summary, indent=2))
        print(f"Reports: {report_dir}")
        return 0 if summary["passed"] else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
