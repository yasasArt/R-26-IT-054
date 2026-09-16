from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

ORIGINAL_ANNOTATION_PATH = (
    PROJECT_ROOT
    / "00_protected_baseline"
    / "segment_annotation.csv"
)

ENHANCED_ANNOTATION_PATH = (
    PROJECT_ROOT
    / "01_data_preparation"
    / "outputs"
    / "segment_annotation_with_operation.csv"
)

SPLIT_MANIFEST_PATH = (
    PROJECT_ROOT
    / "00_protected_baseline"
    / "split_manifest.csv"
)

CLIP_MANIFEST_PATH = (
    PROJECT_ROOT
    / "00_protected_baseline"
    / "clip_manifest.csv"
)

REPORTS_DIR = SCRIPT_DIR / "reports"

OPERATION_REPORT_PATH = (
    REPORTS_DIR
    / "operation_distribution.csv"
)

SPLIT_REPORT_PATH = (
    REPORTS_DIR
    / "split_operation_distribution.csv"
)

SUMMARY_REPORT_PATH = (
    REPORTS_DIR
    / "validation_summary.json"
)


# ---------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------

ORIGINAL_COLUMNS = (
    "video_name",
    "start_time_sec",
    "end_time_sec",
    "state",
)

ENHANCED_COLUMNS = (
    "video_name",
    "start_time_sec",
    "end_time_sec",
    "state",
    "operation_type",
)

SPLIT_COLUMNS = (
    "video_name",
    "split",
)

CLIP_COLUMNS = (
    "split",
    "video_name",
    "state",
)

ALLOWED_STATES = (
    "IDLE_SETUP",
    "SEWING",
)

ALLOWED_OPERATIONS = (
    "COLLAR",
    "POCKET",
    "SLEEVE",
)

ALLOWED_SPLITS = (
    "train",
    "validation",
    "test",
)


# ---------------------------------------------------------
# General file helpers
# ---------------------------------------------------------

def read_csv(
    file_path: Path,
    required_columns: tuple[str, ...],
) -> list[dict[str, str]]:
    """
    Read a CSV file and validate its required columns.
    """

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Required file was not found: {file_path}"
        )

    with file_path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        reader = csv.DictReader(csv_file)
        available_columns = reader.fieldnames or []

        missing_columns = [
            column
            for column in required_columns
            if column not in available_columns
        ]

        if missing_columns:
            raise ValueError(
                f"{file_path.name} is missing columns: "
                f"{', '.join(missing_columns)}"
            )

        rows: list[dict[str, str]] = []

        for row_number, row in enumerate(reader, start=2):
            clean_row = {
                column: (value or "").strip()
                for column, value in row.items()
            }

            clean_row["__row_number"] = str(row_number)
            rows.append(clean_row)

    if not rows:
        raise ValueError(
            f"{file_path.name} does not contain any data rows."
        )

    return rows


def write_csv(
    file_path: Path,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    """
    Write a CSV file safely using a temporary file.
    """

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = file_path.with_name(
        f".{file_path.name}.tmp"
    )

    with temporary_path.open(
        mode="w",
        encoding="utf-8",
        newline="",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)

    os.replace(
        temporary_path,
        file_path,
    )


def write_json(
    file_path: Path,
    data: dict[str, Any],
) -> None:
    """
    Save the validation summary as formatted JSON.
    """

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = file_path.with_name(
        f".{file_path.name}.tmp"
    )

    temporary_path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )

    os.replace(
        temporary_path,
        file_path,
    )


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate a SHA-256 checksum for reproducibility.
    """

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


# ---------------------------------------------------------
# Annotation validation
# ---------------------------------------------------------

def validate_annotations(
    original_rows: list[dict[str, str]],
    enhanced_rows: list[dict[str, str]],
) -> dict[str, str]:
    """
    Confirm that operation_type is the only dataset change.
    """

    checks: dict[str, str] = {}

    if len(original_rows) != len(enhanced_rows):
        raise ValueError(
            "The original and enhanced annotations have "
            "different row counts."
        )

    checks["row_count_preserved"] = "PASS"

    duplicate_rows: set[
        tuple[str, str, str, str, str]
    ] = set()

    seen_rows: set[
        tuple[str, str, str, str, str]
    ] = set()

    operations_by_video: dict[str, set[str]] = defaultdict(set)
    segments_by_video: dict[str, list[tuple[float, float]]] = (
        defaultdict(list)
    )

    for index, (original, enhanced) in enumerate(
        zip(original_rows, enhanced_rows),
        start=2,
    ):
        # Check that all original values remain unchanged.
        for column in ORIGINAL_COLUMNS:
            if original[column] != enhanced[column]:
                raise ValueError(
                    f"Row {index} changed in column "
                    f"{column!r}. Only operation_type may be added."
                )

        video_name = enhanced["video_name"]
        state = enhanced["state"]
        operation_type = enhanced["operation_type"]

        if not video_name:
            raise ValueError(
                f"Enhanced annotation row {index} "
                f"has an empty video_name."
            )

        if state not in ALLOWED_STATES:
            raise ValueError(
                f"Enhanced annotation row {index} has "
                f"invalid state {state!r}."
            )

        if operation_type not in ALLOWED_OPERATIONS:
            raise ValueError(
                f"Enhanced annotation row {index} has "
                f"invalid operation_type {operation_type!r}."
            )

        try:
            start_time = float(
                enhanced["start_time_sec"]
            )

            end_time = float(
                enhanced["end_time_sec"]
            )

        except ValueError as error:
            raise ValueError(
                f"Enhanced annotation row {index} "
                f"has invalid time values."
            ) from error

        if start_time < 0:
            raise ValueError(
                f"Enhanced annotation row {index} "
                f"has a negative start time."
            )

        if end_time <= start_time:
            raise ValueError(
                f"Enhanced annotation row {index} "
                f"has an invalid time range."
            )

        row_key = (
            video_name,
            enhanced["start_time_sec"],
            enhanced["end_time_sec"],
            state,
            operation_type,
        )

        if row_key in seen_rows:
            duplicate_rows.add(row_key)

        seen_rows.add(row_key)

        operations_by_video[video_name].add(
            operation_type
        )

        segments_by_video[video_name].append(
            (start_time, end_time)
        )

    if duplicate_rows:
        raise ValueError(
            f"Found {len(duplicate_rows)} duplicate "
            f"enhanced annotation rows."
        )

    checks["no_duplicate_rows"] = "PASS"
    checks["original_columns_unchanged"] = "PASS"
    checks["valid_state_labels"] = "PASS"
    checks["valid_operation_labels"] = "PASS"
    checks["valid_time_ranges"] = "PASS"

    # Each video must have only one operation type.
    invalid_video_operations = {
        video_name: sorted(operations)
        for video_name, operations
        in operations_by_video.items()
        if len(operations) != 1
    }

    if invalid_video_operations:
        raise ValueError(
            "Some videos contain more than one operation: "
            f"{invalid_video_operations}"
        )

    checks["one_operation_per_video"] = "PASS"

    # Check for overlapping segments.
    for video_name, time_ranges in segments_by_video.items():
        ordered_ranges = sorted(time_ranges)

        for current_index in range(
            1,
            len(ordered_ranges),
        ):
            previous_end = ordered_ranges[
                current_index - 1
            ][1]

            current_start = ordered_ranges[
                current_index
            ][0]

            if current_start < previous_end - 1e-6:
                raise ValueError(
                    f"{video_name} contains overlapping "
                    f"annotation segments."
                )

    checks["no_overlapping_segments"] = "PASS"

    return checks


# ---------------------------------------------------------
# Video and operation lookups
# ---------------------------------------------------------

def create_operation_lookup(
    enhanced_rows: list[dict[str, str]],
) -> dict[str, str]:
    """
    Create video_name -> operation_type mapping.
    """

    operation_lookup: dict[str, str] = {}

    for row in enhanced_rows:
        video_name = row["video_name"]
        operation_type = row["operation_type"]

        existing_operation = operation_lookup.get(
            video_name
        )

        if (
            existing_operation is not None
            and existing_operation != operation_type
        ):
            raise ValueError(
                f"{video_name} has conflicting "
                f"operation types."
            )

        operation_lookup[video_name] = operation_type

    return operation_lookup


def create_split_lookup(
    split_rows: list[dict[str, str]],
) -> dict[str, str]:
    """
    Create video_name -> split mapping.
    """

    split_lookup: dict[str, str] = {}

    for row in split_rows:
        row_number = row["__row_number"]
        video_name = row["video_name"]
        split = row["split"]

        if split not in ALLOWED_SPLITS:
            raise ValueError(
                f"Split manifest row {row_number} "
                f"contains invalid split {split!r}."
            )

        if video_name in split_lookup:
            raise ValueError(
                f"{video_name} appears more than once "
                f"in the split manifest."
            )

        split_lookup[video_name] = split

    return split_lookup


def validate_video_sets(
    operation_lookup: dict[str, str],
    split_lookup: dict[str, str],
) -> None:
    """
    Confirm that annotations and split manifest use the same videos.
    """

    annotation_videos = set(operation_lookup)
    split_videos = set(split_lookup)

    missing_from_splits = sorted(
        annotation_videos - split_videos
    )

    unknown_split_videos = sorted(
        split_videos - annotation_videos
    )

    if missing_from_splits:
        raise ValueError(
            "These annotated videos are missing from "
            "the split manifest:\n"
            + "\n".join(missing_from_splits)
        )

    if unknown_split_videos:
        raise ValueError(
            "The split manifest contains unknown videos:\n"
            + "\n".join(unknown_split_videos)
        )


# ---------------------------------------------------------
# Clip-manifest validation
# ---------------------------------------------------------

def validate_clip_manifest(
    clip_rows: list[dict[str, str]],
    operation_lookup: dict[str, str],
    split_lookup: dict[str, str],
) -> dict[tuple[str, str], dict[str, int]]:
    """
    Validate clip references and count clips by split and operation.
    """

    clip_statistics: dict[
        tuple[str, str],
        dict[str, int],
    ] = defaultdict(
        lambda: {
            "total_clip_count": 0,
            "idle_setup_clip_count": 0,
            "sewing_clip_count": 0,
        }
    )

    for row in clip_rows:
        row_number = row["__row_number"]
        video_name = row["video_name"]
        split = row["split"]
        state = row["state"]

        if video_name not in operation_lookup:
            raise ValueError(
                f"Clip row {row_number} references "
                f"unknown video {video_name!r}."
            )

        if split not in ALLOWED_SPLITS:
            raise ValueError(
                f"Clip row {row_number} contains "
                f"invalid split {split!r}."
            )

        if state not in ALLOWED_STATES:
            raise ValueError(
                f"Clip row {row_number} contains "
                f"invalid state {state!r}."
            )

        expected_split = split_lookup[video_name]

        if split != expected_split:
            raise ValueError(
                f"Clip row {row_number} assigns "
                f"{video_name} to {split}, but the "
                f"split manifest assigns it to "
                f"{expected_split}."
            )

        operation_type = operation_lookup[video_name]
        key = (split, operation_type)

        clip_statistics[key][
            "total_clip_count"
        ] += 1

        if state == "IDLE_SETUP":
            clip_statistics[key][
                "idle_setup_clip_count"
            ] += 1

        if state == "SEWING":
            clip_statistics[key][
                "sewing_clip_count"
            ] += 1

    return clip_statistics


# ---------------------------------------------------------
# Report calculations
# ---------------------------------------------------------

def create_operation_distribution(
    enhanced_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Summarize the complete dataset by operation.
    """

    statistics: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "videos": set(),
            "segment_count": 0,
            "idle_setup_segment_count": 0,
            "sewing_segment_count": 0,
            "idle_setup_duration_sec": 0.0,
            "sewing_duration_sec": 0.0,
        }
    )

    for row in enhanced_rows:
        operation_type = row["operation_type"]
        state = row["state"]

        duration = (
            float(row["end_time_sec"])
            - float(row["start_time_sec"])
        )

        operation_stats = statistics[
            operation_type
        ]

        operation_stats["videos"].add(
            row["video_name"]
        )

        operation_stats["segment_count"] += 1

        if state == "IDLE_SETUP":
            operation_stats[
                "idle_setup_segment_count"
            ] += 1

            operation_stats[
                "idle_setup_duration_sec"
            ] += duration

        if state == "SEWING":
            operation_stats[
                "sewing_segment_count"
            ] += 1

            operation_stats[
                "sewing_duration_sec"
            ] += duration

    report_rows: list[dict[str, Any]] = []

    for operation_type in ALLOWED_OPERATIONS:
        operation_stats = statistics[
            operation_type
        ]

        idle_duration = operation_stats[
            "idle_setup_duration_sec"
        ]

        sewing_duration = operation_stats[
            "sewing_duration_sec"
        ]

        report_rows.append(
            {
                "operation_type": operation_type,
                "video_count": len(
                    operation_stats["videos"]
                ),
                "segment_count": operation_stats[
                    "segment_count"
                ],
                "idle_setup_segment_count": (
                    operation_stats[
                        "idle_setup_segment_count"
                    ]
                ),
                "sewing_segment_count": (
                    operation_stats[
                        "sewing_segment_count"
                    ]
                ),
                "idle_setup_duration_sec": (
                    f"{idle_duration:.3f}"
                ),
                "sewing_duration_sec": (
                    f"{sewing_duration:.3f}"
                ),
                "total_duration_sec": (
                    f"{idle_duration + sewing_duration:.3f}"
                ),
            }
        )

    return report_rows


def create_split_distribution(
    enhanced_rows: list[dict[str, str]],
    operation_lookup: dict[str, str],
    split_lookup: dict[str, str],
    clip_statistics: dict[
        tuple[str, str],
        dict[str, int],
    ],
) -> list[dict[str, Any]]:
    """
    Summarize operations within train, validation and test.
    """

    statistics: dict[
        tuple[str, str],
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "videos": set(),
            "segment_count": 0,
            "idle_setup_segment_count": 0,
            "sewing_segment_count": 0,
            "idle_setup_duration_sec": 0.0,
            "sewing_duration_sec": 0.0,
        }
    )

    for row in enhanced_rows:
        video_name = row["video_name"]
        split = split_lookup[video_name]
        operation_type = operation_lookup[video_name]
        state = row["state"]

        duration = (
            float(row["end_time_sec"])
            - float(row["start_time_sec"])
        )

        key = (
            split,
            operation_type,
        )

        split_stats = statistics[key]

        split_stats["videos"].add(
            video_name
        )

        split_stats["segment_count"] += 1

        if state == "IDLE_SETUP":
            split_stats[
                "idle_setup_segment_count"
            ] += 1

            split_stats[
                "idle_setup_duration_sec"
            ] += duration

        if state == "SEWING":
            split_stats[
                "sewing_segment_count"
            ] += 1

            split_stats[
                "sewing_duration_sec"
            ] += duration

    report_rows: list[dict[str, Any]] = []

    for split in ALLOWED_SPLITS:
        for operation_type in ALLOWED_OPERATIONS:
            key = (
                split,
                operation_type,
            )

            split_stats = statistics[key]
            clip_stats = clip_statistics[key]

            report_rows.append(
                {
                    "split": split,
                    "operation_type": operation_type,
                    "video_count": len(
                        split_stats["videos"]
                    ),
                    "segment_count": split_stats[
                        "segment_count"
                    ],
                    "idle_setup_segment_count": (
                        split_stats[
                            "idle_setup_segment_count"
                        ]
                    ),
                    "sewing_segment_count": (
                        split_stats[
                            "sewing_segment_count"
                        ]
                    ),
                    "idle_setup_duration_sec": (
                        f"{split_stats['idle_setup_duration_sec']:.3f}"
                    ),
                    "sewing_duration_sec": (
                        f"{split_stats['sewing_duration_sec']:.3f}"
                    ),
                    "total_clip_count": clip_stats[
                        "total_clip_count"
                    ],
                    "idle_setup_clip_count": clip_stats[
                        "idle_setup_clip_count"
                    ],
                    "sewing_clip_count": clip_stats[
                        "sewing_clip_count"
                    ],
                }
            )

    return report_rows


def decide_split_status(
    split_distribution: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """
    Decide whether the existing split contains every operation.
    """

    missing_combinations: list[str] = []

    for row in split_distribution:
        if int(row["video_count"]) == 0:
            missing_combinations.append(
                f"{row['split']} -> "
                f"{row['operation_type']}"
            )

    if missing_combinations:
        return (
            "CREATE_OPERATION_STRATIFIED_SPLIT",
            missing_combinations,
        )

    return (
        "KEEP_EXISTING_SPLIT",
        [],
    )


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def main() -> int:
    try:
        original_rows = read_csv(
            ORIGINAL_ANNOTATION_PATH,
            ORIGINAL_COLUMNS,
        )

        enhanced_rows = read_csv(
            ENHANCED_ANNOTATION_PATH,
            ENHANCED_COLUMNS,
        )

        split_rows = read_csv(
            SPLIT_MANIFEST_PATH,
            SPLIT_COLUMNS,
        )

        clip_rows = read_csv(
            CLIP_MANIFEST_PATH,
            CLIP_COLUMNS,
        )

        validation_checks = validate_annotations(
            original_rows,
            enhanced_rows,
        )

        operation_lookup = create_operation_lookup(
            enhanced_rows
        )

        split_lookup = create_split_lookup(
            split_rows
        )

        validate_video_sets(
            operation_lookup,
            split_lookup,
        )

        validation_checks[
            "annotation_and_split_videos_match"
        ] = "PASS"

        clip_statistics = validate_clip_manifest(
            clip_rows,
            operation_lookup,
            split_lookup,
        )

        validation_checks[
            "clip_manifest_matches_video_splits"
        ] = "PASS"

        operation_distribution = (
            create_operation_distribution(
                enhanced_rows
            )
        )

        split_distribution = (
            create_split_distribution(
                enhanced_rows,
                operation_lookup,
                split_lookup,
                clip_statistics,
            )
        )

        split_decision, missing_combinations = (
            decide_split_status(
                split_distribution
            )
        )

        write_csv(
            OPERATION_REPORT_PATH,
            [
                "operation_type",
                "video_count",
                "segment_count",
                "idle_setup_segment_count",
                "sewing_segment_count",
                "idle_setup_duration_sec",
                "sewing_duration_sec",
                "total_duration_sec",
            ],
            operation_distribution,
        )

        write_csv(
            SPLIT_REPORT_PATH,
            [
                "split",
                "operation_type",
                "video_count",
                "segment_count",
                "idle_setup_segment_count",
                "sewing_segment_count",
                "idle_setup_duration_sec",
                "sewing_duration_sec",
                "total_clip_count",
                "idle_setup_clip_count",
                "sewing_clip_count",
            ],
            split_distribution,
        )

        summary = {
            "status": "PASS",
            "dataset": {
                "annotation_row_count": len(
                    enhanced_rows
                ),
                "video_count": len(
                    operation_lookup
                ),
                "clip_count": len(
                    clip_rows
                ),
                "states": list(
                    ALLOWED_STATES
                ),
                "operations": list(
                    ALLOWED_OPERATIONS
                ),
            },
            "validation_checks": (
                validation_checks
            ),
            "split_decision": {
                "decision": split_decision,
                "missing_split_operation_combinations": (
                    missing_combinations
                ),
            },
            "source_checksums": {
                "original_annotation_sha256": (
                    calculate_sha256(
                        ORIGINAL_ANNOTATION_PATH
                    )
                ),
                "enhanced_annotation_sha256": (
                    calculate_sha256(
                        ENHANCED_ANNOTATION_PATH
                    )
                ),
                "split_manifest_sha256": (
                    calculate_sha256(
                        SPLIT_MANIFEST_PATH
                    )
                ),
                "clip_manifest_sha256": (
                    calculate_sha256(
                        CLIP_MANIFEST_PATH
                    )
                ),
            },
            "operation_distribution": (
                operation_distribution
            ),
            "split_operation_distribution": (
                split_distribution
            ),
        }

        write_json(
            SUMMARY_REPORT_PATH,
            summary,
        )

        print("Phase 2 validation completed successfully.")
        print()
        print(f"Annotation rows: {len(enhanced_rows)}")
        print(f"Videos: {len(operation_lookup)}")
        print(f"Clips: {len(clip_rows)}")
        print()
        print(f"Split decision: {split_decision}")
        print()
        print("Generated reports:")
        print(OPERATION_REPORT_PATH)
        print(SPLIT_REPORT_PATH)
        print(SUMMARY_REPORT_PATH)

        return 0

    except (OSError, ValueError) as error:
        print(
            f"Phase 2 validation failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())