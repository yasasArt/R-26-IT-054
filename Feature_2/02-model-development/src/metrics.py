from __future__ import annotations

from typing import Any

import torch


def classification_metrics(
    targets: torch.Tensor, predictions: torch.Tensor, class_names: tuple[str, ...]
) -> dict[str, Any]:
    targets = targets.to(torch.int64).cpu()
    predictions = predictions.to(torch.int64).cpu()
    number_of_classes = len(class_names)
    matrix = torch.zeros((number_of_classes, number_of_classes), dtype=torch.int64)
    for target, prediction in zip(targets, predictions, strict=True):
        matrix[target, prediction] += 1

    total = int(matrix.sum())
    accuracy = float(matrix.diag().sum() / total) if total else 0.0
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    weighted_f1_sum = 0.0
    for index, name in enumerate(class_names):
        true_positive = int(matrix[index, index])
        false_positive = int(matrix[:, index].sum()) - true_positive
        false_negative = int(matrix[index, :].sum()) - true_positive
        support = int(matrix[index, :].sum())
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        weighted_f1_sum += f1 * support
        per_class[name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    return {
        "accuracy": accuracy,
        "macro_f1": sum(f1_values) / len(f1_values),
        "weighted_f1": weighted_f1_sum / total if total else 0.0,
        "sample_count": total,
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }
