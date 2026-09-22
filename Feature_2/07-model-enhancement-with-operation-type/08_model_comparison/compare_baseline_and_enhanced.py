from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision.models import mobilenet_v3_small
from torchvision.transforms import functional as TF
from torchvision.transforms.functional import InterpolationMode


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PHASE_8_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_8_DIR.parent

BASELINE_DIR = PROJECT_ROOT / "00_protected_baseline"
PHASE_6_DIR = PROJECT_ROOT / "06_operation_aware_training"
PHASE_7_OUTPUT_DIR = PROJECT_ROOT / "07_model_evaluation" / "outputs"
OUTPUT_DIR = PHASE_8_DIR / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PHASE_7_SUMMARY_PATH = (
    PHASE_7_OUTPUT_DIR / "phase7_summary.json"
)

ENHANCED_PREDICTIONS_PATH = (
    PHASE_7_OUTPUT_DIR / "test_predictions.csv"
)


# ---------------------------------------------------------------------
# Labels and normalization
# ---------------------------------------------------------------------

CLASS_NAMES = ("IDLE_SETUP", "SEWING")
CLASS_TO_INDEX = {
    name: index
    for index, name in enumerate(CLASS_NAMES)
}

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


# ---------------------------------------------------------------------
# General utility functions
# ---------------------------------------------------------------------

def find_single_file(directory: Path, filename: str) -> Path:
    matches = sorted(directory.rglob(filename))

    if not matches:
        raise FileNotFoundError(
            f"Could not find {filename!r} inside:\n{directory}"
        )

    if len(matches) > 1:
        found_files = "\n".join(str(path) for path in matches)

        raise RuntimeError(
            f"More than one {filename!r} was found inside:\n"
            f"{directory}\n\nFound files:\n{found_files}"
        )

    return matches[0]


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found:\n{path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def choose_device(requested_device: str) -> torch.device:
    requested_device = requested_device.strip().lower()

    if requested_device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")

        if (
            hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            return torch.device("mps")

        return torch.device("cpu")

    if requested_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    if requested_device == "mps":
        if not (
            hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            raise RuntimeError("Apple MPS is not available.")

    return torch.device(requested_device)


def metadata_value(
    metadata: dict[str, Any],
    key: str,
    index: int,
) -> Any:
    value = metadata[key]

    if isinstance(value, torch.Tensor):
        return value[index].item()

    return value[index]


# ---------------------------------------------------------------------
# Test dataset
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class TestClipRecord:
    path: Path
    relative_path: str
    clip_name: str
    video_name: str
    state: str
    operation_type: str
    start_time_sec: float
    end_time_sec: float


class TestClipTransform:
    """
    Apply the same non-training preprocessing used by the two models.
    """

    def __init__(self, input_size: int = 224) -> None:
        self.input_size = input_size
        self.resize_size = int(round(input_size / 0.875))

    def __call__(self, frames: torch.Tensor) -> torch.Tensor:
        frames = TF.resize(
            frames,
            self.resize_size, # type: ignore
            interpolation=InterpolationMode.BILINEAR,
            antialias=True,
        )

        frames = TF.center_crop(
            frames,
            [self.input_size, self.input_size],
        )

        return TF.normalize(
            frames,
            IMAGENET_MEAN, # type: ignore
            IMAGENET_STD, # type: ignore
        )


def read_test_manifest(
    dataset_dir: Path,
    manifest_path: Path,
    valid_operations: tuple[str, ...],
) -> list[TestClipRecord]:
    required_columns = {
        "split",
        "clip_name",
        "relative_clip_path",
        "video_name",
        "start_time_sec",
        "end_time_sec",
        "state",
        "operation_type",
        "status",
    }

    records: list[TestClipRecord] = []

    with manifest_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        missing_columns = required_columns.difference(
            reader.fieldnames or []
        )

        if missing_columns:
            raise ValueError(
                "Enhanced manifest is missing columns: "
                f"{sorted(missing_columns)}"
            )

        for row in reader:
            if row["split"].strip().lower() != "test":
                continue

            if row["status"].strip().upper() != "GENERATED":
                continue

            state = row["state"].strip().upper()
            operation_type = row["operation_type"].strip().upper()

            if state not in CLASS_TO_INDEX:
                raise ValueError(
                    f"Unsupported state: {state!r}"
                )

            if operation_type not in valid_operations:
                raise ValueError(
                    f"Unsupported operation: {operation_type!r}"
                )

            relative_path = row["relative_clip_path"].strip()
            clip_path = (dataset_dir / relative_path).resolve()

            try:
                clip_path.relative_to(dataset_dir.resolve())
            except ValueError as error:
                raise ValueError(
                    f"Unsafe clip path: {relative_path}"
                ) from error

            if not clip_path.is_file():
                raise FileNotFoundError(
                    f"Test clip does not exist:\n{clip_path}"
                )

            records.append(
                TestClipRecord(
                    path=clip_path,
                    relative_path=relative_path,
                    clip_name=row["clip_name"].strip(),
                    video_name=row["video_name"].strip(),
                    state=state,
                    operation_type=operation_type,
                    start_time_sec=float(row["start_time_sec"]),
                    end_time_sec=float(row["end_time_sec"]),
                )
            )

    if not records:
        raise ValueError(
            "No generated test clips were found in the manifest."
        )

    clip_names = [record.clip_name for record in records]

    if len(clip_names) != len(set(clip_names)):
        raise ValueError(
            "Duplicate clip names exist in the test manifest."
        )

    return records


def decode_uniform_frames(
    path: Path,
    frames_per_clip: int,
) -> torch.Tensor:
    capture = cv2.VideoCapture(str(path))

    try:
        frame_count = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        if frame_count <= 0:
            raise RuntimeError(
                f"Video reports no frames:\n{path}"
            )

        frame_indices = np.linspace(
            0,
            frame_count - 1,
            frames_per_clip,
        ).round().astype(int)

        decoded_frames: list[torch.Tensor] = []

        for frame_index in frame_indices:
            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                int(frame_index),
            )

            success, frame = capture.read()

            if not success or frame is None:
                raise RuntimeError(
                    f"Could not decode frame {frame_index} "
                    f"from:\n{path}"
                )

            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            frame_tensor = torch.from_numpy(frame).permute(
                2,
                0,
                1,
            )

            decoded_frames.append(frame_tensor)

    finally:
        capture.release()

    return (
        torch.stack(decoded_frames)
        .float()
        .div_(255.0)
    )


class BaselineTestDataset(
    Dataset[
        tuple[
            torch.Tensor,
            int,
            int,
            dict[str, Any],
        ]
    ]
):
    def __init__(
        self,
        dataset_dir: Path,
        manifest_path: Path,
        operation_names: tuple[str, ...],
        frames_per_clip: int,
        input_size: int,
    ) -> None:
        self.dataset_dir = dataset_dir.expanduser().resolve()
        self.manifest_path = manifest_path.expanduser().resolve()
        self.operation_names = operation_names

        self.operation_to_index = {
            name: index
            for index, name in enumerate(operation_names)
        }

        self.frames_per_clip = frames_per_clip
        self.transform = TestClipTransform(input_size)

        self.records = read_test_manifest(
            self.dataset_dir,
            self.manifest_path,
            self.operation_names,
        )

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(
        self,
        index: int,
    ) -> tuple[
        torch.Tensor,
        int,
        int,
        dict[str, Any],
    ]:
        record = self.records[index]

        frames = decode_uniform_frames(
            record.path,
            self.frames_per_clip,
        )

        frames = self.transform(frames)

        state_index = CLASS_TO_INDEX[record.state]

        operation_index = self.operation_to_index[
            record.operation_type
        ]

        metadata = {
            "clip_name": record.clip_name,
            "video_name": record.video_name,
            "relative_clip_path": record.relative_path,
            "start_time_sec": record.start_time_sec,
            "end_time_sec": record.end_time_sec,
            "operation_type": record.operation_type,
        }

        return (
            frames,
            state_index,
            operation_index,
            metadata,
        )

    @property
    def source_videos(self) -> set[str]:
        return {
            record.video_name
            for record in self.records
        }

    @property
    def class_counts(self) -> dict[str, int]:
        return {
            class_name: sum(
                record.state == class_name
                for record in self.records
            )
            for class_name in CLASS_NAMES
        }

    @property
    def operation_counts(self) -> dict[str, int]:
        return {
            operation_name: sum(
                record.operation_type == operation_name
                for record in self.records
            )
            for operation_name in self.operation_names
        }


# ---------------------------------------------------------------------
# Original baseline architecture
# ---------------------------------------------------------------------

class TemporalMobileNetV3Small(nn.Module):
    """
    Original model without operation_type input.
    """

    def __init__(self, num_classes: int = 2) -> None:
        super().__init__()

        network = mobilenet_v3_small(weights=None)

        self.features = network.features
        self.avgpool = network.avgpool

        feature_dimension = (
            network.classifier[0].in_features
        )

        self.classifier = nn.Sequential(
            nn.Linear(feature_dimension, 1024), # type: ignore
            nn.Hardswish(),
            nn.Dropout(p=0.20),
            nn.Linear(1024, num_classes),
        )

    def forward(
        self,
        clips: torch.Tensor,
    ) -> torch.Tensor:
        if clips.ndim != 5:
            raise ValueError(
                "Expected clips with shape "
                "[batch, time, channels, height, width]."
            )

        (
            batch_size,
            time_steps,
            channels,
            height,
            width,
        ) = clips.shape

        frames = clips.reshape(
            batch_size * time_steps,
            channels,
            height,
            width,
        )

        visual_features = self.features(frames)
        visual_features = self.avgpool(visual_features)
        visual_features = visual_features.flatten(1)

        visual_features = visual_features.reshape(
            batch_size,
            time_steps,
            -1,
        )

        temporal_features = visual_features.mean(dim=1)

        return self.classifier(temporal_features)


# ---------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------

def classification_metrics(
    targets: torch.Tensor,
    predictions: torch.Tensor,
    class_names: tuple[str, ...],
) -> dict[str, Any]:
    targets = targets.to(torch.int64).cpu()
    predictions = predictions.to(torch.int64).cpu()

    number_of_classes = len(class_names)

    matrix = torch.zeros(
        (number_of_classes, number_of_classes),
        dtype=torch.int64,
    )

    for target, prediction in zip(
        targets,
        predictions,
        strict=True,
    ):
        matrix[target, prediction] += 1

    total = int(matrix.sum())
    correct = int(matrix.diag().sum())

    accuracy = correct / total if total else 0.0

    per_class: dict[str, dict[str, float | int]] = {}

    f1_values: list[float] = []
    weighted_f1_sum = 0.0

    for index, class_name in enumerate(class_names):
        true_positive = int(matrix[index, index])

        false_positive = (
            int(matrix[:, index].sum())
            - true_positive
        )

        false_negative = (
            int(matrix[index, :].sum())
            - true_positive
        )

        support = int(matrix[index, :].sum())

        precision_denominator = (
            true_positive + false_positive
        )

        recall_denominator = (
            true_positive + false_negative
        )

        precision = (
            true_positive / precision_denominator
            if precision_denominator
            else 0.0
        )

        recall = (
            true_positive / recall_denominator
            if recall_denominator
            else 0.0
        )

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        f1_values.append(f1)
        weighted_f1_sum += f1 * support

        per_class[class_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    return {
        "accuracy": accuracy,
        "macro_f1": sum(f1_values) / len(f1_values),
        "weighted_f1": (
            weighted_f1_sum / total
            if total
            else 0.0
        ),
        "sample_count": total,
        "correct_count": correct,
        "error_count": total - correct,
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


# ---------------------------------------------------------------------
# Checkpoint loading
# ---------------------------------------------------------------------

def load_baseline_checkpoint(
    checkpoint_path: Path,
) -> tuple[
    dict[str, torch.Tensor],
    dict[str, Any],
]:
    try:
        checkpoint = torch.load(
            checkpoint_path,
            map_location="cpu",
            weights_only=False,
        )
    except TypeError:
        checkpoint = torch.load(
            checkpoint_path,
            map_location="cpu",
        )

    if not isinstance(checkpoint, dict):
        raise TypeError(
            "The baseline checkpoint is not a dictionary."
        )

    architecture = checkpoint.get("architecture")

    if architecture not in {
        None,
        "TemporalMobileNetV3Small",
    }:
        raise ValueError(
            "Unexpected baseline architecture: "
            f"{architecture}"
        )

    if "model_state_dict" in checkpoint:
        return checkpoint["model_state_dict"], checkpoint

    if "state_dict" in checkpoint:
        return checkpoint["state_dict"], checkpoint

    if checkpoint and all(
        isinstance(value, torch.Tensor)
        for value in checkpoint.values()
    ):
        return checkpoint, {}

    raise ValueError(
        "Could not find the baseline model state dictionary."
    )


# ---------------------------------------------------------------------
# Enhanced prediction loading
# ---------------------------------------------------------------------

def load_prediction_csv(
    path: Path,
) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Prediction CSV not found:\n{path}"
        )

    predictions: dict[str, dict[str, str]] = {}

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        required_columns = {
            "clip_name",
            "video_name",
            "operation_type",
            "true_state",
            "predicted_state",
        }

        missing_columns = required_columns.difference(
            reader.fieldnames or []
        )

        if missing_columns:
            raise ValueError(
                "Prediction CSV is missing columns: "
                f"{sorted(missing_columns)}"
            )

        for row in reader:
            clip_name = row["clip_name"].strip()

            if clip_name in predictions:
                raise ValueError(
                    f"Duplicate prediction: {clip_name}"
                )

            predictions[clip_name] = row

    return predictions


# ---------------------------------------------------------------------
# Paired comparison
# ---------------------------------------------------------------------

def exact_mcnemar_p_value(
    baseline_only_correct: int,
    enhanced_only_correct: int,
) -> float:
    """
    Calculate the exact two-sided McNemar/binomial p-value.

    It checks whether the difference between the two models' paired
    predictions could reasonably occur by chance.
    """

    discordant = (
        baseline_only_correct
        + enhanced_only_correct
    )

    if discordant == 0:
        return 1.0

    smaller = min(
        baseline_only_correct,
        enhanced_only_correct,
    )

    probability = sum(
        math.comb(discordant, value)
        * (0.5 ** discordant)
        for value in range(smaller + 1)
    )

    return min(1.0, 2.0 * probability)


def parameter_count(model: nn.Module) -> int:
    return sum(
        parameter.numel()
        for parameter in model.parameters()
    )


# ---------------------------------------------------------------------
# Main Phase 8 process
# ---------------------------------------------------------------------

def main() -> None:
    print("Phase 8: Baseline vs operation-aware model")
    print("=" * 55)

    baseline_checkpoint_path = find_single_file(
        BASELINE_DIR,
        "best_model.pt",
    )

    phase_6_experiment_path = find_single_file(
        PHASE_6_DIR,
        "experiment_config.json",
    )

    phase_6_experiment = load_json(
        phase_6_experiment_path
    )

    phase_7_summary = load_json(
        PHASE_7_SUMMARY_PATH
    )

    enhanced_predictions = load_prediction_csv(
        ENHANCED_PREDICTIONS_PATH
    )

    dataset_dir = Path(
        phase_6_experiment["dataset_dir"]
    )

    enhanced_manifest_path = Path(
        phase_6_experiment["manifest_path"]
    )

    training_config = phase_6_experiment["config"]

    operation_names = tuple(
        phase_6_experiment["operation_names"]
    )

    frames_per_clip = int(
        training_config["frames_per_clip"]
    )

    input_size = int(
        training_config["input_size"]
    )

    batch_size = int(
        training_config["batch_size"]
    )

    num_workers = int(
        training_config["num_workers"]
    )

    device = choose_device(
        training_config.get("device", "auto")
    )

    print(f"Baseline checkpoint: {baseline_checkpoint_path}")
    print(f"Test manifest: {enhanced_manifest_path}")
    print(f"Device: {device}")
    print()

    # -------------------------------------------------------------
    # Create the test dataset
    # -------------------------------------------------------------

    test_dataset = BaselineTestDataset(
        dataset_dir=dataset_dir,
        manifest_path=enhanced_manifest_path,
        operation_names=operation_names,
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
    # Load the original baseline model
    # -------------------------------------------------------------

    baseline_model = TemporalMobileNetV3Small(
        num_classes=len(CLASS_NAMES)
    )

    (
        baseline_state_dict,
        baseline_checkpoint,
    ) = load_baseline_checkpoint(
        baseline_checkpoint_path
    )

    baseline_model.load_state_dict(
        baseline_state_dict,
        strict=True,
    )

    baseline_model.to(device)
    baseline_model.eval()

    baseline_checkpoint_epoch = (
        baseline_checkpoint.get("epoch")
    )

    # -------------------------------------------------------------
    # Evaluate baseline model
    # -------------------------------------------------------------

    all_targets: list[int] = []
    all_predictions: list[int] = []
    all_operation_targets: list[int] = []

    baseline_prediction_rows: list[dict[str, Any]] = []

    total_loss = 0.0
    evaluated_samples = 0

    evaluation_start = time.perf_counter()

    with torch.inference_mode():
        for (
            frames,
            state_targets,
            operation_targets,
            metadata,
        ) in test_loader:
            frames = frames.to(device)
            state_targets = state_targets.to(device)

            logits = baseline_model(frames)

            probabilities = torch.softmax(
                logits,
                dim=1,
            )

            predictions = probabilities.argmax(dim=1)

            batch_loss = F.cross_entropy(
                logits,
                state_targets,
                reduction="sum",
            )

            batch_size_actual = state_targets.size(0)

            total_loss += float(batch_loss)
            evaluated_samples += batch_size_actual

            state_targets_cpu = state_targets.cpu()
            predictions_cpu = predictions.cpu()
            probabilities_cpu = probabilities.cpu()
            operation_targets_cpu = operation_targets.cpu()

            all_targets.extend(
                state_targets_cpu.tolist()
            )

            all_predictions.extend(
                predictions_cpu.tolist()
            )

            all_operation_targets.extend(
                operation_targets_cpu.tolist()
            )

            for index in range(batch_size_actual):
                true_index = int(
                    state_targets_cpu[index]
                )

                predicted_index = int(
                    predictions_cpu[index]
                )

                operation_index = int(
                    operation_targets_cpu[index]
                )

                baseline_prediction_rows.append(
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
                        "true_state": CLASS_NAMES[
                            true_index
                        ],
                        "predicted_state": CLASS_NAMES[
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

    baseline_elapsed_sec = (
        time.perf_counter() - evaluation_start
    )

    baseline_loss = (
        total_loss / evaluated_samples
        if evaluated_samples
        else 0.0
    )

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

    baseline_overall = classification_metrics(
        target_tensor,
        prediction_tensor,
        CLASS_NAMES,
    )

    baseline_by_operation: dict[str, dict[str, Any]] = {}

    for operation_index, operation_name in enumerate(
        operation_names
    ):
        mask = operation_tensor == operation_index

        baseline_by_operation[operation_name] = (
            classification_metrics(
                target_tensor[mask],
                prediction_tensor[mask],
                CLASS_NAMES,
            )
        )

    # -------------------------------------------------------------
    # Save baseline predictions
    # -------------------------------------------------------------

    baseline_predictions_path = (
        OUTPUT_DIR / "baseline_test_predictions.csv"
    )

    prediction_fieldnames = [
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
    ]

    with baseline_predictions_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=prediction_fieldnames,
        )

        writer.writeheader()
        writer.writerows(baseline_prediction_rows)

    baseline_prediction_map = {
        row["clip_name"]: row
        for row in baseline_prediction_rows
    }

    # -------------------------------------------------------------
    # Validate paired test samples
    # -------------------------------------------------------------

    baseline_clip_names = set(
        baseline_prediction_map
    )

    enhanced_clip_names = set(
        enhanced_predictions
    )

    if baseline_clip_names != enhanced_clip_names:
        missing_from_baseline = sorted(
            enhanced_clip_names - baseline_clip_names
        )

        missing_from_enhanced = sorted(
            baseline_clip_names - enhanced_clip_names
        )

        raise ValueError(
            "Baseline and enhanced prediction files do not "
            "contain identical test clips.\n"
            f"Missing from baseline: {missing_from_baseline[:10]}\n"
            f"Missing from enhanced: {missing_from_enhanced[:10]}"
        )

    # -------------------------------------------------------------
    # Clip-by-clip comparison
    # -------------------------------------------------------------

    both_correct = 0
    baseline_only_correct = 0
    enhanced_only_correct = 0
    both_wrong = 0

    paired_rows: list[dict[str, Any]] = []

    for baseline_row in baseline_prediction_rows:
        clip_name = baseline_row["clip_name"]
        enhanced_row = enhanced_predictions[clip_name]

        baseline_true_state = str(
            baseline_row["true_state"]
        )

        enhanced_true_state = enhanced_row[
            "true_state"
        ].strip()

        baseline_operation = str(
            baseline_row["operation_type"]
        )

        enhanced_operation = enhanced_row[
            "operation_type"
        ].strip()

        if baseline_true_state != enhanced_true_state:
            raise ValueError(
                f"True-state mismatch for {clip_name}"
            )

        if baseline_operation != enhanced_operation:
            raise ValueError(
                f"Operation mismatch for {clip_name}"
            )

        baseline_correct = (
            baseline_row["predicted_state"]
            == baseline_true_state
        )

        enhanced_correct = (
            enhanced_row["predicted_state"].strip()
            == enhanced_true_state
        )

        if baseline_correct and enhanced_correct:
            comparison_category = "BOTH_CORRECT"
            both_correct += 1

        elif baseline_correct and not enhanced_correct:
            comparison_category = "BASELINE_ONLY_CORRECT"
            baseline_only_correct += 1

        elif not baseline_correct and enhanced_correct:
            comparison_category = "ENHANCED_ONLY_CORRECT"
            enhanced_only_correct += 1

        else:
            comparison_category = "BOTH_WRONG"
            both_wrong += 1

        paired_rows.append(
            {
                "clip_name": clip_name,
                "video_name": baseline_row["video_name"],
                "operation_type": baseline_operation,
                "true_state": baseline_true_state,
                "baseline_prediction": baseline_row[
                    "predicted_state"
                ],
                "enhanced_prediction": enhanced_row[
                    "predicted_state"
                ].strip(),
                "baseline_correct": baseline_correct,
                "enhanced_correct": enhanced_correct,
                "comparison_category": comparison_category,
            }
        )

    mcnemar_p_value = exact_mcnemar_p_value(
        baseline_only_correct,
        enhanced_only_correct,
    )

    # -------------------------------------------------------------
    # Enhanced metrics from Phase 7
    # -------------------------------------------------------------

    enhanced_overall = phase_7_summary["overall"]
    enhanced_by_operation = phase_7_summary["by_operation"]

    enhanced_elapsed_sec = phase_7_summary[
        "inference"
    ]["elapsed_sec"]

    enhanced_clips_per_second = phase_7_summary[
        "inference"
    ]["clips_per_second"]

    baseline_clips_per_second = (
        evaluated_samples / baseline_elapsed_sec
        if baseline_elapsed_sec > 0
        else 0.0
    )

    # -------------------------------------------------------------
    # Main metric comparison
    # -------------------------------------------------------------

    overall_comparison = {
        "accuracy": {
            "baseline": baseline_overall["accuracy"],
            "enhanced": enhanced_overall["accuracy"],
            "difference": (
                enhanced_overall["accuracy"]
                - baseline_overall["accuracy"]
            ),
        },
        "macro_f1": {
            "baseline": baseline_overall["macro_f1"],
            "enhanced": enhanced_overall["macro_f1"],
            "difference": (
                enhanced_overall["macro_f1"]
                - baseline_overall["macro_f1"]
            ),
        },
        "weighted_f1": {
            "baseline": baseline_overall["weighted_f1"],
            "enhanced": enhanced_overall["weighted_f1"],
            "difference": (
                enhanced_overall["weighted_f1"]
                - baseline_overall["weighted_f1"]
            ),
        },
        "error_count": {
            "baseline": baseline_overall["error_count"],
            "enhanced": (
                enhanced_overall["sample_count"]
                - sum(
                    enhanced_overall["confusion_matrix"][index][index]
                    for index in range(len(CLASS_NAMES))
                )
            ),
        },
    }

    per_operation_comparison: dict[str, Any] = {}

    for operation_name in operation_names:
        baseline_metrics = baseline_by_operation[
            operation_name
        ]

        enhanced_metrics = enhanced_by_operation[
            operation_name
        ]

        per_operation_comparison[operation_name] = {
            "sample_count": baseline_metrics["sample_count"],
            "baseline_accuracy": baseline_metrics["accuracy"],
            "enhanced_accuracy": enhanced_metrics["accuracy"],
            "accuracy_difference": (
                enhanced_metrics["accuracy"]
                - baseline_metrics["accuracy"]
            ),
            "baseline_macro_f1": baseline_metrics["macro_f1"],
            "enhanced_macro_f1": enhanced_metrics["macro_f1"],
            "macro_f1_difference": (
                enhanced_metrics["macro_f1"]
                - baseline_metrics["macro_f1"]
            ),
        }

    if (
        enhanced_overall["macro_f1"]
        > baseline_overall["macro_f1"]
    ):
        metric_winner = "OPERATION_AWARE_MODEL"

    elif (
        enhanced_overall["macro_f1"]
        < baseline_overall["macro_f1"]
    ):
        metric_winner = "BASELINE_MODEL"

    else:
        metric_winner = "TIE"

    if mcnemar_p_value < 0.05:
        significance_result = (
            "STATISTICALLY_SIGNIFICANT_CLIP_LEVEL_DIFFERENCE"
        )
    else:
        significance_result = (
            "NO_STATISTICALLY_SIGNIFICANT_CLIP_LEVEL_DIFFERENCE"
        )

    # -------------------------------------------------------------
    # Save paired comparison CSV
    # -------------------------------------------------------------

    paired_comparison_path = (
        OUTPUT_DIR / "paired_prediction_comparison.csv"
    )

    with paired_comparison_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "clip_name",
                "video_name",
                "operation_type",
                "true_state",
                "baseline_prediction",
                "enhanced_prediction",
                "baseline_correct",
                "enhanced_correct",
                "comparison_category",
            ],
        )

        writer.writeheader()
        writer.writerows(paired_rows)

    # -------------------------------------------------------------
    # Save overall comparison CSV
    # -------------------------------------------------------------

    comparison_csv_path = (
        OUTPUT_DIR / "overall_model_comparison.csv"
    )

    comparison_rows = [
        {
            "metric": "accuracy",
            "baseline": baseline_overall["accuracy"],
            "enhanced": enhanced_overall["accuracy"],
            "difference_enhanced_minus_baseline": (
                enhanced_overall["accuracy"]
                - baseline_overall["accuracy"]
            ),
        },
        {
            "metric": "macro_f1",
            "baseline": baseline_overall["macro_f1"],
            "enhanced": enhanced_overall["macro_f1"],
            "difference_enhanced_minus_baseline": (
                enhanced_overall["macro_f1"]
                - baseline_overall["macro_f1"]
            ),
        },
        {
            "metric": "weighted_f1",
            "baseline": baseline_overall["weighted_f1"],
            "enhanced": enhanced_overall["weighted_f1"],
            "difference_enhanced_minus_baseline": (
                enhanced_overall["weighted_f1"]
                - baseline_overall["weighted_f1"]
            ),
        },
        {
            "metric": "IDLE_SETUP_f1",
            "baseline": baseline_overall[
                "per_class"
            ]["IDLE_SETUP"]["f1"],
            "enhanced": enhanced_overall[
                "per_class"
            ]["IDLE_SETUP"]["f1"],
            "difference_enhanced_minus_baseline": (
                enhanced_overall["per_class"][
                    "IDLE_SETUP"
                ]["f1"]
                - baseline_overall["per_class"][
                    "IDLE_SETUP"
                ]["f1"]
            ),
        },
        {
            "metric": "SEWING_f1",
            "baseline": baseline_overall[
                "per_class"
            ]["SEWING"]["f1"],
            "enhanced": enhanced_overall[
                "per_class"
            ]["SEWING"]["f1"],
            "difference_enhanced_minus_baseline": (
                enhanced_overall["per_class"][
                    "SEWING"
                ]["f1"]
                - baseline_overall["per_class"][
                    "SEWING"
                ]["f1"]
            ),
        },
        {
            "metric": "clips_per_second",
            "baseline": baseline_clips_per_second,
            "enhanced": enhanced_clips_per_second,
            "difference_enhanced_minus_baseline": (
                enhanced_clips_per_second
                - baseline_clips_per_second
            ),
        },
    ]

    with comparison_csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "metric",
                "baseline",
                "enhanced",
                "difference_enhanced_minus_baseline",
            ],
        )

        writer.writeheader()
        writer.writerows(comparison_rows)

    # -------------------------------------------------------------
    # Save per-operation comparison CSV
    # -------------------------------------------------------------

    per_operation_csv_path = (
        OUTPUT_DIR / "per_operation_comparison.csv"
    )

    with per_operation_csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        fieldnames = [
            "operation_type",
            "sample_count",
            "baseline_accuracy",
            "enhanced_accuracy",
            "accuracy_difference",
            "baseline_macro_f1",
            "enhanced_macro_f1",
            "macro_f1_difference",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for operation_name, metrics in (
            per_operation_comparison.items()
        ):
            writer.writerow(
                {
                    "operation_type": operation_name,
                    **metrics,
                }
            )

    # -------------------------------------------------------------
    # Save baseline metrics
    # -------------------------------------------------------------

    baseline_metrics_path = (
        OUTPUT_DIR / "baseline_test_metrics.json"
    )

    baseline_metrics_output = {
        "checkpoint_epoch": baseline_checkpoint_epoch,
        "test_loss": baseline_loss,
        "overall": baseline_overall,
        "by_operation": baseline_by_operation,
        "inference": {
            "elapsed_sec": baseline_elapsed_sec,
            "clips_per_second": baseline_clips_per_second,
        },
    }

    save_json(
        baseline_metrics_output,
        baseline_metrics_path,
    )

    # -------------------------------------------------------------
    # Phase 8 summary
    # -------------------------------------------------------------

    phase_8_summary = {
        "status": "PASS",
        "phase": "Phase 8 - Baseline vs enhanced comparison",
        "test_dataset": {
            "clip_count": len(test_dataset),
            "video_count": len(test_dataset.source_videos),
            "state_counts": test_dataset.class_counts,
            "operation_counts": test_dataset.operation_counts,
        },
        "baseline": {
            "architecture": "TemporalMobileNetV3Small",
            "checkpoint": str(baseline_checkpoint_path),
            "checkpoint_epoch": baseline_checkpoint_epoch,
            "parameter_count": parameter_count(
                baseline_model
            ),
            "test_loss": baseline_loss,
            "overall": baseline_overall,
            "by_operation": baseline_by_operation,
            "inference": {
                "elapsed_sec": baseline_elapsed_sec,
                "clips_per_second": baseline_clips_per_second,
            },
        },
        "enhanced": {
            "architecture": phase_7_summary["architecture"],
            "checkpoint": phase_7_summary["checkpoint"],
            "checkpoint_epoch": phase_7_summary[
                "checkpoint_epoch"
            ],
            "overall": enhanced_overall,
            "by_operation": enhanced_by_operation,
            "inference": {
                "elapsed_sec": enhanced_elapsed_sec,
                "clips_per_second": enhanced_clips_per_second,
            },
        },
        "overall_comparison": overall_comparison,
        "per_operation_comparison": (
            per_operation_comparison
        ),
        "paired_prediction_comparison": {
            "both_correct": both_correct,
            "baseline_only_correct": baseline_only_correct,
            "enhanced_only_correct": enhanced_only_correct,
            "both_wrong": both_wrong,
            "net_correct_prediction_gain": (
                enhanced_only_correct
                - baseline_only_correct
            ),
            "discordant_prediction_count": (
                baseline_only_correct
                + enhanced_only_correct
            ),
            "exact_mcnemar_p_value": mcnemar_p_value,
            "significance_result": significance_result,
        },
        "result": {
            "primary_metric": "macro_f1",
            "metric_winner": metric_winner,
            "note": (
                "The operation-aware model should only be accepted "
                "as an improvement after considering overall metrics, "
                "per-operation metrics, paired predictions, inference "
                "speed, and the practical need to provide operation_type."
            ),
        },
        "checks": {
            "baseline_checkpoint_loaded": "PASS",
            "same_test_clip_count": (
                "PASS"
                if len(test_dataset)
                == phase_7_summary["overall"]["sample_count"]
                else "FAIL"
            ),
            "same_clip_names": "PASS",
            "same_true_labels": "PASS",
            "same_operation_labels": "PASS",
            "all_baseline_clips_evaluated": (
                "PASS"
                if evaluated_samples == len(test_dataset)
                else "FAIL"
            ),
        },
        "outputs": {
            "baseline_metrics": str(
                baseline_metrics_path
            ),
            "baseline_predictions": str(
                baseline_predictions_path
            ),
            "overall_comparison": str(
                comparison_csv_path
            ),
            "per_operation_comparison": str(
                per_operation_csv_path
            ),
            "paired_prediction_comparison": str(
                paired_comparison_path
            ),
        },
    }

    phase_8_summary_path = (
        OUTPUT_DIR / "phase8_summary.json"
    )

    save_json(
        phase_8_summary,
        phase_8_summary_path,
    )

    # -------------------------------------------------------------
    # Terminal result
    # -------------------------------------------------------------

    print("Phase 8 completed successfully.")
    print()

    print(
        "Baseline accuracy: "
        f"{baseline_overall['accuracy']:.4f}"
    )

    print(
        "Enhanced accuracy: "
        f"{enhanced_overall['accuracy']:.4f}"
    )

    print(
        "Baseline macro-F1: "
        f"{baseline_overall['macro_f1']:.4f}"
    )

    print(
        "Enhanced macro-F1: "
        f"{enhanced_overall['macro_f1']:.4f}"
    )

    print()

    print(
        "Baseline-only correct clips: "
        f"{baseline_only_correct}"
    )

    print(
        "Enhanced-only correct clips: "
        f"{enhanced_only_correct}"
    )

    print(
        "McNemar p-value: "
        f"{mcnemar_p_value:.6f}"
    )

    print(f"Metric winner: {metric_winner}")

    print()
    print(
        f"Phase 8 summary:\n{phase_8_summary_path}"
    )


if __name__ == "__main__":
    main()