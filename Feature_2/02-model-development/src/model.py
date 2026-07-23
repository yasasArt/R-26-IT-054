from __future__ import annotations

import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


class TemporalMobileNetV3Small(nn.Module):
    def __init__(self, num_classes: int = 2, pretrained: bool = True) -> None:
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        network = mobilenet_v3_small(weights=weights)
        self.features = network.features
        self.avgpool = network.avgpool
        feature_dim = network.classifier[0].in_features
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, 1024),
            nn.Hardswish(),
            nn.Dropout(p=0.20),
            nn.Linear(1024, num_classes),
        )

    def forward(self, clips: torch.Tensor) -> torch.Tensor:
        if clips.ndim != 5:
            raise ValueError("Expected input shape [batch, time, channels, height, width]")
        batch_size, time_steps, channels, height, width = clips.shape
        frames = clips.reshape(batch_size * time_steps, channels, height, width)
        features = self.avgpool(self.features(frames)).flatten(1)
        features = features.reshape(batch_size, time_steps, -1).mean(dim=1)
        return self.classifier(features)


def build_optimizer(
    model: TemporalMobileNetV3Small,
    backbone_learning_rate: float,
    classifier_learning_rate: float,
    weight_decay: float,
) -> torch.optim.Optimizer:
    return torch.optim.AdamW(
        [
            {"params": model.features.parameters(), "lr": backbone_learning_rate},
            {"params": model.classifier.parameters(), "lr": classifier_learning_rate},
        ],
        weight_decay=weight_decay,
    )

