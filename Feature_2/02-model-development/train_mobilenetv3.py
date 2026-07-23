from __future__ import annotations

import argparse
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
from torch import nn
from torch.utils.data import DataLoader

from src.dataset import CLASS_NAMES, GarmentClipDataset, assert_no_video_leakage
from src.metrics import classification_metrics
from src.model import TemporalMobileNetV3Small, build_optimizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/training_config.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/experiment_01"))
    parser.add_argument("--resume", type=Path, help="Resume from a last_model.pt checkpoint")
    parser.add_argument("--no-pretrained", action="store_true", help="Do not load ImageNet weights")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
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
        "device",
    }
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Training config is missing keys: {sorted(missing)}")
    return config


def choose_device(requested: str) -> torch.device:
    requested = requested.lower()
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def class_weights(dataset: GarmentClipDataset, device: torch.device) -> torch.Tensor:
    counts = dataset.class_counts
    total = sum(counts.values())
    weights = [total / (len(CLASS_NAMES) * counts[name]) for name in CLASS_NAMES]
    return torch.tensor(weights, dtype=torch.float32, device=device)


def make_loader(
    dataset: GarmentClipDataset,
    batch_size: int,
    num_workers: int,
    shuffle: bool,
    device: torch.device,
    seed: int,
) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=num_workers > 0,
        worker_init_fn=seed_worker,
        generator=generator,
    )


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    scaler: Any,
) -> tuple[float, dict[str, Any]]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    all_targets: list[torch.Tensor] = []
    all_predictions: list[torch.Tensor] = []
    amp_enabled = device.type == "cuda"

    for clips, targets, _metadata in loader:
        clips = clips.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)

        gradient_context = nullcontext() if training else torch.no_grad()
        with gradient_context:
            with torch.autocast(device_type=device.type, enabled=amp_enabled):
                logits = model(clips)
                loss = criterion(logits, targets)

        if training:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            scaler.step(optimizer)
            scaler.update()

        total_loss += float(loss.detach()) * targets.size(0)
        all_targets.append(targets.detach().cpu())
        all_predictions.append(logits.detach().argmax(dim=1).cpu())

    metrics = classification_metrics(
        torch.cat(all_targets), torch.cat(all_predictions), CLASS_NAMES
    )
    return total_loss / len(loader.dataset), metrics # type: ignore


def save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    seed_everything(int(config["seed"]))
    device = choose_device(str(config["device"]))

    train_dataset = GarmentClipDataset(
        args.dataset_dir, "train", config["frames_per_clip"], config["input_size"]
    )
    validation_dataset = GarmentClipDataset(
        args.dataset_dir, "validation", config["frames_per_clip"], config["input_size"]
    )
    assert_no_video_leakage(train_dataset, validation_dataset)

    train_loader = make_loader(
        train_dataset,
        config["batch_size"],
        config["num_workers"],
        True,
        device,
        config["seed"],
    )
    validation_loader = make_loader(
        validation_dataset,
        config["batch_size"],
        config["num_workers"],
        False,
        device,
        config["seed"],
    )

    model = TemporalMobileNetV3Small(
        num_classes=len(CLASS_NAMES), pretrained=not args.no_pretrained
    ).to(device)
    optimizer = build_optimizer(
        model,
        config["backbone_learning_rate"],
        config["classifier_learning_rate"],
        config["weight_decay"],
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config["epochs"], eta_min=1e-6
    )
    weights = class_weights(train_dataset, device) if config["use_class_weights"] else None
    criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=config["label_smoothing"])
    if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda") # type: ignore
    else:  # Compatibility with older supported PyTorch releases.
        scaler = torch.cuda.amp.GradScaler(enabled=device.type == "cuda")

    start_epoch = 1
    best_macro_f1 = -1.0
    best_validation_loss = float("inf")
    epochs_without_improvement = 0
    history: list[dict[str, Any]] = []
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        if checkpoint["config"] != config:
            raise ValueError(
                "The resume checkpoint configuration differs from the supplied config file"
            )
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        start_epoch = int(checkpoint["epoch"]) + 1
        best_macro_f1 = float(checkpoint["best_validation_macro_f1"])
        best_validation_loss = float(checkpoint["best_validation_loss"])
        epochs_without_improvement = int(checkpoint["epochs_without_improvement"])
        history = list(checkpoint.get("history", []))

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(Path(args.dataset_dir).expanduser().resolve()),
        "config": config,
        "class_names": list(CLASS_NAMES),
        "class_to_index": {name: index for index, name in enumerate(CLASS_NAMES)},
        "train_clip_counts": train_dataset.class_counts,
        "validation_clip_counts": validation_dataset.class_counts,
        "train_video_count": len(train_dataset.source_videos),
        "validation_video_count": len(validation_dataset.source_videos),
        "device": str(device),
        "python_version": platform.python_version(),
        "pytorch_version": torch.__version__,
        "torchvision_version": __import__("torchvision").__version__,
    }
    write_json(output_dir / "experiment_config.json", metadata)
    write_json(
        output_dir / "label_mapping.json",
        {"class_to_index": metadata["class_to_index"], "index_to_class": list(CLASS_NAMES)},
    )

    print(json.dumps(metadata, indent=2))
    for epoch in range(start_epoch, int(config["epochs"]) + 1):
        epoch_start = time.monotonic()
        train_loss, train_metrics = run_epoch(
            model, train_loader, criterion, device, optimizer, scaler
        )
        validation_loss, validation_metrics = run_epoch(
            model, validation_loader, criterion, device, None, scaler
        )
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_accuracy": train_metrics["accuracy"],
            "train_macro_f1": train_metrics["macro_f1"],
            "validation_loss": validation_loss,
            "validation_accuracy": validation_metrics["accuracy"],
            "validation_macro_f1": validation_metrics["macro_f1"],
            "backbone_learning_rate": optimizer.param_groups[0]["lr"],
            "classifier_learning_rate": optimizer.param_groups[1]["lr"],
            "elapsed_sec": time.monotonic() - epoch_start,
        }
        history.append(row)
        scheduler.step()

        improved = validation_metrics["macro_f1"] > best_macro_f1 + 1e-8
        tied_but_lower_loss = (
            abs(validation_metrics["macro_f1"] - best_macro_f1) <= 1e-8
            and validation_loss < best_validation_loss
        )
        if improved or tied_but_lower_loss:
            best_macro_f1 = validation_metrics["macro_f1"]
            best_validation_loss = validation_loss
            epochs_without_improvement = 0
            is_best = True
        else:
            epochs_without_improvement += 1
            is_best = False

        checkpoint_payload = {
            "architecture": "TemporalMobileNetV3Small",
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "best_validation_macro_f1": best_macro_f1,
            "best_validation_loss": best_validation_loss,
            "epochs_without_improvement": epochs_without_improvement,
            "history": history,
            "class_names": list(CLASS_NAMES),
            "config": config,
            "validation_metrics": validation_metrics,
        }
        save_checkpoint(output_dir / "last_model.pt", checkpoint_payload)
        if is_best:
            save_checkpoint(output_dir / "best_model.pt", checkpoint_payload)
            write_json(output_dir / "best_validation_metrics.json", validation_metrics)

        with (output_dir / "training_history.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(history[0]))
            writer.writeheader()
            writer.writerows(history)

        print(
            f"Epoch {epoch:02d} | train loss {train_loss:.4f}, macro-F1 "
            f"{train_metrics['macro_f1']:.4f} | validation loss {validation_loss:.4f}, "
            f"macro-F1 {validation_metrics['macro_f1']:.4f}"
        )
        if epochs_without_improvement >= int(config["early_stopping_patience"]):
            print(f"Early stopping after {epoch} epochs.")
            break

    print(f"Best validation macro-F1: {best_macro_f1:.4f}")
    print(f"Best checkpoint: {output_dir / 'best_model.pt'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Training interrupted. Resume from last_model.pt.", file=sys.stderr)
        raise SystemExit(130)
