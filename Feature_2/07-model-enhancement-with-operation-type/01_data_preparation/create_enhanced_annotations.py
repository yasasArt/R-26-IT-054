from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from pathlib import Path


# File paths


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

SEGMENT_PATH = (
    PROJECT_ROOT
    / "00_protected_baseline"
    / "segment_annotation.csv"
)

MAPPING_PATH = (
    SCRIPT_DIR
    / "video_operation_mapping.csv"
)

OUTPUT_PATH = (
    SCRIPT_DIR
    / "outputs"
    / "segment_annotation_with_operation.csv"
)



# Dataset configuration

ALLOWED_OPERATIONS = {
    "SLEEVE",
    "COLLAR",
    "POCKET",
}

ALLOWED_STATES = {
    "IDLE_SETUP",
    "SEWING",
}

SEGMENT_COLUMNS = (
    "video_name",
    "start_time_sec",
    "end_time_sec",
    "state",
)

MAPPING_COLUMNS = (
    "video_name",
    "operation_type",
)

OUTPUT_COLUMNS = (
    "video_name",
    "start_time_sec",
    "end_time_sec",
    "state",
    "operation_type",
)



# CSV reading


def read_csv(
    file_path: Path,
    required_columns: tuple[str, ...],
) -> list[dict[str, str]]:
    """
    Read a CSV file and confirm that its required columns exist.
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



# Operation mapping validation


def create_operation_lookup(
    mapping_rows: list[dict[str, str]],
) -> dict[str, str]:
    """
    Convert the mapping CSV into:

    {
        "v01.mp4": "SLEEVE",
        "v02.mp4": "COLLAR"
    }
    """

    operation_lookup: dict[str, str] = {}

    for row in mapping_rows:
        row_number = row["__row_number"]

        video_name = row["video_name"].strip()
        operation_type = row["operation_type"].strip().upper()

        if not video_name:
            raise ValueError(
                f"Mapping row {row_number} has an empty video_name."
            )

        if operation_type not in ALLOWED_OPERATIONS:
            allowed = ", ".join(sorted(ALLOWED_OPERATIONS))

            raise ValueError(
                f"Mapping row {row_number} has invalid operation_type "
                f"{operation_type!r}. Allowed values: {allowed}"
            )

        if video_name in operation_lookup:
            raise ValueError(
                f"Video {video_name!r} appears more than once "
                f"in {MAPPING_PATH.name}."
            )

        operation_lookup[video_name] = operation_type

    return operation_lookup



# Segment annotation validation


def validate_segment_row(
    row: dict[str, str],
) -> None:
    """
    Validate one row from segment_annotation.csv.
    """

    row_number = row["__row_number"]

    video_name = row["video_name"].strip()
    state = row["state"].strip().upper()

    if not video_name:
        raise ValueError(
            f"Segment row {row_number} has an empty video_name."
        )

    if state not in ALLOWED_STATES:
        allowed = ", ".join(sorted(ALLOWED_STATES))

        raise ValueError(
            f"Segment row {row_number} has invalid state "
            f"{state!r}. Allowed values: {allowed}"
        )

    try:
        start_time = float(row["start_time_sec"])
        end_time = float(row["end_time_sec"])

    except ValueError as error:
        raise ValueError(
            f"Segment row {row_number} contains an invalid time value."
        ) from error

    if start_time < 0:
        raise ValueError(
            f"Segment row {row_number} has a negative start time."
        )

    if end_time <= start_time:
        raise ValueError(
            f"Segment row {row_number} must have an end time "
            f"greater than its start time."
        )



# Enhanced annotation creation


def create_enhanced_rows(
    segment_rows: list[dict[str, str]],
    operation_lookup: dict[str, str],
) -> list[dict[str, str]]:
    """
    Add operation_type to every segment annotation row.
    """

    annotated_videos = {
        row["video_name"].strip()
        for row in segment_rows
    }

    mapped_videos = set(operation_lookup)

    missing_mappings = sorted(
        annotated_videos - mapped_videos
    )

    if missing_mappings:
        raise ValueError(
            "The following annotated videos do not have an "
            "operation mapping:\n"
            + "\n".join(missing_mappings)
        )

    unknown_mapping_videos = sorted(
        mapped_videos - annotated_videos
    )

    if unknown_mapping_videos:
        raise ValueError(
            "The mapping file contains videos that do not exist "
            "in segment_annotation.csv:\n"
            + "\n".join(unknown_mapping_videos)
        )

    enhanced_rows: list[dict[str, str]] = []

    for row in segment_rows:
        validate_segment_row(row)

        video_name = row["video_name"].strip()
        state = row["state"].strip().upper()

        enhanced_row = {
            "video_name": video_name,
            "start_time_sec": row["start_time_sec"].strip(),
            "end_time_sec": row["end_time_sec"].strip(),
            "state": state,
            "operation_type": operation_lookup[video_name],
        }

        enhanced_rows.append(enhanced_row)

    return enhanced_rows



# CSV writing


def write_enhanced_csv(
    rows: list[dict[str, str]],
) -> None:
    """
    Save the enhanced annotations safely.

    A temporary file is written first. It replaces the final
    output only after writing completes successfully.
    """

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = OUTPUT_PATH.with_name(
        f".{OUTPUT_PATH.name}.tmp"
    )

    with temporary_path.open(
        mode="w",
        encoding="utf-8",
        newline="",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=OUTPUT_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(rows) # type: ignore

    os.replace(
        temporary_path,
        OUTPUT_PATH,
    )



# Program entry point


def main() -> int:
    try:
        segment_rows = read_csv(
            SEGMENT_PATH,
            SEGMENT_COLUMNS,
        )

        mapping_rows = read_csv(
            MAPPING_PATH,
            MAPPING_COLUMNS,
        )

        operation_lookup = create_operation_lookup(
            mapping_rows
        )

        enhanced_rows = create_enhanced_rows(
            segment_rows,
            operation_lookup,
        )

        write_enhanced_csv(
            enhanced_rows
        )

        video_counts = Counter(
            operation_lookup.values()
        )

        segment_counts = Counter(
            row["operation_type"]
            for row in enhanced_rows
        )

        print("Enhanced annotations generated successfully.")
        print()
        print(f"Original annotation: {SEGMENT_PATH}")
        print(f"Operation mapping: {MAPPING_PATH}")
        print(f"Generated file: {OUTPUT_PATH}")
        print()
        print(f"Total videos: {len(operation_lookup)}")
        print(f"Total annotation rows: {len(enhanced_rows)}")
        print()
        print("Videos by operation:")

        for operation in sorted(ALLOWED_OPERATIONS):
            print(
                f"  {operation}: "
                f"{video_counts.get(operation, 0)}"
            )

        print()
        print("Annotation rows by operation:")

        for operation in sorted(ALLOWED_OPERATIONS):
            print(
                f"  {operation}: "
                f"{segment_counts.get(operation, 0)}"
            )

        return 0

    except (OSError, ValueError) as error:
        print(
            f"Error: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())