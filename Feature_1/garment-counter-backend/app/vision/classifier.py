from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torchvision import models, transforms


class TemporalMobileNetV3Small(nn.Module):
    """Exact architecture used by the supplied best_model.pt training checkpoint."""

    def __init__(self, num_classes: int = 2) -> None:
        super().__init__()
        backbone = models.mobilenet_v3_small(weights=None)
        self.features = backbone.features
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Sequential(
            nn.Linear(576, 1024),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.3),
            nn.Linear(1024, num_classes),
        )

    def forward(self, clip: torch.Tensor) -> torch.Tensor:
        batch, frames, channels, height, width = clip.shape
        features = self.features(clip.reshape(batch * frames, channels, height, width))
        pooled = self.avgpool(features).flatten(1).reshape(batch, frames, -1).mean(dim=1)
        return self.classifier(pooled)


def resolve_device(preference: str = "auto") -> torch.device:
    if preference != "auto":
        return torch.device(preference)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_label_mapping(mapping_path: Path) -> tuple[str, ...]:
    if not mapping_path.is_file():
        raise FileNotFoundError("The trained classifier label_mapping.json file is missing.")

    mapping: dict[str, Any] = json.loads(mapping_path.read_text(encoding="utf-8"))
    indexed = mapping.get("index_to_class") or mapping.get("idx_to_class")

    if isinstance(indexed, list):
        labels = tuple(str(label) for label in indexed)
    elif isinstance(indexed, dict):
        labels = tuple(str(indexed[str(index)]) for index in range(len(indexed)))
    else:
        classes = mapping.get("class_to_index") or mapping.get("class_to_idx")
        if not isinstance(classes, dict):
            raise ValueError("The classifier label mapping does not contain indexed classes.")
        labels = tuple(label for label, _ in sorted(classes.items(), key=lambda item: item[1]))

    if labels != ("IDLE_SETUP", "SEWING"):
        raise ValueError("The classifier must expose IDLE_SETUP at index 0 and SEWING at index 1.")
    return labels


def _extract_state_dict(checkpoint: Any) -> dict[str, torch.Tensor]:
    if not isinstance(checkpoint, dict):
        raise ValueError("The garment checkpoint does not contain a model state dictionary.")

    state: Any = checkpoint
    for candidate in ("model_state_dict", "state_dict", "model"):
        if isinstance(checkpoint.get(candidate), dict):
            state = checkpoint[candidate]
            break

    if not isinstance(state, dict):
        raise ValueError("The garment checkpoint state dictionary is invalid.")
    return {
        key.removeprefix("module."): value
        for key, value in state.items()
        if isinstance(key, str) and isinstance(value, torch.Tensor)
    }


class GarmentClassifier:
    clip_frames = 8
    input_size = 224

    def __init__(self, checkpoint_path: Path, mapping_path: Path, device: str = "auto") -> None:
        if not checkpoint_path.is_file():
            raise FileNotFoundError("The trained garment checkpoint best_model.pt is missing.")

        self.labels = load_label_mapping(mapping_path)
        self.device = resolve_device(device)
        self.model = TemporalMobileNetV3Small(num_classes=len(self.labels))

        try:
            checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        except TypeError:
            checkpoint = torch.load(checkpoint_path, map_location="cpu")

        self.model.load_state_dict(_extract_state_dict(checkpoint), strict=True)
        self.model.to(self.device).eval()
        self.transform = transforms.Compose(
            [
                transforms.ToPILImage(),
                transforms.Resize((self.input_size, self.input_size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )

    def warmup(self) -> None:
        with torch.inference_mode():
            clip = torch.zeros(
                (1, self.clip_frames, 3, self.input_size, self.input_size), device=self.device
            )
            output = self.model(clip)
        if tuple(output.shape) != (1, len(self.labels)):
            raise RuntimeError("The garment classifier returned an unexpected output shape.")

    def predict(self, frames_bgr: list[Any]) -> dict[str, Any]:
        import cv2

        if len(frames_bgr) != self.clip_frames:
            raise ValueError(f"Garment classification requires exactly {self.clip_frames} frames.")

        tensors = [
            self.transform(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) for frame in frames_bgr
        ]
        clip = torch.stack(tensors, dim=0).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            probabilities = torch.softmax(self.model(clip), dim=1)[0].detach().cpu().tolist()

        index = max(range(len(probabilities)), key=lambda item: probabilities[item])
        return {
            "label": self.labels[index],
            "confidence": float(probabilities[index]),
            "probabilities": {
                label: float(probabilities[position]) for position, label in enumerate(self.labels)
            },
        }
