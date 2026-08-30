"""Phase 3B: validation error analysis and READY-threshold tuning.

This program deliberately loads only best_frame_dataset/val. It never opens the
test split. It is compatible with checkpoints produced by train_baseline.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFile
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
)
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from tqdm import tqdm


EXPECTED_CLASSES = {"INVALID", "NOT_READY", "READY"}
DEFAULT_MEAN = [0.485, 0.456, 0.406]
DEFAULT_STD = [0.229, 0.224, 0.225]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze validation errors and tune the READY threshold."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("../best_frame_dataset"),
        help="Dataset root containing val/INVALID, val/NOT_READY and val/READY.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("outputs/baseline_mobilenetv3_gpu/best_model.pt"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/phase3b_validation_analysis"),
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--target-precision", type=float, default=0.90)
    parser.add_argument("--minimum-recall", type=float, default=0.70)
    parser.add_argument("--threshold-min", type=float, default=0.50)
    parser.add_argument("--threshold-max", type=float, default=0.99)
    parser.add_argument("--threshold-step", type=float, default=0.01)
    parser.add_argument(
        "--copy-errors",
        action="store_true",
        help="Copy all selected-threshold errors into review folders.",
    )
    parser.add_argument(
        "--contact-sheet-count",
        type=int,
        default=60,
        help="Maximum images in each false/missed READY contact sheet.",
    )
    parser.add_argument("--no-amp", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.batch_size < 1 or args.workers < 0:
        raise ValueError("batch-size must be positive and workers cannot be negative.")
    if not (0 < args.target_precision <= 1):
        raise ValueError("target-precision must be in (0, 1].")
    if not (0 <= args.minimum_recall <= 1):
        raise ValueError("minimum-recall must be in [0, 1].")
    if not (0 <= args.threshold_min <= args.threshold_max <= 1):
        raise ValueError("Threshold limits must satisfy 0 <= min <= max <= 1.")
    if args.threshold_step <= 0:
        raise ValueError("threshold-step must be positive.")


def load_checkpoint(path: Path, device: torch.device) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {path.resolve()}")
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    required = {"model_state_dict", "class_to_idx", "model_name"}
    missing = required.difference(checkpoint)
    if missing:
        raise ValueError(f"Checkpoint is missing keys: {sorted(missing)}")
    if checkpoint["model_name"] != "mobilenet_v3_small":
        raise ValueError(f"Unsupported model: {checkpoint['model_name']}")
    return checkpoint


def make_dataset(data_dir: Path, checkpoint: dict) -> datasets.ImageFolder:
    val_dir = data_dir / "val"
    if not val_dir.is_dir():
        raise FileNotFoundError(f"Validation folder not found: {val_dir.resolve()}")
    image_size = int(checkpoint.get("image_size", 224))
    normalization = checkpoint.get("normalization", {})
    mean = normalization.get("mean", DEFAULT_MEAN)
    std = normalization.get("std", DEFAULT_STD)
    transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ]
    )
    dataset = datasets.ImageFolder(val_dir, transform=transform)
    if set(dataset.classes) != EXPECTED_CLASSES:
        raise ValueError(
            f"Expected class folders {sorted(EXPECTED_CLASSES)}, found {dataset.classes}"
        )
    if dataset.class_to_idx != checkpoint["class_to_idx"]:
        raise ValueError(
            "Validation class mapping does not match checkpoint: "
            f"dataset={dataset.class_to_idx}, checkpoint={checkpoint['class_to_idx']}"
        )
    return dataset


def build_model(checkpoint: dict, device: torch.device) -> nn.Module:
    class_to_idx = checkpoint["class_to_idx"]
    model = models.mobilenet_v3_small(weights=None)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, len(class_to_idx))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    if device.type == "cuda":
        model.to(memory_format=torch.channels_last)
    model.eval()
    return model


def predict(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    amp_enabled: bool,
) -> tuple[np.ndarray, np.ndarray]:
    probabilities: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    with torch.inference_mode():
        for images, labels in tqdm(loader, desc="Validation inference"):
            images = images.to(
                device,
                non_blocking=True,
                memory_format=(
                    torch.channels_last
                    if device.type == "cuda"
                    else torch.preserve_format
                ),
            )
            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=amp_enabled,
            ):
                logits = model(images)
                batch_probabilities = torch.softmax(logits.float(), dim=1)
            probabilities.append(batch_probabilities.cpu().numpy())
            targets.append(labels.numpy())
    return np.concatenate(targets), np.concatenate(probabilities)


def threshold_metrics(
    targets: np.ndarray,
    ready_probabilities: np.ndarray,
    ready_idx: int,
    threshold: float,
) -> dict:
    actual_ready = targets == ready_idx
    accepted = ready_probabilities >= threshold
    tp = int(np.sum(actual_ready & accepted))
    fp = int(np.sum(~actual_ready & accepted))
    fn = int(np.sum(actual_ready & ~accepted))
    tn = int(np.sum(~actual_ready & ~accepted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "threshold": round(float(threshold), 6),
        "ready_precision": precision,
        "ready_recall": recall,
        "ready_f1": f1,
        "specificity": specificity,
        "false_positive_rate": 1 - specificity,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "accepted_ready_frames": tp + fp,
    }


def make_thresholds(args: argparse.Namespace) -> np.ndarray:
    count = int(math.floor((args.threshold_max - args.threshold_min) / args.threshold_step))
    values = args.threshold_min + np.arange(count + 1) * args.threshold_step
    if values[-1] < args.threshold_max - 1e-9:
        values = np.append(values, args.threshold_max)
    return np.round(values, 10)


def select_threshold(rows: list[dict], target_precision: float, min_recall: float):
    strict = [
        row
        for row in rows
        if row["accepted_ready_frames"] > 0
        and row["ready_precision"] >= target_precision
        and row["ready_recall"] >= min_recall
    ]
    if strict:
        selected = max(
            strict,
            key=lambda row: (
                row["ready_recall"],
                row["ready_f1"],
                row["ready_precision"],
                -row["threshold"],
            ),
        )
        return selected, True, "precision_and_recall_gate_met"

    precision_only = [
        row
        for row in rows
        if row["accepted_ready_frames"] > 0
        and row["ready_precision"] >= target_precision
    ]
    if precision_only:
        selected = max(
            precision_only,
            key=lambda row: (row["ready_recall"], row["ready_f1"], -row["threshold"]),
        )
        return selected, False, "precision_met_but_minimum_recall_not_met"

    selected = max(
        rows,
        key=lambda row: (
            row["ready_f1"],
            row["ready_precision"],
            row["ready_recall"],
            -row["threshold"],
        ),
    )
    return selected, False, "target_precision_not_met_best_f1_fallback"


def thresholded_predictions(
    probabilities: np.ndarray, ready_idx: int, threshold: float
) -> np.ndarray:
    result = np.empty(len(probabilities), dtype=np.int64)
    non_ready_indices = [i for i in range(probabilities.shape[1]) if i != ready_idx]
    non_ready_probabilities = probabilities[:, non_ready_indices]
    non_ready_choice = np.argmax(non_ready_probabilities, axis=1)
    fallback = np.asarray(non_ready_indices)[non_ready_choice]
    result[:] = fallback
    result[probabilities[:, ready_idx] >= threshold] = ready_idx
    return result


def parse_video_id(frame_id: str) -> str:
    return frame_id.split("_", 1)[0] if "_" in frame_id else "UNKNOWN"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_threshold_sweep(rows: list[dict], selected_threshold: float, path: Path):
    thresholds = [row["threshold"] for row in rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(thresholds, [row["ready_precision"] for row in rows], label="READY precision")
    ax.plot(thresholds, [row["ready_recall"] for row in rows], label="READY recall")
    ax.plot(thresholds, [row["ready_f1"] for row in rows], label="READY F1")
    ax.axvline(selected_threshold, color="black", linestyle="--", label=f"Selected {selected_threshold:.2f}")
    ax.set(xlabel="READY threshold", ylabel="Metric", ylim=(0, 1.02), title="Validation READY threshold sweep")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def plot_pr_curve(targets, ready_probabilities, ready_idx, selected, path: Path):
    binary_targets = (targets == ready_idx).astype(np.int32)
    precision, recall, _ = precision_recall_curve(binary_targets, ready_probabilities)
    average_precision = average_precision_score(binary_targets, ready_probabilities)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(recall, precision, label=f"Average precision = {average_precision:.3f}")
    ax.scatter([selected["ready_recall"]], [selected["ready_precision"]], color="red", zorder=3, label="Selected threshold")
    ax.set(xlabel="READY recall", ylabel="READY precision", xlim=(0, 1.02), ylim=(0, 1.02), title="Validation READY precision-recall curve")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return float(average_precision)


def plot_matrix(matrix: np.ndarray, labels: list[str], title: str, path: Path):
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax)
    ax.set(
        xticks=np.arange(len(labels)),
        yticks=np.arange(len(labels)),
        xticklabels=labels,
        yticklabels=labels,
        xlabel="Predicted",
        ylabel="Actual",
        title=title,
    )
    threshold = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            ax.text(
                column,
                row,
                str(matrix[row, column]),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
            )
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def make_contact_sheet(rows: list[dict], path: Path, title: str, limit: int):
    if not rows or limit <= 0:
        return
    chosen = rows[:limit]
    columns = 5
    cell_width, cell_height = 240, 210
    rows_count = math.ceil(len(chosen) / columns)
    sheet = Image.new("RGB", (columns * cell_width, 45 + rows_count * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 12), title, fill="black")
    for index, row in enumerate(chosen):
        image = Image.open(row["image_path"]).convert("RGB")
        image.thumbnail((cell_width - 12, 150))
        x = (index % columns) * cell_width + (cell_width - image.width) // 2
        y = 45 + (index // columns) * cell_height
        sheet.paste(image, (x, y))
        text_y = y + 154
        caption = (
            f"{row['frame_id']}\n"
            f"actual={row['actual_state']} pred={row['thresholded_state']}\n"
            f"p_ready={float(row['p_ready']):.3f}"
        )
        draw.multiline_text((index % columns * cell_width + 5, text_y), caption, fill="black", spacing=2)
    sheet.save(path, quality=92)


def copy_error_images(rows: list[dict], root: Path) -> None:
    for row in rows:
        error_type = row["error_type"]
        actual = row["actual_state"]
        predicted = row["thresholded_state"]
        destination = root / error_type / f"actual_{actual}__pred_{predicted}"
        destination.mkdir(parents=True, exist_ok=True)
        source = Path(row["image_path"])
        shutil.copy2(source, destination / source.name)


def main() -> int:
    args = parse_args()
    validate_args(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ImageFile.LOAD_TRUNCATED_IMAGES = False

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp_enabled = device.type == "cuda" and not args.no_amp
    if device.type == "cuda":
        torch.set_float32_matmul_precision("high")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Automatic mixed precision: {'enabled' if amp_enabled else 'disabled'}")

    checkpoint = load_checkpoint(args.checkpoint, device)
    dataset = make_dataset(args.data_dir, checkpoint)
    model = build_model(checkpoint, device)
    loader_kwargs = {
        "batch_size": args.batch_size,
        "shuffle": False,
        "num_workers": args.workers,
        "pin_memory": device.type == "cuda",
        "persistent_workers": args.workers > 0,
    }
    if args.workers > 0:
        loader_kwargs["prefetch_factor"] = 2
    loader = DataLoader(dataset, **loader_kwargs)
    print(f"Validation images: {len(dataset):,}")
    print(f"Class mapping: {dataset.class_to_idx}")

    targets, probabilities = predict(model, loader, device, amp_enabled)
    classes = dataset.classes
    idx_to_class = {index: name for name, index in dataset.class_to_idx.items()}
    ready_idx = dataset.class_to_idx["READY"]
    argmax_predictions = probabilities.argmax(axis=1)

    thresholds = make_thresholds(args)
    sweep_rows = [
        threshold_metrics(targets, probabilities[:, ready_idx], ready_idx, threshold)
        for threshold in thresholds
    ]
    selected, gate_pass, selection_reason = select_threshold(
        sweep_rows, args.target_precision, args.minimum_recall
    )
    selected_threshold = float(selected["threshold"])
    selected_predictions = thresholded_predictions(
        probabilities, ready_idx, selected_threshold
    )

    prediction_rows: list[dict] = []
    error_rows: list[dict] = []
    false_ready_rows: list[dict] = []
    missed_ready_rows: list[dict] = []
    for index, (image_path, _) in enumerate(dataset.samples):
        frame_id = Path(image_path).stem
        actual_state = idx_to_class[int(targets[index])]
        argmax_state = idx_to_class[int(argmax_predictions[index])]
        thresholded_state = idx_to_class[int(selected_predictions[index])]
        error_type = "CORRECT"
        if thresholded_state == "READY" and actual_state != "READY":
            error_type = "FALSE_READY"
        elif actual_state == "READY" and thresholded_state != "READY":
            error_type = "MISSED_READY"
        elif thresholded_state != actual_state:
            error_type = "NON_READY_CONFUSION"
        row = {
            "video_id": parse_video_id(frame_id),
            "frame_id": frame_id,
            "image_path": str(Path(image_path).resolve()),
            "actual_state": actual_state,
            "argmax_state": argmax_state,
            "thresholded_state": thresholded_state,
            "error_type": error_type,
            "p_invalid": round(float(probabilities[index, dataset.class_to_idx["INVALID"]]), 8),
            "p_not_ready": round(float(probabilities[index, dataset.class_to_idx["NOT_READY"]]), 8),
            "p_ready": round(float(probabilities[index, ready_idx]), 8),
            "failure_category": "",
            "review_notes": "",
        }
        prediction_rows.append(row)
        if error_type != "CORRECT":
            error_rows.append(row)
        if error_type == "FALSE_READY":
            false_ready_rows.append(row)
        elif error_type == "MISSED_READY":
            missed_ready_rows.append(row)

    false_ready_rows.sort(key=lambda row: float(row["p_ready"]), reverse=True)
    missed_ready_rows.sort(key=lambda row: float(row["p_ready"]))
    error_rows.sort(key=lambda row: (row["error_type"], -float(row["p_ready"])))

    prediction_fields = list(prediction_rows[0].keys())
    write_csv(args.output_dir / "validation_predictions.csv", prediction_fields, prediction_rows)
    write_csv(args.output_dir / "validation_errors.csv", prediction_fields, error_rows)
    write_csv(args.output_dir / "false_ready_errors.csv", prediction_fields, false_ready_rows)
    write_csv(args.output_dir / "missed_ready_errors.csv", prediction_fields, missed_ready_rows)
    write_csv(args.output_dir / "threshold_sweep.csv", list(sweep_rows[0].keys()), sweep_rows)

    by_video = defaultdict(Counter)
    for row in prediction_rows:
        by_video[row["video_id"]]["frames"] += 1
        by_video[row["video_id"]][row["error_type"]] += 1
    video_rows = []
    for video_id in sorted(by_video):
        counts = by_video[video_id]
        video_rows.append(
            {
                "video_id": video_id,
                "frames": counts["frames"],
                "false_ready": counts["FALSE_READY"],
                "missed_ready": counts["MISSED_READY"],
                "non_ready_confusion": counts["NON_READY_CONFUSION"],
                "total_errors": counts["FALSE_READY"] + counts["MISSED_READY"] + counts["NON_READY_CONFUSION"],
            }
        )
    write_csv(
        args.output_dir / "errors_by_video.csv",
        ["video_id", "frames", "false_ready", "missed_ready", "non_ready_confusion", "total_errors"],
        video_rows,
    )

    argmax_report = classification_report(
        targets, argmax_predictions, target_names=classes, output_dict=True, zero_division=0
    )
    thresholded_report = classification_report(
        targets, selected_predictions, target_names=classes, output_dict=True, zero_division=0
    )
    argmax_matrix = confusion_matrix(targets, argmax_predictions, labels=range(len(classes)))
    thresholded_matrix = confusion_matrix(targets, selected_predictions, labels=range(len(classes)))
    np.savetxt(args.output_dir / "argmax_confusion_matrix.csv", argmax_matrix, fmt="%d", delimiter=",")
    np.savetxt(args.output_dir / "thresholded_confusion_matrix.csv", thresholded_matrix, fmt="%d", delimiter=",")
    plot_matrix(argmax_matrix, classes, "Validation confusion matrix: argmax", args.output_dir / "argmax_confusion_matrix.png")
    plot_matrix(thresholded_matrix, classes, f"Validation confusion matrix: READY threshold {selected_threshold:.2f}", args.output_dir / "thresholded_confusion_matrix.png")
    plot_threshold_sweep(sweep_rows, selected_threshold, args.output_dir / "threshold_sweep.png")
    average_precision = plot_pr_curve(
        targets,
        probabilities[:, ready_idx],
        ready_idx,
        selected,
        args.output_dir / "ready_precision_recall_curve.png",
    )
    make_contact_sheet(
        false_ready_rows,
        args.output_dir / "false_ready_contact_sheet.jpg",
        "Highest-confidence false READY validation frames",
        args.contact_sheet_count,
    )
    make_contact_sheet(
        missed_ready_rows,
        args.output_dir / "missed_ready_contact_sheet.jpg",
        "Lowest-confidence missed READY validation frames",
        args.contact_sheet_count,
    )
    if args.copy_errors:
        copy_error_images(error_rows, args.output_dir / "error_images")

    result = {
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_best_epoch": checkpoint.get("best_epoch"),
        "checkpoint_best_validation_macro_f1": checkpoint.get("best_val_macro_f1"),
        "device": str(device),
        "validation_images": len(dataset),
        "class_to_idx": dataset.class_to_idx,
        "test_split_used": False,
        "selection_rule": "Accept READY when p_ready >= threshold; otherwise choose max(INVALID, NOT_READY).",
        "target_ready_precision": args.target_precision,
        "minimum_ready_recall": args.minimum_recall,
        "selected_threshold": selected_threshold,
        "gate_pass": gate_pass,
        "selection_reason": selection_reason,
        "selected_threshold_metrics": selected,
        "ready_average_precision": average_precision,
        "argmax_ready_metrics": argmax_report["READY"],
        "thresholded_ready_metrics": thresholded_report["READY"],
        "argmax_macro_f1": argmax_report["macro avg"]["f1-score"],
        "thresholded_macro_f1": thresholded_report["macro avg"]["f1-score"],
        "error_counts_at_selected_threshold": dict(Counter(row["error_type"] for row in prediction_rows)),
        "next_action": (
            "Proceed to Phase 4 temporal selector tuning on validation videos."
            if gate_pass
            else "Do not proceed yet; inspect errors and consider tempered class-weight retraining."
        ),
    }
    with (args.output_dir / "selected_threshold.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print("\nPhase 3B validation analysis complete")
    print(f"Selected READY threshold: {selected_threshold:.2f}")
    print(f"READY precision: {selected['ready_precision']:.4f}")
    print(f"READY recall: {selected['ready_recall']:.4f}")
    print(f"READY F1: {selected['ready_f1']:.4f}")
    print(f"False READY frames: {selected['false_positive']}")
    print(f"Missed READY frames: {selected['false_negative']}")
    print(f"Phase 3B gate passed: {gate_pass}")
    print(f"Selection reason: {selection_reason}")
    print(f"Outputs: {args.output_dir.resolve()}")
    print("The test split was not used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())