from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.dataset import CLASS_NAMES, GarmentClipDataset, assert_no_video_leakage
from src.metrics import classification_metrics
from src.model import TemporalMobileNetV3Small


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/test_evaluation"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="auto")
    return parser.parse_args()


def choose_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def main() -> int:
    args = parse_args()
    device = choose_device(args.device.lower())
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    config = checkpoint["config"]
    if tuple(checkpoint["class_names"]) != CLASS_NAMES:
        raise ValueError("Checkpoint label order does not match the project label mapping")

    train_dataset = GarmentClipDataset(
        args.dataset_dir, "train", config["frames_per_clip"], config["input_size"]
    )
    validation_dataset = GarmentClipDataset(
        args.dataset_dir, "validation", config["frames_per_clip"], config["input_size"]
    )
    test_dataset = GarmentClipDataset(
        args.dataset_dir, "test", config["frames_per_clip"], config["input_size"]
    )
    assert_no_video_leakage(train_dataset, validation_dataset, test_dataset)

    loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.num_workers > 0,
    )
    model = TemporalMobileNetV3Small(num_classes=len(CLASS_NAMES), pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()

    targets: list[torch.Tensor] = []
    predictions: list[torch.Tensor] = []
    prediction_rows: list[dict[str, object]] = []
    with torch.no_grad():
        for clips, batch_targets, metadata in loader:
            logits = model(clips.to(device, non_blocking=True))
            probabilities = logits.softmax(dim=1).cpu()
            batch_predictions = probabilities.argmax(dim=1)
            targets.append(batch_targets)
            predictions.append(batch_predictions)
            for index in range(batch_targets.size(0)):
                target_index = int(batch_targets[index])
                predicted_index = int(batch_predictions[index])
                prediction_rows.append(
                    {
                        "clip_name": metadata["clip_name"][index],
                        "video_name": metadata["video_name"][index],
                        "start_time_sec": float(metadata["start_time_sec"][index]),
                        "end_time_sec": float(metadata["end_time_sec"][index]),
                        "actual_state": CLASS_NAMES[target_index],
                        "predicted_state": CLASS_NAMES[predicted_index],
                        "probability_idle_setup": float(probabilities[index, 0]),
                        "probability_sewing": float(probabilities[index, 1]),
                        "correct": target_index == predicted_index,
                    }
                )

    metrics = classification_metrics(
        torch.cat(targets), torch.cat(predictions), CLASS_NAMES
    )
    report = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(args.checkpoint.expanduser().resolve()),
        "checkpoint_epoch": checkpoint["epoch"],
        "best_validation_macro_f1": checkpoint["best_validation_macro_f1"],
        "test_video_count": len(test_dataset.source_videos),
        "test_clip_counts": test_dataset.class_counts,
        "metrics": metrics,
    }
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    with (output_dir / "classification_report.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fieldnames = ["class", "precision", "recall", "f1", "support"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for name in CLASS_NAMES:
            writer.writerow({"class": name, **metrics["per_class"][name]})

    with (output_dir / "confusion_matrix.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual/predicted", *CLASS_NAMES])
        for name, row in zip(CLASS_NAMES, metrics["confusion_matrix"], strict=True):
            writer.writerow([name, *row])

    with (output_dir / "test_predictions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(prediction_rows[0]))
        writer.writeheader()
        writer.writerows(prediction_rows)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

