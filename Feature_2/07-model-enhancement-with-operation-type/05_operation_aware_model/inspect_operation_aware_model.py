from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import torch
import torchvision

from src.operation_aware_model import (
    OperationAwareTemporalMobileNetV3Small,
    build_optimizer,
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent

REPORT_PATH = (
    SCRIPT_DIR
    / "reports"
    / "phase5_summary.json"
)


# ---------------------------------------------------------
# Model configuration
# ---------------------------------------------------------

SEED = 42
BATCH_SIZE = 2
FRAMES_PER_CLIP = 8
CHANNELS = 3
INPUT_SIZE = 224

NUM_CLASSES = 2
NUM_OPERATIONS = 3

BACKBONE_LEARNING_RATE = 0.0001
CLASSIFIER_LEARNING_RATE = 0.0003
WEIGHT_DECAY = 0.0001


# ---------------------------------------------------------
# Helpers
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


def count_parameters(
    parameters: Any,
) -> int:
    """
    Count the number of values in model parameters.
    """

    return sum(
        parameter.numel()
        for parameter in parameters
    )


# ---------------------------------------------------------
# Model inspection
# ---------------------------------------------------------

def main() -> int:
    try:
        torch.manual_seed(SEED)

        # pretrained=False prevents downloading weights
        # during this architecture-only inspection.
        model = (
            OperationAwareTemporalMobileNetV3Small(
                num_classes=NUM_CLASSES,
                num_operations=NUM_OPERATIONS,
                pretrained=False,
            )
        )

        model.eval()

        dummy_clips = torch.randn(
            BATCH_SIZE,
            FRAMES_PER_CLIP,
            CHANNELS,
            INPUT_SIZE,
            INPUT_SIZE,
            dtype=torch.float32,
        )

        dummy_operations = torch.tensor(
            [0, 2],
            dtype=torch.int64,
        )

        with torch.no_grad():
            logits = model(
                dummy_clips,
                dummy_operations,
            )

        expected_output_shape = (
            BATCH_SIZE,
            NUM_CLASSES,
        )

        if tuple(logits.shape) != expected_output_shape:
            raise ValueError(
                "Unexpected output shape. "
                f"Expected {expected_output_shape}, "
                f"found {tuple(logits.shape)}."
            )

        if model.visual_feature_dim != 576:
            raise ValueError(
                "Expected MobileNetV3-Small to "
                "produce 576 visual features."
            )

        if model.operation_feature_dim != 3:
            raise ValueError(
                "Expected three operation features."
            )

        if model.combined_feature_dim != 579:
            raise ValueError(
                "Expected 579 combined features."
            )

        first_classifier_layer = (
            model.classifier[0]
        )

        last_classifier_layer = (
            model.classifier[3]
        )

        if first_classifier_layer.in_features != 579:
            raise ValueError(
                "First classifier layer must "
                "accept 579 features."
            )

        if first_classifier_layer.out_features != 1024:
            raise ValueError(
                "First classifier layer must "
                "produce 1024 features."
            )

        if last_classifier_layer.in_features != 1024:
            raise ValueError(
                "Final classifier layer must "
                "accept 1024 features."
            )

        if last_classifier_layer.out_features != 2:
            raise ValueError(
                "Final classifier layer must "
                "produce two state logits."
            )

        # Confirm that operation input affects the output.
        repeated_clip = dummy_clips[0:1].repeat(
            NUM_OPERATIONS,
            1,
            1,
            1,
            1,
        )

        all_operation_indices = torch.tensor(
            [0, 1, 2],
            dtype=torch.int64,
        )

        with torch.no_grad():
            operation_logits = model(
                repeated_clip,
                all_operation_indices,
            )

        operation_difference = float(
            (
                operation_logits[0]
                - operation_logits[1]
            )
            .abs()
            .max()
            .item()
        )

        operation_difference = max(
            operation_difference,
            float(
                (
                    operation_logits[0]
                    - operation_logits[2]
                )
                .abs()
                .max()
                .item()
            ),
        )

        if operation_difference <= 0:
            raise ValueError(
                "Changing the operation did not "
                "change the model output."
            )

        # Confirm invalid operation IDs are rejected.
        invalid_operation_rejected = False

        try:
            model(
                dummy_clips,
                torch.tensor(
                    [0, 3],
                    dtype=torch.int64,
                ),
            )

        except ValueError:
            invalid_operation_rejected = True

        if not invalid_operation_rejected:
            raise ValueError(
                "The model accepted an invalid "
                "operation index."
            )

        optimizer = build_optimizer(
            model=model,
            backbone_learning_rate=(
                BACKBONE_LEARNING_RATE
            ),
            classifier_learning_rate=(
                CLASSIFIER_LEARNING_RATE
            ),
            weight_decay=WEIGHT_DECAY,
        )

        if len(optimizer.param_groups) != 2:
            raise ValueError(
                "Optimizer must contain two "
                "parameter groups."
            )

        backbone_lr = optimizer.param_groups[0][
            "lr"
        ]

        classifier_lr = optimizer.param_groups[1][
            "lr"
        ]

        if backbone_lr != BACKBONE_LEARNING_RATE:
            raise ValueError(
                "Incorrect backbone learning rate."
            )

        if (
            classifier_lr
            != CLASSIFIER_LEARNING_RATE
        ):
            raise ValueError(
                "Incorrect classifier learning rate."
            )

        total_parameters = count_parameters(
            model.parameters()
        )

        trainable_parameters = count_parameters(
            parameter
            for parameter in model.parameters()
            if parameter.requires_grad
        )

        backbone_parameters = count_parameters(
            model.features.parameters()
        )

        classifier_parameters = count_parameters(
            model.classifier.parameters()
        )

        summary = {
            "status": "PASS",
            "architecture": (
                "OperationAwareTemporalMobileNetV3Small"
            ),
            "configuration": {
                "seed": SEED,
                "frames_per_clip": FRAMES_PER_CLIP,
                "input_size": INPUT_SIZE,
                "num_classes": NUM_CLASSES,
                "num_operations": NUM_OPERATIONS,
                "visual_feature_dim": (
                    model.visual_feature_dim
                ),
                "operation_feature_dim": (
                    model.operation_feature_dim
                ),
                "combined_feature_dim": (
                    model.combined_feature_dim
                ),
                "classifier_hidden_dim": 1024,
                "dropout": 0.20,
                "operation_encoding": "one_hot",
                "operation_fusion": (
                    "concatenation"
                ),
                "temporal_aggregation": (
                    "mean_pooling"
                ),
            },
            "classifier_contract": {
                "first_layer": "579 -> 1024",
                "activation": "Hardswish",
                "dropout": 0.20,
                "final_layer": "1024 -> 2",
            },
            "forward_test": {
                "input_clip_shape": list(
                    dummy_clips.shape
                ),
                "operation_input_shape": list(
                    dummy_operations.shape
                ),
                "output_shape": list(
                    logits.shape
                ),
                "output_dtype": str(
                    logits.dtype
                ),
                "operation_changes_output": True,
                "maximum_operation_difference": (
                    operation_difference
                ),
                "invalid_operation_rejected": (
                    invalid_operation_rejected
                ),
            },
            "optimizer": {
                "name": "AdamW",
                "parameter_group_count": len(
                    optimizer.param_groups
                ),
                "backbone_learning_rate": (
                    backbone_lr
                ),
                "classifier_learning_rate": (
                    classifier_lr
                ),
                "weight_decay": WEIGHT_DECAY,
            },
            "parameters": {
                "total": total_parameters,
                "trainable": trainable_parameters,
                "backbone": backbone_parameters,
                "classifier": classifier_parameters,
            },
            "environment": {
                "python_version": (
                    platform.python_version()
                ),
                "pytorch_version": torch.__version__,
                "torchvision_version": (
                    torchvision.__version__
                ),
            },
            "checks": {
                "visual_feature_dimension": "PASS",
                "operation_feature_dimension": "PASS",
                "combined_feature_dimension": "PASS",
                "classifier_contract": "PASS",
                "forward_output_shape": "PASS",
                "operation_affects_output": "PASS",
                "invalid_operation_rejected": "PASS",
                "optimizer_parameter_groups": "PASS",
            },
        }

        write_json(
            REPORT_PATH,
            summary,
        )

        print(
            "Phase 5 model inspection "
            "completed successfully."
        )

        print()
        print(
            "Architecture: "
            "OperationAwareTemporalMobileNetV3Small"
        )

        print(
            "Visual features: "
            f"{model.visual_feature_dim}"
        )

        print(
            "Operation features: "
            f"{model.operation_feature_dim}"
        )

        print(
            "Combined features: "
            f"{model.combined_feature_dim}"
        )

        print(
            "Classifier: 579 -> 1024 -> 2"
        )

        print(
            f"Output shape: {list(logits.shape)}"
        )

        print(
            f"Total parameters: {total_parameters:,}"
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
            f"Phase 5 failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())