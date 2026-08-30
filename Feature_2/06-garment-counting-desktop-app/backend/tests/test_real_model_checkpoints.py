from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn

from app.vision.classifier import GarmentClassifier, TemporalMobileNetV3Small, load_label_mapping
from app.vision.detector import WorkstationDetector

MODEL_DIRECTORY = Path(__file__).resolve().parents[2] / "resources" / "models"


def test_supplied_classifier_checkpoint_loads_strictly_and_predicts_real_clip() -> None:
    classifier = GarmentClassifier(
        MODEL_DIRECTORY / "best_model.pt", MODEL_DIRECTORY / "label_mapping.json", device="cpu"
    )
    assert classifier.labels == ("IDLE_SETUP", "SEWING")
    assert isinstance(classifier.model, TemporalMobileNetV3Small)
    assert isinstance(classifier.model.classifier[1], nn.ReLU)
    assert tuple(classifier.model.classifier[0].weight.shape) == (1024, 576)
    assert tuple(classifier.model.classifier[3].weight.shape) == (2, 1024)
    frame = np.zeros((224, 224, 3), dtype=np.uint8)
    prediction = classifier.predict([frame] * 8)
    assert prediction["label"] in {"IDLE_SETUP", "SEWING"}
    assert abs(sum(prediction["probabilities"].values()) - 1.0) < 0.00001


def test_supplied_checkpoint_preserves_training_configuration_and_labels() -> None:
    checkpoint = torch.load(
        MODEL_DIRECTORY / "best_model.pt", map_location="cpu", weights_only=True
    )
    assert checkpoint["architecture"] == "TemporalMobileNetV3Small"
    assert checkpoint["class_names"] == ["IDLE_SETUP", "SEWING"]
    assert checkpoint["config"]["frames_per_clip"] == 8
    assert checkpoint["config"]["input_size"] == 224
    assert load_label_mapping(MODEL_DIRECTORY / "label_mapping.json") == (
        "IDLE_SETUP", "SEWING"
    )


def test_supplied_yolo_checkpoint_detects_only_the_trained_workstation_class(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("YOLO_CONFIG_DIR", str(tmp_path / "ultralytics"))
    detector = WorkstationDetector(MODEL_DIRECTORY / "best.pt", device="cpu")
    assert detector.model.names == {0: "workstation"}
    detection = detector.detect(np.zeros((224, 224, 3), dtype=np.uint8))
    assert detection.visible is False
    assert detection.confidence == 0.0
