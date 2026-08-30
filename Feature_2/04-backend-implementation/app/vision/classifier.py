from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import torch
    from torch import Tensor, nn
    from torchvision.models import mobilenet_v3_small
except (ImportError, RuntimeError) as exc:  # Report missing/incompatible runtimes.
    torch = None  # type: ignore[assignment]
    Tensor = Any  # type: ignore[misc,assignment]
    nn = None  # type: ignore[assignment]
    mobilenet_v3_small = None  # type: ignore[assignment]
    _TORCH_IMPORT_ERROR: Exception | None = exc
else:
    _TORCH_IMPORT_ERROR = None


CLASS_NAMES = ("IDLE_SETUP", "SEWING")
CLIP_FRAMES = 8
IMAGE_SIZE = 224
FEATURE_DIMENSIONS = 576
HIDDEN_DIMENSIONS = 1024
NUM_CLASSES = 2
DEFAULT_DROPOUT = 0.2
IMAGENET_MEAN = np.asarray((0.485, 0.456, 0.406), dtype=np.float32)
IMAGENET_STD = np.asarray((0.229, 0.224, 0.225), dtype=np.float32)


class ModelDependencyError(RuntimeError):
    """Raised when optional model libraries are not installed."""


class ClassifierCheckpointError(RuntimeError):
    """Raised when a classifier checkpoint does not match the trained model."""


def require_torch() -> None:
    """Raise a controlled error instead of failing during application import."""

    if torch is None or nn is None or mobilenet_v3_small is None:
        raise ModelDependencyError(
            "PyTorch and torchvision are required to load the garment classifier"
        ) from _TORCH_IMPORT_ERROR


if nn is not None:

    class TemporalMobileNetV3Small(nn.Module):

        def __init__(self, dropout: float = DEFAULT_DROPOUT) -> None:
            super().__init__()
            backbone = mobilenet_v3_small(weights=None)
            self.backbone = backbone.features
            self.pool = nn.AdaptiveAvgPool2d((1, 1))
            self.classifier = nn.Sequential(
                nn.Linear(FEATURE_DIMENSIONS, HIDDEN_DIMENSIONS),
                nn.Hardswish(),
                nn.Dropout(p=dropout),
                nn.Linear(HIDDEN_DIMENSIONS, NUM_CLASSES),
            )

        def forward(self, clips: Tensor) -> Tensor:
            if clips.ndim != 5:
                raise ValueError(
                    "Classifier input must have shape [batch, frames, 3, height, width]"
                )
            batch_size, frame_count, channels, height, width = clips.shape
            if channels != 3:
                raise ValueError(
                    "Classifier input must contain exactly three RGB channels"
                )

            frames = clips.reshape(batch_size * frame_count, channels, height, width)
            features = self.backbone(frames)
            features = self.pool(features).flatten(1)
            temporal_features = features.reshape(
                batch_size, frame_count, FEATURE_DIMENSIONS
            ).mean(dim=1)
            return self.classifier(temporal_features)

else:

    class TemporalMobileNetV3Small:  # type: ignore[no-redef]
        """Dependency-safe placeholder used only when torch is unavailable."""

        def __init__(self, *_: Any, **__: Any) -> None:
            require_torch()


def _as_rgb_image(frame: Image.Image | np.ndarray) -> Image.Image:
    if isinstance(frame, Image.Image):
        return frame.convert("RGB")

    array = np.asarray(frame)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("Each classifier frame must be an RGB image")
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def prepare_clip(
    frames: Sequence[Image.Image | np.ndarray],
    *,
    device: str = "cpu",
) -> Tensor:
    """Resize, normalize and batch exactly eight RGB frames."""

    require_torch()
    if len(frames) != CLIP_FRAMES:
        raise ValueError(f"Classifier requires exactly {CLIP_FRAMES} frames")

    prepared: list[np.ndarray] = []
    for frame in frames:
        image = _as_rgb_image(frame).resize(
            (IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR
        )
        array = np.asarray(image, dtype=np.float32) / 255.0
        array = (array - IMAGENET_MEAN) / IMAGENET_STD
        prepared.append(np.transpose(array, (2, 0, 1)))

    clip = torch.from_numpy(np.stack(prepared)).unsqueeze(0)
    return clip.to(device=device, dtype=torch.float32)


def _extract_state_dict(checkpoint: Any) -> Mapping[str, Tensor]:
    if not isinstance(checkpoint, Mapping):
        raise ClassifierCheckpointError(
            "Classifier checkpoint must contain a state dictionary"
        )

    for key in ("model_state_dict", "state_dict"):
        candidate = checkpoint.get(key)
        if isinstance(candidate, Mapping):
            return candidate

    if checkpoint and all(isinstance(key, str) for key in checkpoint):
        return checkpoint
    raise ClassifierCheckpointError(
        "Classifier checkpoint has no model state dictionary"
    )


def _canonical_key(key: str) -> str:
    for prefix in ("module.", "model."):
        key = key.removeprefix(prefix)
    if key.startswith("features."):
        return "backbone." + key[len("features.") :]
    if key.startswith("feature_extractor."):
        return "backbone." + key[len("feature_extractor.") :]
    if key.startswith("backbone.features."):
        return "backbone." + key[len("backbone.features.") :]
    if key.startswith("temporal_classifier."):
        return "classifier." + key[len("temporal_classifier.") :]
    if key.startswith("classifier_head."):
        return "classifier." + key[len("classifier_head.") :]
    if key.startswith("head."):
        return "classifier." + key[len("head.") :]
    if key.startswith("fc."):
        return "classifier." + key[len("fc.") :]
    return key


def canonicalize_state_dict(state_dict: Mapping[str, Tensor]) -> dict[str, Tensor]:
    """Normalize common training-wrapper prefixes without weakening validation."""

    canonical: dict[str, Tensor] = {}
    for key, value in state_dict.items():
        normalized = _canonical_key(str(key))
        if normalized in canonical:
            raise ClassifierCheckpointError(
                f"Classifier checkpoint contains duplicate key {normalized}"
            )
        canonical[normalized] = value
    return canonical


def validate_classifier_dimensions(state_dict: Mapping[str, Tensor]) -> None:
    """Validate the exact learned head dimensions before loading any weights."""

    expected = {
        "classifier.0.weight": (HIDDEN_DIMENSIONS, FEATURE_DIMENSIONS),
        "classifier.0.bias": (HIDDEN_DIMENSIONS,),
        "classifier.3.weight": (NUM_CLASSES, HIDDEN_DIMENSIONS),
        "classifier.3.bias": (NUM_CLASSES,),
    }
    problems: list[str] = []
    for key, expected_shape in expected.items():
        value = state_dict.get(key)
        if value is None:
            problems.append(f"missing {key}")
            continue
        actual_shape = tuple(value.shape)
        if actual_shape != expected_shape:
            problems.append(
                f"{key} has shape {actual_shape}, expected {expected_shape}"
            )
    if problems:
        raise ClassifierCheckpointError(
            "Classifier architecture mismatch: " + "; ".join(problems)
        )


def load_classifier(checkpoint_path: Path, device: str) -> TemporalMobileNetV3Small:
    """Load, strictly validate and place the classifier in evaluation mode."""

    require_torch()
    try:
        try:
            checkpoint = torch.load(
                checkpoint_path, map_location="cpu", weights_only=True
            )
        except TypeError:  # PyTorch versions before the weights_only argument.
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
    except Exception as exc:
        raise ClassifierCheckpointError(
            f"Unable to read classifier checkpoint: {exc}"
        ) from exc

    state_dict = canonicalize_state_dict(_extract_state_dict(checkpoint))
    validate_classifier_dimensions(state_dict)
    model = TemporalMobileNetV3Small()
    try:
        model.load_state_dict(state_dict, strict=True)
    except RuntimeError as exc:
        raise ClassifierCheckpointError(
            f"Classifier checkpoint keys do not match the deployment model: {exc}"
        ) from exc
    model.to(device)
    model.eval()
    return model
