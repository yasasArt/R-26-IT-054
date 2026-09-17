from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from src.operation_aware_dataset import (
    OperationAwareGarmentClipDataset,
    assert_no_video_leakage,
)


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


# IMPORTANT:
# Change this path to the existing folder containing:
#
# train/idle_setup/
# train/sewing/
# validation/idle_setup/
# validation/sewing/
# test/idle_setup/
# test/sewing/
#
# Do not point this to 03_dataset_splitting.
# It must point to the real MP4 clip dataset.

DATASET_DIR = Path(
    "/Users/nuwandharmarathna/Desktop/Projects/R-26-IT-054/Feature_2/01-data-annotation-and-dataset-preparation/generated_clips"
).expanduser().resolve()


MANIFEST_PATH = (
    PROJECT_ROOT
    / "03_dataset_splitting"
    / "outputs"
    / "enhanced_clip_manifest.csv"
)

OPERATION_MAPPING_PATH = (
    SCRIPT_DIR
    / "config"
    / "operation_mapping.json"
)

REPORT_PATH = (
    SCRIPT_DIR
    / "reports"
    / "phase4_summary.json"
)


# ---------------------------------------------------------
# Dataset configuration
# ---------------------------------------------------------

FRAMES_PER_CLIP = 8
INPUT_SIZE = 224
BATCH_SIZE = 2

SPLITS = (
    "train",
    "validation",
    "test",
)


# ---------------------------------------------------------
# JSON writing
# ---------------------------------------------------------

def write_json(
    file_path: Path,
    data: dict[str, Any],
) -> None:
    """
    Write a JSON report safely.
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


# ---------------------------------------------------------
# Dataset inspection
# ---------------------------------------------------------

def inspect_dataset(
    dataset: OperationAwareGarmentClipDataset,
) -> dict[str, Any]:
    """
    Load one batch and inspect tensor shapes.
    """

    data_loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    (
        clips,
        state_targets,
        operation_targets,
        metadata,
    ) = next(iter(data_loader))

    expected_clip_shape = (
        BATCH_SIZE,
        FRAMES_PER_CLIP,
        3,
        INPUT_SIZE,
        INPUT_SIZE,
    )

    if tuple(clips.shape) != expected_clip_shape:
        raise ValueError(
            "Unexpected clip batch shape. "
            f"Expected {expected_clip_shape}, "
            f"found {tuple(clips.shape)}."
        )

    if clips.dtype != torch.float32:
        raise ValueError(
            "Clip tensor must use torch.float32."
        )

    if tuple(state_targets.shape) != (
        BATCH_SIZE,
    ):
        raise ValueError(
            "Unexpected state-target shape."
        )

    if tuple(operation_targets.shape) != (
        BATCH_SIZE,
    ):
        raise ValueError(
            "Unexpected operation-target shape."
        )

    if state_targets.dtype != torch.int64:
        raise ValueError(
            "State targets must use torch.int64."
        )

    if operation_targets.dtype != torch.int64:
        raise ValueError(
            "Operation targets must use torch.int64."
        )

    return {
        "split": dataset.split,
        "clip_count": len(dataset),
        "video_count": len(
            dataset.source_videos
        ),
        "state_counts": dataset.class_counts,
        "operation_counts": (
            dataset.operation_counts
        ),
        "sample_batch": {
            "clip_shape": list(
                clips.shape
            ),
            "clip_dtype": str(
                clips.dtype
            ),
            "state_target_shape": list(
                state_targets.shape
            ),
            "operation_target_shape": list(
                operation_targets.shape
            ),
            "state_targets": (
                state_targets.tolist()
            ),
            "operation_targets": (
                operation_targets.tolist()
            ),
            "video_names": list(
                metadata["video_name"]
            ),
            "operation_types": list(
                metadata["operation_type"]
            ),
        },
    }


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def main() -> int:
    try:
        if (
            "replace/this"
            in str(DATASET_DIR)
        ):
            raise ValueError(
                "Update DATASET_DIR inside "
                "inspect_operation_dataset.py "
                "before running the script."
            )

        datasets = {
            split: OperationAwareGarmentClipDataset(
                dataset_dir=DATASET_DIR,
                manifest_path=MANIFEST_PATH,
                operation_mapping_path=(
                    OPERATION_MAPPING_PATH
                ),
                split=split,
                frames_per_clip=(
                    FRAMES_PER_CLIP
                ),
                input_size=INPUT_SIZE,
            )
            for split in SPLITS
        }

        assert_no_video_leakage(
            datasets["train"],
            datasets["validation"],
            datasets["test"],
        )

        results = {
            split: inspect_dataset(
                datasets[split]
            )
            for split in SPLITS
        }

        summary = {
            "status": "PASS",
            "dataset_dir": str(
                DATASET_DIR
            ),
            "manifest_path": str(
                MANIFEST_PATH
            ),
            "operation_mapping_path": str(
                OPERATION_MAPPING_PATH
            ),
            "configuration": {
                "frames_per_clip": (
                    FRAMES_PER_CLIP
                ),
                "input_size": INPUT_SIZE,
                "batch_size": BATCH_SIZE,
            },
            "checks": {
                "all_clip_files_exist": "PASS",
                "operation_mapping_valid": "PASS",
                "all_splits_loaded": "PASS",
                "no_video_leakage": "PASS",
                "clip_tensor_shape_valid": "PASS",
                "state_target_shape_valid": "PASS",
                "operation_target_shape_valid": "PASS",
            },
            "splits": results,
        }

        write_json(
            REPORT_PATH,
            summary,
        )

        print(
            "Phase 4 dataset inspection "
            "completed successfully."
        )

        print()

        for split in SPLITS:
            result = results[split]

            print(
                f"{split}: "
                f"{result['clip_count']} clips, "
                f"{result['video_count']} videos"
            )

            print(
                f"  State counts: "
                f"{result['state_counts']}"
            )

            print(
                f"  Operation counts: "
                f"{result['operation_counts']}"
            )

            print(
                f"  Batch shape: "
                f"{result['sample_batch']['clip_shape']}"
            )

        print()
        print(f"Report: {REPORT_PATH}")

        return 0

    except (
        OSError,
        ValueError,
        RuntimeError,
    ) as error:

        print(
            f"Phase 4 failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())