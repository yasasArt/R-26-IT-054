from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PHASE_7_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_7_DIR.parent

PHASE_6_DIR = PROJECT_ROOT / "06_operation_aware_training"
OUTPUT_DIR = PHASE_7_DIR / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Add Phase 6 to Python's module search path.
# This lets Phase 7 reuse the exact model, dataset, and metric code
# that was used during training.
sys.path.insert(0, str(PHASE_6_DIR))

from src.dataset import OperationAwareGarmentClipDataset # type: ignore
from src.metrics import classification_metrics # type: ignore
from src.model import OperationAwareTemporalMobileNetV3Small # type: ignore


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def find_single_file(directory: Path, filename: str) -> Path:
    """
    Find exactly one file with the given name inside a directory.

    This means you do not have to provide the checkpoint path in the
    terminal.
    """
    matches = sorted(directory.rglob(filename))

    if not matches:
        raise FileNotFoundError(
            f"Could not find {filename!r} inside:\n{directory}"
        )

    if len(matches) > 1:
        formatted_matches = "\n".join(str(path) for path in matches)

        raise RuntimeError(
            f"More than one {filename!r} was found.\n"
            f"Please keep only the required experiment or set the path "
            f"directly in the code.\n\nFound:\n{formatted_matches}"
        )

    return matches[0]


def load_json(path: Path) -> dict[str, Any]:
    """Read and return a JSON file."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save a dictionary as a formatted JSON file."""

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def select_device(device_setting: str) -> torch.device:
    """
    Select CUDA, Apple MPS, or CPU.

    The value 'auto' selects the best device available on the computer.
    """

    requested_device = device_setting.strip().lower()

    if requested_device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")

        if torch.backends.mps.is_available():
            return torch.device("mps")

        return torch.device("cpu")

    if requested_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but CUDA is not available.")

    if requested_device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested, but MPS is not available.")

    return torch.device(requested_device)


def load_checkpoint(path: Path) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    """
    Load the saved Phase 6 checkpoint.

    The function supports:
    1. A checkpoint containing 'model_state_dict'
    2. A checkpoint containing 'state_dict'
    3. A raw PyTorch state dictionary
    """

    try:
        checkpoint = torch.load(
            path,
            map_location="cpu",
            weights_only=False,
        )
    except TypeError:
        # Compatibility for PyTorch versions without weights_only.
        checkpoint = torch.load(path, map_location="cpu")

    if not isinstance(checkpoint, dict):
        raise TypeError("The checkpoint must contain a Python dictionary.")

    if "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        checkpoint_information = checkpoint

    elif "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
        checkpoint_information = checkpoint

    elif checkpoint and all(
        isinstance(value, torch.Tensor)
        for value in checkpoint.values()
    ):
        state_dict = checkpoint
        checkpoint_information = {}

    else:
        raise ValueError(
            "The checkpoint does not contain a recognizable model state."
        )

    return state_dict, checkpoint_information


def metadata_value(
    metadata: dict[str, Any],
    key: str,
    index: int,
) -> Any:
    """
    Extract one metadata value from a DataLoader batch.

    Numeric metadata normally becomes a tensor, while text metadata
    normally becomes a list.
    """

    value = metadata[key]

    if isinstance(value, torch.Tensor):
        return value[index].item()

    return value[index]


def save_confusion_matrix(
    matrix: list[list[int]],
    class_names: tuple[str, ...],
    output_path: Path,
) -> None:
    """Save the overall confusion matrix as a CSV file."""

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(
            ["true_state"]
            + [f"predicted_{name}" for name in class_names]
        )

        for index, class_name in enumerate(class_names):
            writer.writerow([class_name] + matrix[index])


def save_per_operation_metrics(
    operation_metrics: dict[str, dict[str, Any]],
    class_names: tuple[str, ...],
    output_path: Path,
) -> None:
    """Save the important metrics for every operation as a CSV file."""

    fieldnames = [
        "operation_type",
        "sample_count",
        "accuracy",
        "macro_f1",
        "weighted_f1",
    ]

    for class_name in class_names:
        fieldnames.extend(
            [
                f"{class_name}_precision",
                f"{class_name}_recall",
                f"{class_name}_f1",
                f"{class_name}_support",
            ]
        )

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for operation_name, metrics in operation_metrics.items():
            row: dict[str, Any] = {
                "operation_type": operation_name,
                "sample_count": metrics["sample_count"],
                "accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "weighted_f1": metrics["weighted_f1"],
            }

            for class_name in class_names:
                class_metrics = metrics["per_class"][class_name]

                row[f"{class_name}_precision"] = class_metrics["precision"]
                row[f"{class_name}_recall"] = class_metrics["recall"]
                row[f"{class_name}_f1"] = class_metrics["f1"]
                row[f"{class_name}_support"] = class_metrics["support"]

            writer.writerow(row)


# ---------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------

def main() -> None:
    print("Phase 7: Operation-aware model test evaluation")
    print("=" * 55)

    # Locate the Phase 6 best checkpoint automatically.
    checkpoint_path = find_single_file(
        PHASE_6_DIR,
        "best_model.pt",
    )

    run_directory = checkpoint_path.parent

    experiment_config_path = (
        run_directory / "experiment_config.json"
    )

    validation_metrics_path = (
        run_directory / "best_validation_metrics.json"
    )

    if not experiment_config_path.is_file():
        raise FileNotFoundError(
            f"Missing experiment configuration:\n"
            f"{experiment_config_path}"
        )

    experiment = load_json(experiment_config_path)

    validation_reference = None

    if validation_metrics_path.is_file():
        validation_reference = load_json(validation_metrics_path)

    training_config = experiment["config"]

    dataset_dir = Path(experiment["dataset_dir"])
    manifest_path = Path(experiment["manifest_path"])
    operation_mapping_path = Path(
        experiment["operation_mapping_path"]
    )

    class_names = tuple(experiment["class_names"])
    operation_names = tuple(experiment["operation_names"])

    frames_per_clip = int(training_config["frames_per_clip"])
    input_size = int(training_config["input_size"])
    batch_size = int(training_config["batch_size"])
    num_workers = int(training_config["num_workers"])

    device = select_device(training_config.get("device", "auto"))

    print(f"Checkpoint: {checkpoint_path}")
    print(f"Test manifest: {manifest_path}")
    print(f"Device: {device}")
    print()

    # -------------------------------------------------------------
    # Build the untouched test dataset
    # -------------------------------------------------------------

    test_dataset = OperationAwareGarmentClipDataset(
        dataset_dir=dataset_dir,
        manifest_path=manifest_path,
        operation_mapping_path=operation_mapping_path,
        split="test",
        frames_per_clip=frames_per_clip,
        input_size=input_size,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=num_workers > 0,
    )

    print(f"Test clips: {len(test_dataset)}")
    print(f"Test videos: {len(test_dataset.source_videos)}")
    print(f"State counts: {test_dataset.class_counts}")
    print(f"Operation counts: {test_dataset.operation_counts}")
    print()

    # -------------------------------------------------------------
    # Rebuild the Phase 6 model
    # -------------------------------------------------------------

    model = OperationAwareTemporalMobileNetV3Small(
        num_classes=len(class_names),
        num_operations=len(operation_names),
        pretrained=False,
    )

    model_state_dict, checkpoint_information = load_checkpoint(
        checkpoint_path
    )

    model.load_state_dict(model_state_dict, strict=True)
    model.to(device)
    model.eval()

    checkpoint_epoch = checkpoint_information.get("epoch")

    # -------------------------------------------------------------
    # Test inference
    # -------------------------------------------------------------

    all_targets: list[int] = []
    all_predictions: list[int] = []
    all_operation_targets: list[int] = []
    prediction_rows: list[dict[str, Any]] = []

    total_cross_entropy = 0.0
    total_samples = 0

    evaluation_start_time = time.perf_counter()

    with torch.inference_mode():
        for batch in test_loader:
            if len(batch) != 4:
                raise ValueError(
                    "The operation-aware dataset must return four values: "
                    "frames, state target, operation target, and metadata."
                )

            (
                frames,
                state_targets,
                operation_targets,
                metadata,
            ) = batch

            frames = frames.to(device)
            state_targets = state_targets.to(device)
            operation_targets = operation_targets.to(device)

            logits = model(frames, operation_targets)
            probabilities = torch.softmax(logits, dim=1)
            predictions = probabilities.argmax(dim=1)

            batch_size_actual = state_targets.size(0)

            batch_loss = F.cross_entropy(
                logits,
                state_targets,
                reduction="sum",
            )

            total_cross_entropy += batch_loss.item()
            total_samples += batch_size_actual

            state_targets_cpu = state_targets.cpu()
            operation_targets_cpu = operation_targets.cpu()
            predictions_cpu = predictions.cpu()
            probabilities_cpu = probabilities.cpu()

            all_targets.extend(state_targets_cpu.tolist())
            all_predictions.extend(predictions_cpu.tolist())
            all_operation_targets.extend(
                operation_targets_cpu.tolist()
            )

            for index in range(batch_size_actual):
                true_index = int(state_targets_cpu[index])
                predicted_index = int(predictions_cpu[index])
                operation_index = int(
                    operation_targets_cpu[index]
                )

                prediction_rows.append(
                    {
                        "clip_name": metadata_value(
                            metadata,
                            "clip_name",
                            index,
                        ),
                        "video_name": metadata_value(
                            metadata,
                            "video_name",
                            index,
                        ),
                        "start_time_sec": metadata_value(
                            metadata,
                            "start_time_sec",
                            index,
                        ),
                        "end_time_sec": metadata_value(
                            metadata,
                            "end_time_sec",
                            index,
                        ),
                        "operation_type": operation_names[
                            operation_index
                        ],
                        "true_state": class_names[true_index],
                        "predicted_state": class_names[
                            predicted_index
                        ],
                        "confidence": float(
                            probabilities_cpu[index].max()
                        ),
                        "probability_idle_setup": float(
                            probabilities_cpu[index][0]
                        ),
                        "probability_sewing": float(
                            probabilities_cpu[index][1]
                        ),
                        "correct": (
                            true_index == predicted_index
                        ),
                    }
                )

    evaluation_elapsed_sec = (
        time.perf_counter() - evaluation_start_time
    )

    # -------------------------------------------------------------
    # Calculate overall metrics
    # -------------------------------------------------------------

    target_tensor = torch.tensor(
        all_targets,
        dtype=torch.int64,
    )

    prediction_tensor = torch.tensor(
        all_predictions,
        dtype=torch.int64,
    )

    operation_tensor = torch.tensor(
        all_operation_targets,
        dtype=torch.int64,
    )

    overall_metrics = classification_metrics(
        target_tensor,
        prediction_tensor,
        class_names,
    )

    mean_test_loss = (
        total_cross_entropy / total_samples
        if total_samples
        else 0.0
    )

    # -------------------------------------------------------------
    # Calculate metrics separately for each operation
    # -------------------------------------------------------------

    by_operation: dict[str, dict[str, Any]] = {}

    for operation_index, operation_name in enumerate(
        operation_names
    ):
        operation_mask = operation_tensor == operation_index
        operation_sample_count = int(operation_mask.sum())

        if operation_sample_count == 0:
            raise ValueError(
                f"No test samples were found for {operation_name}."
            )

        by_operation[operation_name] = classification_metrics(
            target_tensor[operation_mask],
            prediction_tensor[operation_mask],
            class_names,
        )

    # -------------------------------------------------------------
    # Compare test results with the saved validation result
    # -------------------------------------------------------------

    validation_comparison = None

    if validation_reference is not None:
        validation_overall = validation_reference["overall"]

        validation_comparison = {
            "validation_accuracy": validation_overall["accuracy"],
            "test_accuracy": overall_metrics["accuracy"],
            "test_minus_validation_accuracy": (
                overall_metrics["accuracy"]
                - validation_overall["accuracy"]
            ),
            "validation_macro_f1": validation_overall["macro_f1"],
            "test_macro_f1": overall_metrics["macro_f1"],
            "test_minus_validation_macro_f1": (
                overall_metrics["macro_f1"]
                - validation_overall["macro_f1"]
            ),
        }

    clips_per_second = (
        total_samples / evaluation_elapsed_sec
        if evaluation_elapsed_sec > 0
        else 0.0
    )

    # -------------------------------------------------------------
    # Save every test prediction
    # -------------------------------------------------------------

    predictions_path = OUTPUT_DIR / "test_predictions.csv"

    with predictions_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "clip_name",
                "video_name",
                "start_time_sec",
                "end_time_sec",
                "operation_type",
                "true_state",
                "predicted_state",
                "confidence",
                "probability_idle_setup",
                "probability_sewing",
                "correct",
            ],
        )

        writer.writeheader()
        writer.writerows(prediction_rows)

    # -------------------------------------------------------------
    # Save metrics
    # -------------------------------------------------------------

    test_metrics = {
        "checkpoint_epoch": checkpoint_epoch,
        "test_cross_entropy_loss": mean_test_loss,
        "overall": overall_metrics,
        "by_operation": by_operation,
    }

    test_metrics_path = OUTPUT_DIR / "test_metrics.json"
    save_json(test_metrics, test_metrics_path)

    confusion_matrix_path = (
        OUTPUT_DIR / "overall_confusion_matrix.csv"
    )

    save_confusion_matrix(
        overall_metrics["confusion_matrix"],
        class_names,
        confusion_matrix_path,
    )

    per_operation_path = (
        OUTPUT_DIR / "per_operation_metrics.csv"
    )

    save_per_operation_metrics(
        by_operation,
        class_names,
        per_operation_path,
    )

    # -------------------------------------------------------------
    # Save the Phase 7 summary
    # -------------------------------------------------------------

    phase_7_summary = {
        "status": "PASS",
        "phase": "Phase 7 - Enhanced model test evaluation",
        "architecture": experiment["architecture"],
        "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": checkpoint_epoch,
        "device": str(device),
        "test_dataset": {
            "clip_count": len(test_dataset),
            "video_count": len(test_dataset.source_videos),
            "state_counts": test_dataset.class_counts,
            "operation_counts": test_dataset.operation_counts,
        },
        "test_cross_entropy_loss": mean_test_loss,
        "overall": overall_metrics,
        "by_operation": by_operation,
        "validation_comparison": validation_comparison,
        "inference": {
            "elapsed_sec": evaluation_elapsed_sec,
            "clips_per_second": clips_per_second,
        },
        "checks": {
            "best_checkpoint_loaded": "PASS",
            "test_split_loaded": "PASS",
            "all_test_clips_evaluated": (
                "PASS"
                if total_samples == len(test_dataset)
                else "FAIL"
            ),
            "all_operations_evaluated": (
                "PASS"
                if len(by_operation) == len(operation_names)
                else "FAIL"
            ),
        },
        "outputs": {
            "test_metrics": str(test_metrics_path),
            "test_predictions": str(predictions_path),
            "overall_confusion_matrix": str(
                confusion_matrix_path
            ),
            "per_operation_metrics": str(
                per_operation_path
            ),
        },
    }

    summary_path = OUTPUT_DIR / "phase7_summary.json"
    save_json(phase_7_summary, summary_path)

    # -------------------------------------------------------------
    # Terminal report
    # -------------------------------------------------------------

    print("Phase 7 completed successfully.")
    print()
    print(f"Test loss: {mean_test_loss:.4f}")
    print(
        f"Test accuracy: "
        f"{overall_metrics['accuracy']:.4f}"
    )
    print(
        f"Test macro-F1: "
        f"{overall_metrics['macro_f1']:.4f}"
    )
    print()

    for operation_name, metrics in by_operation.items():
        print(
            f"{operation_name}: "
            f"accuracy={metrics['accuracy']:.4f}, "
            f"macro-F1={metrics['macro_f1']:.4f}"
        )

    print()
    print(f"Phase 7 summary:\n{summary_path}")


if __name__ == "__main__":
    main()