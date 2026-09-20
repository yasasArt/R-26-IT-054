from __future__ import annotations

from typing import Any

import torch


def classification_metrics(
    targets: torch.Tensor,
    predictions: torch.Tensor,
    class_names: tuple[str, ...],
) -> dict[str, Any]:
    """
    Calculate overall classification metrics.
    """

    targets = targets.to(
        torch.int64
    ).cpu()

    predictions = predictions.to(
        torch.int64
    ).cpu()

    number_of_classes = len(
        class_names
    )

    confusion_matrix = torch.zeros(
        (
            number_of_classes,
            number_of_classes,
        ),
        dtype=torch.int64,
    )

    for target, prediction in zip(
        targets,
        predictions,
        strict=True,
    ):
        confusion_matrix[
            target,
            prediction,
        ] += 1

    total = int(
        confusion_matrix.sum()
    )

    correct = int(
        confusion_matrix.diag().sum()
    )

    accuracy = (
        correct / total
        if total
        else 0.0
    )

    per_class: dict[
        str,
        dict[str, float | int],
    ] = {}

    f1_values: list[float] = []
    weighted_f1_sum = 0.0

    for index, class_name in enumerate(
        class_names
    ):
        true_positive = int(
            confusion_matrix[index, index]
        )

        false_positive = (
            int(
                confusion_matrix[
                    :,
                    index,
                ].sum()
            )
            - true_positive
        )

        false_negative = (
            int(
                confusion_matrix[
                    index,
                    :,
                ].sum()
            )
            - true_positive
        )

        support = int(
            confusion_matrix[
                index,
                :,
            ].sum()
        )

        precision = (
            true_positive
            / (
                true_positive
                + false_positive
            )
            if (
                true_positive
                + false_positive
            )
            else 0.0
        )

        recall = (
            true_positive
            / (
                true_positive
                + false_negative
            )
            if (
                true_positive
                + false_negative
            )
            else 0.0
        )

        f1 = (
            2
            * precision
            * recall
            / (
                precision
                + recall
            )
            if precision + recall
            else 0.0
        )

        f1_values.append(
            f1
        )

        weighted_f1_sum += (
            f1 * support
        )

        per_class[class_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    return {
        "accuracy": accuracy,
        "macro_f1": (
            sum(f1_values)
            / len(f1_values)
        ),
        "weighted_f1": (
            weighted_f1_sum / total
            if total
            else 0.0
        ),
        "sample_count": total,
        "per_class": per_class,
        "confusion_matrix": (
            confusion_matrix.tolist()
        ),
    }


def classification_metrics_by_operation(
    targets: torch.Tensor,
    predictions: torch.Tensor,
    operation_indices: torch.Tensor,
    class_names: tuple[str, ...],
    operation_names: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """
    Calculate state-classification metrics separately
    for collar, pocket and sleeve clips.
    """

    targets = targets.to(
        torch.int64
    ).cpu()

    predictions = predictions.to(
        torch.int64
    ).cpu()

    operation_indices = operation_indices.to(
        torch.int64
    ).cpu()

    if not (
        len(targets)
        == len(predictions)
        == len(operation_indices)
    ):
        raise ValueError(
            "Targets, predictions and operation "
            "indices must have equal lengths."
        )

    results: dict[
        str,
        dict[str, Any],
    ] = {}

    for operation_index, operation_name in enumerate(
        operation_names
    ):
        operation_mask = (
            operation_indices
            == operation_index
        )

        operation_targets = targets[
            operation_mask
        ]

        operation_predictions = predictions[
            operation_mask
        ]

        results[operation_name] = (
            classification_metrics(
                operation_targets,
                operation_predictions,
                class_names,
            )
        )

    return results