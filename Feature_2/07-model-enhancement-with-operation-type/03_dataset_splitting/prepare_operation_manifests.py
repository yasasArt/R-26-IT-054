from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

PHASE_2_SUMMARY_PATH = (
    PROJECT_ROOT
    / "02_dataset_validation"
    / "reports"
    / "validation_summary.json"
)

ENHANCED_ANNOTATION_PATH = (
    PROJECT_ROOT
    / "01_data_preparation"
    / "outputs"
    / "segment_annotation_with_operation.csv"
)

ORIGINAL_SPLIT_MANIFEST_PATH = (
    PROJECT_ROOT
    / "00_protected_baseline"
    / "split_manifest.csv"
)

ORIGINAL_CLIP_MANIFEST_PATH = (
    PROJECT_ROOT
    / "00_protected_baseline"
    / "clip_manifest.csv"
)

OUTPUTS_DIR = SCRIPT_DIR / "outputs"
REPORTS_DIR = SCRIPT_DIR / "reports"

ENHANCED_SPLIT_MANIFEST_PATH = (
    OUTPUTS_DIR
    / "enhanced_split_manifest.csv"
)

ENHANCED_CLIP_MANIFEST_PATH = (
    OUTPUTS_DIR
    / "enhanced_clip_manifest.csv"
)

PHASE_3_SUMMARY_PATH = (
    REPORTS_DIR
    / "phase3_summary.json"
)


# ---------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------

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

ALLOWED_STATES = (
    "IDLE_SETUP",
    "SEWING",
)

ENHANCED_ANNOTATION_COLUMNS = (
    "video_name",
    "start_time_sec",
    "end_time_sec",
    "state",
    "operation_type",
)

SPLIT_MANIFEST_COLUMNS = (
    "video_name",
    "split",
)

CLIP_MANIFEST_COLUMNS = (
    "split",
    "clip_name",
    "relative_clip_path",
    "video_name",
    "state",
)


# ---------------------------------------------------------
# File-reading functions
# ---------------------------------------------------------

def read_csv(
    file_path: Path,
    required_columns: tuple[str, ...],
) -> tuple[list[str], list[dict[str, str]]]:
    """
    Read a CSV file and validate its required columns.

    Returns:
        1. Original CSV column names.
        2. CSV data rows.
    """

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Required CSV file was not found: {file_path}"
        )

    with file_path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:

        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []

        missing_columns = [
            column
            for column in required_columns
            if column not in fieldnames
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

    return fieldnames, rows # type: ignore


def read_json(file_path: Path) -> dict[str, Any]:
    """
    Read a JSON file and ensure it contains an object.
    """

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Required JSON file was not found: {file_path}"
        )

    try:
        data = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"{file_path.name} contains invalid JSON."
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            f"{file_path.name} must contain a JSON object."
        )

    return data


# ---------------------------------------------------------
# File-writing functions
# ---------------------------------------------------------

def write_csv(
    file_path: Path,
    fieldnames: list[str],
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
            fieldnames=fieldnames,
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
    Save a formatted JSON report safely.
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
    Calculate a file's SHA-256 checksum.
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
# Phase 2 verification
# ---------------------------------------------------------

def validate_phase_2(
    phase_2_summary: dict[str, Any],
) -> None:
    """
    Confirm that Phase 2 passed and approved the existing split.
    """

    status = phase_2_summary.get("status")

    if status != "PASS":
        raise ValueError(
            "Phase 2 did not complete successfully. "
            f"Found status: {status!r}"
        )

    split_information = phase_2_summary.get(
        "split_decision"
    )

    if not isinstance(split_information, dict):
        raise ValueError(
            "Phase 2 summary does not contain "
            "split_decision information."
        )

    decision = split_information.get("decision")

    if decision != "KEEP_EXISTING_SPLIT":
        raise ValueError(
            "Phase 2 did not approve the existing split. "
            f"Found decision: {decision!r}"
        )


# ---------------------------------------------------------
# Operation mapping
# ---------------------------------------------------------

def create_operation_lookup(
    enhanced_annotation_rows: list[dict[str, str]],
) -> dict[str, str]:
    """
    Create a video-to-operation lookup.

    Example:
        {
            "v01.mp4": "COLLAR",
            "v02.mp4": "SLEEVE"
        }
    """

    operation_lookup: dict[str, str] = {}

    for row in enhanced_annotation_rows:
        row_number = row["__row_number"]
        video_name = row["video_name"]
        operation_type = row["operation_type"]

        if not video_name:
            raise ValueError(
                f"Enhanced annotation row {row_number} "
                f"has an empty video_name."
            )

        if operation_type not in ALLOWED_OPERATIONS:
            raise ValueError(
                f"Enhanced annotation row {row_number} "
                f"has invalid operation_type "
                f"{operation_type!r}."
            )

        current_operation = operation_lookup.get(
            video_name
        )

        if (
            current_operation is not None
            and current_operation != operation_type
        ):
            raise ValueError(
                f"{video_name} has conflicting "
                f"operation types."
            )

        operation_lookup[video_name] = operation_type

    return operation_lookup


# ---------------------------------------------------------
# Split-manifest preparation
# ---------------------------------------------------------

def prepare_split_manifest(
    split_rows: list[dict[str, str]],
    operation_lookup: dict[str, str],
) -> tuple[
    list[dict[str, str]],
    dict[str, str],
]:
    """
    Add operation_type to the original split manifest.
    """

    enhanced_rows: list[dict[str, str]] = []
    split_lookup: dict[str, str] = {}

    for row in split_rows:
        row_number = row["__row_number"]
        video_name = row["video_name"]
        split = row["split"]

        if not video_name:
            raise ValueError(
                f"Split manifest row {row_number} "
                f"has an empty video_name."
            )

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

        if video_name not in operation_lookup:
            raise ValueError(
                f"{video_name} does not have an "
                f"operation_type."
            )

        split_lookup[video_name] = split

        enhanced_row = {
            column: value
            for column, value in row.items()
            if not column.startswith("__")
        }

        enhanced_row["operation_type"] = (
            operation_lookup[video_name]
        )

        enhanced_rows.append(
            enhanced_row
        )

    annotation_videos = set(operation_lookup)
    split_videos = set(split_lookup)

    missing_split_videos = sorted(
        annotation_videos - split_videos
    )

    unknown_split_videos = sorted(
        split_videos - annotation_videos
    )

    if missing_split_videos:
        raise ValueError(
            "These annotated videos are missing "
            "from the split manifest:\n"
            + "\n".join(missing_split_videos)
        )

    if unknown_split_videos:
        raise ValueError(
            "The split manifest contains unknown videos:\n"
            + "\n".join(unknown_split_videos)
        )

    return enhanced_rows, split_lookup


# ---------------------------------------------------------
# Clip-manifest preparation
# ---------------------------------------------------------

def prepare_clip_manifest(
    clip_rows: list[dict[str, str]],
    operation_lookup: dict[str, str],
    split_lookup: dict[str, str],
) -> list[dict[str, str]]:
    """
    Add operation_type to every clip-manifest row.
    """

    enhanced_rows: list[dict[str, str]] = []

    seen_clip_names: set[str] = set()
    seen_clip_paths: set[str] = set()

    for row in clip_rows:
        row_number = row["__row_number"]

        video_name = row["video_name"]
        split = row["split"]
        state = row["state"]
        clip_name = row["clip_name"]
        relative_clip_path = row[
            "relative_clip_path"
        ]

        if video_name not in operation_lookup:
            raise ValueError(
                f"Clip row {row_number} references "
                f"unknown video {video_name!r}."
            )

        if video_name not in split_lookup:
            raise ValueError(
                f"Clip row {row_number} references "
                f"a video missing from the split manifest."
            )

        expected_split = split_lookup[video_name]

        if split != expected_split:
            raise ValueError(
                f"Clip row {row_number} assigns "
                f"{video_name} to {split}, but the "
                f"split manifest assigns it to "
                f"{expected_split}."
            )

        if state not in ALLOWED_STATES:
            raise ValueError(
                f"Clip row {row_number} contains "
                f"invalid state {state!r}."
            )

        if clip_name in seen_clip_names:
            raise ValueError(
                f"Duplicate clip name found: "
                f"{clip_name}"
            )

        if relative_clip_path in seen_clip_paths:
            raise ValueError(
                f"Duplicate clip path found: "
                f"{relative_clip_path}"
            )

        seen_clip_names.add(
            clip_name
        )

        seen_clip_paths.add(
            relative_clip_path
        )

        enhanced_row = {
            column: value
            for column, value in row.items()
            if not column.startswith("__")
        }

        enhanced_row["operation_type"] = (
            operation_lookup[video_name]
        )

        enhanced_rows.append(
            enhanced_row
        )

    return enhanced_rows


# ---------------------------------------------------------
# Column-position helper
# ---------------------------------------------------------

def insert_column_after(
    columns: list[str],
    existing_column: str,
    new_column: str,
) -> list[str]:
    """
    Insert a new column after an existing CSV column.
    """

    if new_column in columns:
        raise ValueError(
            f"Column {new_column!r} already exists."
        )

    if existing_column not in columns:
        raise ValueError(
            f"Column {existing_column!r} was not found."
        )

    new_columns = list(columns)

    position = (
        new_columns.index(existing_column) + 1
    )

    new_columns.insert(
        position,
        new_column,
    )

    return new_columns


# ---------------------------------------------------------
# Report calculations
# ---------------------------------------------------------

def build_distribution_report(
    enhanced_split_rows: list[dict[str, str]],
    enhanced_clip_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Calculate video and clip counts by split and operation.
    """

    video_counts: Counter[
        tuple[str, str]
    ] = Counter()

    clip_counts: Counter[
        tuple[str, str]
    ] = Counter()

    state_clip_counts: Counter[
        tuple[str, str, str]
    ] = Counter()

    for row in enhanced_split_rows:
        key = (
            row["split"],
            row["operation_type"],
        )

        video_counts[key] += 1

    for row in enhanced_clip_rows:
        split = row["split"]
        operation_type = row["operation_type"]
        state = row["state"]

        clip_counts[
            (
                split,
                operation_type,
            )
        ] += 1

        state_clip_counts[
            (
                split,
                operation_type,
                state,
            )
        ] += 1

    rows: list[dict[str, Any]] = []

    missing_combinations: list[str] = []

    for split in ALLOWED_SPLITS:
        for operation_type in ALLOWED_OPERATIONS:
            video_count = video_counts[
                (
                    split,
                    operation_type,
                )
            ]

            if video_count == 0:
                missing_combinations.append(
                    f"{split} -> {operation_type}"
                )

            rows.append(
                {
                    "split": split,
                    "operation_type": operation_type,
                    "video_count": video_count,
                    "clip_count": clip_counts[
                        (
                            split,
                            operation_type,
                        )
                    ],
                    "idle_setup_clip_count": (
                        state_clip_counts[
                            (
                                split,
                                operation_type,
                                "IDLE_SETUP",
                            )
                        ]
                    ),
                    "sewing_clip_count": (
                        state_clip_counts[
                            (
                                split,
                                operation_type,
                                "SEWING",
                            )
                        ]
                    ),
                }
            )

    if missing_combinations:
        raise ValueError(
            "Operation types are missing from splits: "
            + ", ".join(missing_combinations)
        )

    return {
        "rows": rows,
        "missing_combinations": (
            missing_combinations
        ),
    }


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def main() -> int:
    try:
        phase_2_summary = read_json(
            PHASE_2_SUMMARY_PATH
        )

        validate_phase_2(
            phase_2_summary
        )

        (
            _enhanced_annotation_headers,
            enhanced_annotation_rows,
        ) = read_csv(
            ENHANCED_ANNOTATION_PATH,
            ENHANCED_ANNOTATION_COLUMNS,
        )

        (
            original_split_headers,
            original_split_rows,
        ) = read_csv(
            ORIGINAL_SPLIT_MANIFEST_PATH,
            SPLIT_MANIFEST_COLUMNS,
        )

        (
            original_clip_headers,
            original_clip_rows,
        ) = read_csv(
            ORIGINAL_CLIP_MANIFEST_PATH,
            CLIP_MANIFEST_COLUMNS,
        )

        operation_lookup = create_operation_lookup(
            enhanced_annotation_rows
        )

        (
            enhanced_split_rows,
            split_lookup,
        ) = prepare_split_manifest(
            original_split_rows,
            operation_lookup,
        )

        enhanced_clip_rows = prepare_clip_manifest(
            original_clip_rows,
            operation_lookup,
            split_lookup,
        )

        enhanced_split_headers = (
            insert_column_after(
                original_split_headers,
                "split",
                "operation_type",
            )
        )

        enhanced_clip_headers = (
            insert_column_after(
                original_clip_headers,
                "video_name",
                "operation_type",
            )
        )

        write_csv(
            ENHANCED_SPLIT_MANIFEST_PATH,
            enhanced_split_headers,
            enhanced_split_rows,
        )

        write_csv(
            ENHANCED_CLIP_MANIFEST_PATH,
            enhanced_clip_headers,
            enhanced_clip_rows,
        )

        # Create a separate video list for each split.
        for split in ALLOWED_SPLITS:
            split_video_rows = [
                {
                    "video_name": row["video_name"],
                    "split": row["split"],
                    "operation_type": (
                        row["operation_type"]
                    ),
                }
                for row in enhanced_split_rows
                if row["split"] == split
            ]

            split_video_path = (
                OUTPUTS_DIR
                / split
                / "videos_with_operation.csv"
            )

            write_csv(
                split_video_path,
                [
                    "video_name",
                    "split",
                    "operation_type",
                ],
                split_video_rows,
            )

        distribution = build_distribution_report(
            enhanced_split_rows,
            enhanced_clip_rows,
        )

        split_video_counts = Counter(
            row["split"]
            for row in enhanced_split_rows
        )

        split_clip_counts = Counter(
            row["split"]
            for row in enhanced_clip_rows
        )

        summary = {
            "status": "PASS",
            "split_strategy": (
                "Existing video-level split preserved"
            ),
            "phase_2_decision": (
                "KEEP_EXISTING_SPLIT"
            ),
            "counts": {
                "video_count": len(
                    enhanced_split_rows
                ),
                "clip_count": len(
                    enhanced_clip_rows
                ),
                "train_video_count": (
                    split_video_counts["train"]
                ),
                "validation_video_count": (
                    split_video_counts["validation"]
                ),
                "test_video_count": (
                    split_video_counts["test"]
                ),
                "train_clip_count": (
                    split_clip_counts["train"]
                ),
                "validation_clip_count": (
                    split_clip_counts["validation"]
                ),
                "test_clip_count": (
                    split_clip_counts["test"]
                ),
            },
            "distribution": distribution["rows"],
            "checks": {
                "phase_2_status": "PASS",
                "existing_split_preserved": "PASS",
                "all_videos_have_operation_type": "PASS",
                "all_clips_have_operation_type": "PASS",
                "clip_names_are_unique": "PASS",
                "clip_paths_are_unique": "PASS",
                "clip_splits_match_video_splits": "PASS",
                "all_operations_exist_in_all_splits": "PASS",
            },
            "source_checksums": {
                "phase_2_summary_sha256": (
                    calculate_sha256(
                        PHASE_2_SUMMARY_PATH
                    )
                ),
                "enhanced_annotation_sha256": (
                    calculate_sha256(
                        ENHANCED_ANNOTATION_PATH
                    )
                ),
                "original_split_manifest_sha256": (
                    calculate_sha256(
                        ORIGINAL_SPLIT_MANIFEST_PATH
                    )
                ),
                "original_clip_manifest_sha256": (
                    calculate_sha256(
                        ORIGINAL_CLIP_MANIFEST_PATH
                    )
                ),
            },
            "output_checksums": {
                "enhanced_split_manifest_sha256": (
                    calculate_sha256(
                        ENHANCED_SPLIT_MANIFEST_PATH
                    )
                ),
                "enhanced_clip_manifest_sha256": (
                    calculate_sha256(
                        ENHANCED_CLIP_MANIFEST_PATH
                    )
                ),
            },
        }

        write_json(
            PHASE_3_SUMMARY_PATH,
            summary,
        )

        print(
            "Phase 3 operation-aware manifests "
            "created successfully."
        )

        print()
        print(
            f"Videos: {len(enhanced_split_rows)}"
        )

        print(
            f"Clips: {len(enhanced_clip_rows)}"
        )

        print()
        print(
            "Video split:"
        )

        for split in ALLOWED_SPLITS:
            print(
                f"  {split}: "
                f"{split_video_counts[split]}"
            )

        print()
        print(
            "Clip split:"
        )

        for split in ALLOWED_SPLITS:
            print(
                f"  {split}: "
                f"{split_clip_counts[split]}"
            )

        print()
        print("Generated files:")
        print(ENHANCED_SPLIT_MANIFEST_PATH)
        print(ENHANCED_CLIP_MANIFEST_PATH)
        print(PHASE_3_SUMMARY_PATH)

        return 0

    except (OSError, ValueError) as error:
        print(
            f"Phase 3 failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())