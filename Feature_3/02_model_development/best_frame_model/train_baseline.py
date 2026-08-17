from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import ImageFile
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from torchvision.models import MobileNet_V3_Small_Weights
from tqdm import tqdm


EXPECTED_CLASSES = {"INVALID", "NOT_READY", "READY"}
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("../best_frame_dataset"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/baseline_mobilenetv3"))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--freeze-epochs", type=int, default=5)
    parser.add_argument("--head-lr", type=float, default=1e-3)
    parser.add_argument("--backbone-lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-amp",
        action="store_true",
        help="Disable CUDA automatic mixed precision (normally keep AMP enabled).",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Prefer exact reproducibility over maximum GPU performance.",
    )
    return parser.parse_args()


def seed_everything(seed: int, deterministic: bool) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(deterministic, warn_only=True)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.deterministic = deterministic
        torch.backends.cudnn.benchmark = not deterministic


def seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def build_datasets(data_dir: Path):
    train_dir = data_dir / "train"
    val_dir = data_dir / "val"
    if not train_dir.is_dir() or not val_dir.is_dir():
        raise FileNotFoundError(
            f"Expected train and val folders under: {data_dir.resolve()}"
        )

    train_transform = transforms.Compose(
        [
            transforms.Resize((240, 240)),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomAffine(
                degrees=8,
                translate=(0.04, 0.04),
                scale=(0.95, 1.05),
                fill=0,
            ),
            transforms.ColorJitter(brightness=0.15, contrast=0.15),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )

    train_dataset = datasets.ImageFolder(train_dir, transform=train_transform)
    val_dataset = datasets.ImageFolder(val_dir, transform=eval_transform)

    if set(train_dataset.classes) != EXPECTED_CLASSES:
        raise ValueError(
            f"Expected class folders {sorted(EXPECTED_CLASSES)}, "
            f"found {train_dataset.classes}"
        )
    if train_dataset.class_to_idx != val_dataset.class_to_idx:
        raise ValueError("Train and validation class mappings are different.")
    return train_dataset, val_dataset


def class_counts_and_weights(dataset: datasets.ImageFolder):
    targets = np.asarray(dataset.targets)
    counts = np.bincount(targets, minlength=len(dataset.classes))
    if np.any(counts == 0):
        raise ValueError(f"At least one training class is empty: {counts.tolist()}")
    weights = len(dataset) / (len(dataset.classes) * counts.astype(np.float64))
    return counts, torch.tensor(weights, dtype=torch.float32)


def make_loaders(train_dataset, val_dataset, args, device):
    generator = torch.Generator().manual_seed(args.seed)
    common = {
        "batch_size": args.batch_size,
        "num_workers": args.workers,
        "pin_memory": device.type == "cuda",
        "persistent_workers": args.workers > 0,
        "worker_init_fn": seed_worker,
        "generator": generator,
    }
    if args.workers > 0:
        common["prefetch_factor"] = 2
    train_loader = DataLoader(train_dataset, shuffle=True, **common)
    val_loader = DataLoader(val_dataset, shuffle=False, **common)
    return train_loader, val_loader


def build_model(num_classes: int, freeze_backbone: bool):
    model = models.mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    for parameter in model.features.parameters():
        parameter.requires_grad = not freeze_backbone
    return model


def run_epoch(
    model,
    loader,
    criterion,
    device,
    amp_enabled,
    scaler=None,
    optimizer=None,
):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    predictions: list[int] = []
    targets: list[int] = []

    context = torch.enable_grad() if training else torch.inference_mode()
    with context:
        progress = tqdm(loader, desc="train" if training else "val", leave=False)
        for images, labels in progress:
            images = images.to(
                device,
                non_blocking=True,
                memory_format=(
                    torch.channels_last
                    if device.type == "cuda"
                    else torch.preserve_format
                ),
            )
            labels = labels.to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=amp_enabled,
            ):
                logits = model(images)
                loss = criterion(logits, labels)
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

            total_loss += loss.item() * images.size(0)
            batch_predictions = logits.argmax(dim=1)
            predictions.extend(batch_predictions.cpu().tolist())
            targets.extend(labels.cpu().tolist())
            progress.set_postfix(loss=f"{loss.item():.4f}")

    average_loss = total_loss / len(loader.dataset)
    accuracy = float(np.mean(np.asarray(predictions) == np.asarray(targets)))
    macro_f1 = f1_score(targets, predictions, average="macro", zero_division=0)
    return average_loss, accuracy, macro_f1, targets, predictions


def write_history(path: Path, history: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)


def plot_history(history: list[dict], output_path: Path) -> None:
    epochs = [row["epoch"] for row in history]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(epochs, [row["train_loss"] for row in history], label="train")
    axes[0].plot(epochs, [row["val_loss"] for row in history], label="validation")
    axes[0].set(title="Loss", xlabel="Epoch", ylabel="Loss")
    axes[0].legend()
    axes[1].plot(epochs, [row["train_macro_f1"] for row in history], label="train")
    axes[1].plot(epochs, [row["val_macro_f1"] for row in history], label="validation")
    axes[1].set(title="Macro F1", xlabel="Epoch", ylabel="F1", ylim=(0, 1))
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_confusion_matrix(matrix, classes, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax)
    ax.set(
        xticks=np.arange(len(classes)),
        yticks=np.arange(len(classes)),
        xticklabels=classes,
        yticklabels=classes,
        xlabel="Predicted",
        ylabel="Actual",
        title="Best-checkpoint validation confusion matrix",
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
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    if args.epochs < 1 or args.patience < 1 or args.batch_size < 1:
        raise ValueError("epochs, patience, and batch-size must be positive.")
    if args.workers < 0 or args.freeze_epochs < 0:
        raise ValueError("workers and freeze-epochs cannot be negative.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    seed_everything(args.seed, args.deterministic)
    ImageFile.LOAD_TRUNCATED_IMAGES = False

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    amp_enabled = device.type == "cuda" and not args.no_amp
    if device.type == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        torch.set_float32_matmul_precision("high")
        torch.cuda.reset_peak_memory_stats()
        print(f"GPU: {gpu_name} ({gpu_memory_gb:.1f} GB)")
    else:
        gpu_name = None
        gpu_memory_gb = None
    print(f"Automatic mixed precision: {'enabled' if amp_enabled else 'disabled'}")
    print(f"Batch size: {args.batch_size}; data-loader workers: {args.workers}")
    train_dataset, val_dataset = build_datasets(args.data_dir)
    counts, class_weights = class_counts_and_weights(train_dataset)
    print(f"Class mapping: {train_dataset.class_to_idx}")
    print(f"Training images: {len(train_dataset):,}")
    print(f"Validation images: {len(val_dataset):,}")
    for class_name, count, weight in zip(train_dataset.classes, counts, class_weights):
        print(f"  {class_name}: {count:,} images, loss weight={weight.item():.4f}")

    train_loader, val_loader = make_loaders(
        train_dataset, val_dataset, args, device
    )
    model = build_model(len(train_dataset.classes), args.freeze_epochs > 0).to(device)
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)
    optimizer = AdamW(
        [
            {"params": model.features.parameters(), "lr": args.backbone_lr},
            {"params": model.classifier.parameters(), "lr": args.head_lr},
        ],
        weight_decay=args.weight_decay,
    )
    scheduler = ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=3)

    best_f1 = -1.0
    best_epoch = 0
    stale_epochs = 0
    history: list[dict] = []
    checkpoint_path = args.output_dir / "best_model.pt"
    start_time = time.time()

    for epoch in range(1, args.epochs + 1):
        if args.freeze_epochs > 0 and epoch == args.freeze_epochs + 1:
            for parameter in model.features.parameters():
                parameter.requires_grad = True
            print("Backbone unfrozen for fine-tuning.")

        print(f"\nEpoch {epoch}/{args.epochs}")
        train_loss, train_acc, train_f1, _, _ = run_epoch(
            model,
            train_loader,
            criterion,
            device,
            amp_enabled,
            scaler,
            optimizer,
        )
        val_loss, val_acc, val_f1, _, _ = run_epoch(
            model, val_loader, criterion, device, amp_enabled
        )
        scheduler.step(val_f1)

        row = {
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "train_accuracy": round(train_acc, 6),
            "train_macro_f1": round(train_f1, 6),
            "val_loss": round(val_loss, 6),
            "val_accuracy": round(val_acc, 6),
            "val_macro_f1": round(val_f1, 6),
            "backbone_lr": optimizer.param_groups[0]["lr"],
            "head_lr": optimizer.param_groups[1]["lr"],
        }
        history.append(row)
        write_history(args.output_dir / "training_history.csv", history)
        print(
            f"train loss={train_loss:.4f} acc={train_acc:.4f} macro_f1={train_f1:.4f} | "
            f"val loss={val_loss:.4f} acc={val_acc:.4f} macro_f1={val_f1:.4f}"
        )

        if val_f1 > best_f1 + 1e-4:
            best_f1 = val_f1
            best_epoch = epoch
            stale_epochs = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "class_to_idx": train_dataset.class_to_idx,
                    "model_name": "mobilenet_v3_small",
                    "image_size": 224,
                    "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
                    "best_epoch": best_epoch,
                    "best_val_macro_f1": best_f1,
                    "training_args": vars(args),
                },
                checkpoint_path,
            )
            print(f"Saved new best checkpoint: val macro F1={best_f1:.4f}")
        else:
            stale_epochs += 1
            print(f"No improvement: {stale_epochs}/{args.patience}")
            if stale_epochs >= args.patience:
                print("Early stopping activated.")
                break

    plot_history(history, args.output_dir / "training_curves.png")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    val_loss, val_acc, val_f1, val_targets, val_predictions = run_epoch(
        model, val_loader, criterion, device, amp_enabled
    )
    report = classification_report(
        val_targets,
        val_predictions,
        target_names=train_dataset.classes,
        output_dict=True,
        zero_division=0,
    )
    with (args.output_dir / "validation_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    matrix = confusion_matrix(val_targets, val_predictions)
    np.savetxt(
        args.output_dir / "validation_confusion_matrix.csv",
        matrix,
        fmt="%d",
        delimiter=",",
    )
    plot_confusion_matrix(
        matrix,
        train_dataset.classes,
        args.output_dir / "validation_confusion_matrix.png",
    )

    elapsed_minutes = (time.time() - start_time) / 60
    summary = {
        "device": str(device),
        "gpu_name": gpu_name,
        "gpu_memory_gb": gpu_memory_gb,
        "automatic_mixed_precision": amp_enabled,
        "batch_size": args.batch_size,
        "data_loader_workers": args.workers,
        "best_epoch": best_epoch,
        "best_validation_macro_f1": best_f1,
        "validation_accuracy_at_best": val_acc,
        "validation_loss_at_best": val_loss,
        "elapsed_minutes": elapsed_minutes,
        "train_images": len(train_dataset),
        "validation_images": len(val_dataset),
        "class_to_idx": train_dataset.class_to_idx,
        "test_split_used": False,
    }
    if device.type == "cuda":
        summary["peak_gpu_memory_gb"] = torch.cuda.max_memory_allocated() / (1024**3)
    with (args.output_dir / "run_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    ready_metrics = report["READY"]
    print("\nTraining complete")
    print(f"Best epoch: {best_epoch}")
    print(f"Validation macro F1: {val_f1:.4f}")
    print(f"Validation READY precision: {ready_metrics['precision']:.4f}")
    print(f"Validation READY recall: {ready_metrics['recall']:.4f}")
    print(f"Validation READY F1: {ready_metrics['f1-score']:.4f}")
    print(f"Elapsed time: {elapsed_minutes:.1f} minutes")
    print(f"Outputs: {args.output_dir.resolve()}")
    print("The test split was not used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())