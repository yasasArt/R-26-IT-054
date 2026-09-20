from __future__ import annotations

import csv
import json
import os
import platform
import random
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchvision
from torch import nn
from torch.utils.data import DataLoader

from src.dataset import (
    CLASS_NAMES,
    OperationAwareGarmentClipDataset,
    assert_no_video_leakage,
)

from src.metrics import (
    classification_metrics,
    classification_metrics_by_operation,
)

from src.model import (
    OperationAwareTemporalMobileNetV3Small,
    build_optimizer,
)


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

TRAINING_CONFIG_PATH = (
    SCRIPT_DIR
    / "config"
    / "training_config.json"
)

PATHS_CONFIG_PATH = (
    SCRIPT_DIR
    / "config"
    / "paths_config.json"
)

MANIFEST_PATH = (
    PROJECT_ROOT
    / "03_dataset_splitting"
    / "outputs"
    / "enhanced_clip_manifest.csv"
)

OPERATION_MAPPING_PATH = (
    PROJECT_ROOT
    / "04_operation_aware_dataset"
    / "config"
    / "operation_mapping.json"
)

OUTPUT_DIR = (
    SCRIPT_DIR
    / "models"
    / "operation_aware_experiment_01"
)


# ---------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------

def read_json(
    file_path: Path,
) -> dict[str, Any]:
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Required JSON file was not found: "
            f"{file_path}"
        )

    try:
        data = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON file: {file_path}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            f"{file_path.name} must contain "
            "a JSON object."
        )

    return data


def validate_training_config(
    config: dict[str, Any],
) -> None:
    required_keys = {
        "seed",
        "frames_per_clip",
        "input_size",
        "batch_size",
        "num_workers",
        "epochs",
        "early_stopping_patience",
        "backbone_learning_rate",
        "classifier_learning_rate",
        "weight_decay",
        "label_smoothing",
        "use_class_weights",
        "pretrained",
        "device",
    }

    missing_keys = required_keys.difference(
        config
    )

    if missing_keys:
        raise ValueError(
            "Training configuration is missing: "
            f"{sorted(missing_keys)}"
        )


# ---------------------------------------------------------
# Reproducibility and device
# ---------------------------------------------------------

def choose_device(
    requested_device: str,
) -> torch.device:
    requested_device = (
        requested_device.strip().lower()
    )

    if requested_device != "auto":
        return torch.device(
            requested_device
        )

    if torch.cuda.is_available():
        return torch.device("cuda")

    if (
        getattr(
            torch.backends,
            "mps",
            None,
        )
        and torch.backends.mps.is_available()
    ):
        return torch.device("mps")

    return torch.device("cpu")


def seed_everything(
    seed: int,
) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(
            seed
        )

    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def seed_worker(
    worker_id: int,
) -> None:
    worker_seed = (
        torch.initial_seed()
        % (2**32)
    )

    np.random.seed(
        worker_seed
    )

    random.seed(
        worker_seed
    )


# ---------------------------------------------------------
# Dataset and DataLoader
# ---------------------------------------------------------

def make_loader(
    dataset: OperationAwareGarmentClipDataset,
    batch_size: int,
    num_workers: int,
    shuffle: bool,
    device: torch.device,
    seed: int,
) -> DataLoader:
    generator = torch.Generator().manual_seed(
        seed
    )

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=(
            device.type == "cuda"
        ),
        persistent_workers=(
            num_workers > 0
        ),
        worker_init_fn=seed_worker,
        generator=generator,
    )


def calculate_class_weights(
    dataset: OperationAwareGarmentClipDataset,
    device: torch.device,
) -> torch.Tensor:
    counts = dataset.class_counts
    total = sum(
        counts.values()
    )

    weights = [
        total
        / (
            len(CLASS_NAMES)
            * counts[class_name]
        )
        for class_name in CLASS_NAMES
    ]

    return torch.tensor(
        weights,
        dtype=torch.float32,
        device=device,
    )


# ---------------------------------------------------------
# Training and validation epoch
# ---------------------------------------------------------

def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    scaler: Any,
    operation_names: tuple[str, ...],
) -> tuple[
    float,
    dict[str, Any],
    dict[str, dict[str, Any]],
]:
    training = optimizer is not None

    model.train(
        training
    )

    total_loss = 0.0

    all_targets: list[
        torch.Tensor
    ] = []

    all_predictions: list[
        torch.Tensor
    ] = []

    all_operations: list[
        torch.Tensor
    ] = []

    amp_enabled = (
        device.type == "cuda"
    )

    for (
        clips,
        targets,
        operation_indices,
        _metadata,
    ) in loader:

        clips = clips.to(
            device,
            non_blocking=True,
        )

        targets = targets.to(
            device,
            non_blocking=True,
        )

        operation_indices = (
            operation_indices.to(
                device,
                non_blocking=True,
            )
        )

        if training:
            optimizer.zero_grad(
                set_to_none=True
            )

        gradient_context = (
            nullcontext()
            if training
            else torch.no_grad()
        )

        with gradient_context:
            with torch.autocast(
                device_type=device.type,
                enabled=amp_enabled,
            ):
                logits = model(
                    clips,
                    operation_indices,
                )

                loss = criterion(
                    logits,
                    targets,
                )

        if training:
            scaler.scale(
                loss
            ).backward()

            scaler.unscale_(
                optimizer
            )

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=5.0,
            )

            scaler.step(
                optimizer
            )

            scaler.update()

        total_loss += (
            float(loss.detach())
            * targets.size(0)
        )

        predictions = logits.detach().argmax(
            dim=1
        )

        all_targets.append(
            targets.detach().cpu()
        )

        all_predictions.append(
            predictions.cpu()
        )

        all_operations.append(
            operation_indices.detach().cpu()
        )

    combined_targets = torch.cat(
        all_targets
    )

    combined_predictions = torch.cat(
        all_predictions
    )

    combined_operations = torch.cat(
        all_operations
    )

    overall_metrics = (
        classification_metrics(
            combined_targets,
            combined_predictions,
            CLASS_NAMES,
        )
    )

    operation_metrics = (
        classification_metrics_by_operation(
            combined_targets,
            combined_predictions,
            combined_operations,
            CLASS_NAMES,
            operation_names,
        )
    )

    average_loss = (
        total_loss
        / len(loader.dataset) # type: ignore
    )

    return (
        average_loss,
        overall_metrics,
        operation_metrics,
    )


# ---------------------------------------------------------
# Output writing
# ---------------------------------------------------------

def write_json(
    file_path: Path,
    data: Any,
) -> None:
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


def write_training_history(
    file_path: Path,
    history: list[dict[str, Any]],
) -> None:
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
            fieldnames=list(
                history[0]
            ),
        )

        writer.writeheader()
        writer.writerows(
            history
        )

    os.replace(
        temporary_path,
        file_path,
    )


def save_checkpoint(
    file_path: Path,
    payload: dict[str, Any],
) -> None:
    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = file_path.with_suffix(
        file_path.suffix + ".tmp"
    )

    torch.save(
        payload,
        temporary_path,
    )

    os.replace(
        temporary_path,
        file_path,
    )


# ---------------------------------------------------------
# Main training program
# ---------------------------------------------------------

def main() -> int:
    try:
        config = read_json(
            TRAINING_CONFIG_PATH
        )

        paths_config = read_json(
            PATHS_CONFIG_PATH
        )

        validate_training_config(
            config
        )

        dataset_dir_value = (
            paths_config.get(
                "dataset_dir"
            )
        )

        if not dataset_dir_value:
            raise ValueError(
                "paths_config.json does not contain "
                "dataset_dir."
            )

        dataset_dir = (
            Path(dataset_dir_value)
            .expanduser()
            .resolve()
        )

        if not dataset_dir.is_dir():
            raise FileNotFoundError(
                f"Dataset directory was not found: "
                f"{dataset_dir}"
            )

        resume_value = paths_config.get(
            "resume_checkpoint"
        )

        resume_checkpoint = (
            Path(resume_value)
            .expanduser()
            .resolve()
            if resume_value
            else None
        )

        if (
            resume_checkpoint is not None
            and not resume_checkpoint.is_file()
        ):
            raise FileNotFoundError(
                f"Resume checkpoint was not found: "
                f"{resume_checkpoint}"
            )

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        seed = int(
            config["seed"]
        )

        seed_everything(
            seed
        )

        device = choose_device(
            str(config["device"])
        )

        train_dataset = (
            OperationAwareGarmentClipDataset(
                dataset_dir=dataset_dir,
                manifest_path=MANIFEST_PATH,
                operation_mapping_path=(
                    OPERATION_MAPPING_PATH
                ),
                split="train",
                frames_per_clip=int(
                    config["frames_per_clip"]
                ),
                input_size=int(
                    config["input_size"]
                ),
            )
        )

        validation_dataset = (
            OperationAwareGarmentClipDataset(
                dataset_dir=dataset_dir,
                manifest_path=MANIFEST_PATH,
                operation_mapping_path=(
                    OPERATION_MAPPING_PATH
                ),
                split="validation",
                frames_per_clip=int(
                    config["frames_per_clip"]
                ),
                input_size=int(
                    config["input_size"]
                ),
            )
        )

        assert_no_video_leakage(
            train_dataset,
            validation_dataset,
        )

        operation_names = (
            train_dataset.index_to_operation
        )

        if (
            validation_dataset.index_to_operation
            != operation_names
        ):
            raise ValueError(
                "Training and validation datasets "
                "use different operation mappings."
            )

        train_loader = make_loader(
            dataset=train_dataset,
            batch_size=int(
                config["batch_size"]
            ),
            num_workers=int(
                config["num_workers"]
            ),
            shuffle=True,
            device=device,
            seed=seed,
        )

        validation_loader = make_loader(
            dataset=validation_dataset,
            batch_size=int(
                config["batch_size"]
            ),
            num_workers=int(
                config["num_workers"]
            ),
            shuffle=False,
            device=device,
            seed=seed,
        )

        model = (
            OperationAwareTemporalMobileNetV3Small(
                num_classes=len(
                    CLASS_NAMES
                ),
                num_operations=len(
                    operation_names
                ),
                pretrained=bool(
                    config["pretrained"]
                ),
            )
            .to(device)
        )

        optimizer = build_optimizer(
            model=model,
            backbone_learning_rate=float(
                config[
                    "backbone_learning_rate"
                ]
            ),
            classifier_learning_rate=float(
                config[
                    "classifier_learning_rate"
                ]
            ),
            weight_decay=float(
                config["weight_decay"]
            ),
        )

        scheduler = (
            torch.optim.lr_scheduler
            .CosineAnnealingLR(
                optimizer,
                T_max=int(
                    config["epochs"]
                ),
                eta_min=1e-6,
            )
        )

        class_weight_tensor = (
            calculate_class_weights(
                train_dataset,
                device,
            )
            if config["use_class_weights"]
            else None
        )

        criterion = nn.CrossEntropyLoss(
            weight=class_weight_tensor,
            label_smoothing=float(
                config["label_smoothing"]
            ),
        )

        if (
            hasattr(torch, "amp")
            and hasattr(
                torch.amp,
                "GradScaler",
            )
        ):
            scaler = torch.amp.GradScaler(
                "cuda",
                enabled=device.type == "cuda",
            )

        else:
            scaler = (
                torch.cuda.amp.GradScaler(
                    enabled=(
                        device.type == "cuda"
                    )
                )
            )

        start_epoch = 1
        best_validation_macro_f1 = -1.0
        best_validation_loss = float("inf")
        epochs_without_improvement = 0

        history: list[
            dict[str, Any]
        ] = []

        if resume_checkpoint is not None:
            checkpoint = torch.load(
                resume_checkpoint,
                map_location=device,
                weights_only=True,
            )

            if checkpoint["config"] != config:
                raise ValueError(
                    "Resume checkpoint configuration "
                    "does not match training_config.json."
                )

            model.load_state_dict(
                checkpoint[
                    "model_state_dict"
                ]
            )

            optimizer.load_state_dict(
                checkpoint[
                    "optimizer_state_dict"
                ]
            )

            scheduler.load_state_dict(
                checkpoint[
                    "scheduler_state_dict"
                ]
            )

            start_epoch = (
                int(checkpoint["epoch"]) + 1
            )

            best_validation_macro_f1 = float(
                checkpoint[
                    "best_validation_macro_f1"
                ]
            )

            best_validation_loss = float(
                checkpoint[
                    "best_validation_loss"
                ]
            )

            epochs_without_improvement = int(
                checkpoint[
                    "epochs_without_improvement"
                ]
            )

            history = list(
                checkpoint.get(
                    "history",
                    [],
                )
            )

        experiment_metadata = {
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "architecture": (
                "OperationAwareTemporalMobileNetV3Small"
            ),
            "dataset_dir": str(
                dataset_dir
            ),
            "manifest_path": str(
                MANIFEST_PATH
            ),
            "operation_mapping_path": str(
                OPERATION_MAPPING_PATH
            ),
            "config": config,
            "class_names": list(
                CLASS_NAMES
            ),
            "class_to_index": {
                class_name: index
                for index, class_name
                in enumerate(CLASS_NAMES)
            },
            "operation_names": list(
                operation_names
            ),
            "operation_to_index": (
                train_dataset.operation_to_index
            ),
            "train_clip_counts": (
                train_dataset.class_counts
            ),
            "validation_clip_counts": (
                validation_dataset.class_counts
            ),
            "train_operation_counts": (
                train_dataset.operation_counts
            ),
            "validation_operation_counts": (
                validation_dataset.operation_counts
            ),
            "train_video_count": len(
                train_dataset.source_videos
            ),
            "validation_video_count": len(
                validation_dataset.source_videos
            ),
            "device": str(
                device
            ),
            "python_version": (
                platform.python_version()
            ),
            "pytorch_version": (
                torch.__version__
            ),
            "torchvision_version": (
                torchvision.__version__
            ),
        }

        write_json(
            OUTPUT_DIR
            / "experiment_config.json",
            experiment_metadata,
        )

        write_json(
            OUTPUT_DIR
            / "label_mapping.json",
            {
                "class_to_index": {
                    class_name: index
                    for index, class_name
                    in enumerate(CLASS_NAMES)
                },
                "index_to_class": list(
                    CLASS_NAMES
                ),
            },
        )

        write_json(
            OUTPUT_DIR
            / "operation_mapping.json",
            {
                "operation_to_index": (
                    train_dataset.operation_to_index
                ),
                "index_to_operation": list(
                    operation_names
                ),
            },
        )

        print(
            json.dumps(
                experiment_metadata,
                indent=2,
            )
        )

        for epoch in range(
            start_epoch,
            int(config["epochs"]) + 1,
        ):
            epoch_start = time.monotonic()

            (
                train_loss,
                train_metrics,
                train_operation_metrics,
            ) = run_epoch(
                model=model,
                loader=train_loader,
                criterion=criterion,
                device=device,
                optimizer=optimizer,
                scaler=scaler,
                operation_names=(
                    operation_names
                ),
            )

            (
                validation_loss,
                validation_metrics,
                validation_operation_metrics,
            ) = run_epoch(
                model=model,
                loader=validation_loader,
                criterion=criterion,
                device=device,
                optimizer=None,
                scaler=scaler,
                operation_names=(
                    operation_names
                ),
            )

            epoch_result = {
                "epoch": epoch,
                "train_loss": train_loss,
                "train_accuracy": (
                    train_metrics["accuracy"]
                ),
                "train_macro_f1": (
                    train_metrics["macro_f1"]
                ),
                "validation_loss": (
                    validation_loss
                ),
                "validation_accuracy": (
                    validation_metrics[
                        "accuracy"
                    ]
                ),
                "validation_macro_f1": (
                    validation_metrics[
                        "macro_f1"
                    ]
                ),
                "backbone_learning_rate": (
                    optimizer.param_groups[0][
                        "lr"
                    ]
                ),
                "classifier_learning_rate": (
                    optimizer.param_groups[1][
                        "lr"
                    ]
                ),
                "elapsed_sec": (
                    time.monotonic()
                    - epoch_start
                ),
            }

            history.append(
                epoch_result
            )

            scheduler.step()

            macro_f1_improved = (
                validation_metrics[
                    "macro_f1"
                ]
                > best_validation_macro_f1
                + 1e-8
            )

            tied_with_lower_loss = (
                abs(
                    validation_metrics[
                        "macro_f1"
                    ]
                    - best_validation_macro_f1
                )
                <= 1e-8
                and validation_loss
                < best_validation_loss
            )

            if (
                macro_f1_improved
                or tied_with_lower_loss
            ):
                best_validation_macro_f1 = (
                    validation_metrics[
                        "macro_f1"
                    ]
                )

                best_validation_loss = (
                    validation_loss
                )

                epochs_without_improvement = 0
                is_best = True

            else:
                epochs_without_improvement += 1
                is_best = False

            checkpoint_payload = {
                "architecture": (
                    "OperationAwareTemporalMobileNetV3Small"
                ),
                "epoch": epoch,
                "model_state_dict": (
                    model.state_dict()
                ),
                "optimizer_state_dict": (
                    optimizer.state_dict()
                ),
                "scheduler_state_dict": (
                    scheduler.state_dict()
                ),
                "best_validation_macro_f1": (
                    best_validation_macro_f1
                ),
                "best_validation_loss": (
                    best_validation_loss
                ),
                "epochs_without_improvement": (
                    epochs_without_improvement
                ),
                "history": history,
                "class_names": list(
                    CLASS_NAMES
                ),
                "operation_names": list(
                    operation_names
                ),
                "operation_to_index": (
                    train_dataset.operation_to_index
                ),
                "config": config,
                "validation_metrics": {
                    "overall": (
                        validation_metrics
                    ),
                    "by_operation": (
                        validation_operation_metrics
                    ),
                },
            }

            save_checkpoint(
                OUTPUT_DIR
                / "last_model.pt",
                checkpoint_payload,
            )

            if is_best:
                save_checkpoint(
                    OUTPUT_DIR
                    / "best_model.pt",
                    checkpoint_payload,
                )

                write_json(
                    OUTPUT_DIR
                    / "best_validation_metrics.json",
                    {
                        "epoch": epoch,
                        "validation_loss": (
                            validation_loss
                        ),
                        "overall": (
                            validation_metrics
                        ),
                        "by_operation": (
                            validation_operation_metrics
                        ),
                    },
                )

            write_training_history(
                OUTPUT_DIR
                / "training_history.csv",
                history,
            )

            print(
                f"Epoch {epoch:02d} | "
                f"train loss {train_loss:.4f}, "
                f"macro-F1 "
                f"{train_metrics['macro_f1']:.4f} | "
                f"validation loss "
                f"{validation_loss:.4f}, "
                f"macro-F1 "
                f"{validation_metrics['macro_f1']:.4f}"
            )

            for operation_name in operation_names:
                operation_result = (
                    validation_operation_metrics[
                        operation_name
                    ]
                )

                print(
                    f"  {operation_name}: "
                    f"accuracy "
                    f"{operation_result['accuracy']:.4f}, "
                    f"macro-F1 "
                    f"{operation_result['macro_f1']:.4f}"
                )

            if (
                epochs_without_improvement
                >= int(
                    config[
                        "early_stopping_patience"
                    ]
                )
            ):
                print(
                    f"Early stopping after "
                    f"{epoch} epochs."
                )

                break

        print()
        print(
            "Best validation macro-F1: "
            f"{best_validation_macro_f1:.4f}"
        )

        print(
            "Best checkpoint: "
            f"{OUTPUT_DIR / 'best_model.pt'}"
        )

        return 0

    except (
        OSError,
        ValueError,
        RuntimeError,
    ) as error:
        print(
            f"Training failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())