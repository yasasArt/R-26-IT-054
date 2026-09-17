from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import (
    MobileNet_V3_Small_Weights,
    mobilenet_v3_small,
)


class OperationAwareTemporalMobileNetV3Small(
    nn.Module
):
    """
    Temporal MobileNetV3-Small that uses both:

    1. Visual features from an eight-frame clip.
    2. A known sewing-operation ID.

    The operation ID is converted into a one-hot vector
    and concatenated with the visual features.
    """

    def __init__(
        self,
        num_classes: int = 2,
        num_operations: int = 3,
        pretrained: bool = True,
    ) -> None:
        super().__init__()

        if num_classes <= 0:
            raise ValueError(
                "num_classes must be greater than zero."
            )

        if num_operations <= 0:
            raise ValueError(
                "num_operations must be greater than zero."
            )

        weights = (
            MobileNet_V3_Small_Weights.DEFAULT
            if pretrained
            else None
        )

        network = mobilenet_v3_small(
            weights=weights
        )

        # MobileNetV3 convolutional feature extractor.
        self.features = network.features

        # Converts the final feature map into one value
        # per feature channel.
        self.avgpool = network.avgpool

        # MobileNetV3-Small produces 576 visual features.
        self.visual_feature_dim = (
            network.classifier[0].in_features
        )

        self.num_classes = num_classes
        self.num_operations = num_operations

        # A one-hot vector has one value per operation.
        self.operation_feature_dim = num_operations

        self.combined_feature_dim = (
            self.visual_feature_dim
            + self.operation_feature_dim
        ) # type: ignore

        # Current baseline:
        # 576 -> 1024 -> 2
        #
        # Enhanced model:
        # 579 -> 1024 -> 2
        self.classifier = nn.Sequential(
            nn.Linear(
                self.combined_feature_dim, # type: ignore
                1024,
            ),
            nn.Hardswish(),
            nn.Dropout(p=0.20),
            nn.Linear(
                1024,
                num_classes,
            ),
        )

    def extract_visual_features(
        self,
        clips: torch.Tensor,
    ) -> torch.Tensor:
        """
        Extract one visual feature vector per clip.

        Input:
            [batch, time, channels, height, width]

        Output:
            [batch, 576]
        """

        if clips.ndim != 5:
            raise ValueError(
                "Expected clips with shape "
                "[batch, time, channels, height, width]."
            )

        (
            batch_size,
            time_steps,
            channels,
            height,
            width,
        ) = clips.shape

        if batch_size <= 0:
            raise ValueError(
                "The clip batch cannot be empty."
            )

        if time_steps <= 0:
            raise ValueError(
                "A clip must contain at least one frame."
            )

        if channels != 3:
            raise ValueError(
                "Expected three RGB channels."
            )

        # Combine batch and time so MobileNet processes
        # every frame independently.
        frames = clips.reshape(
            batch_size * time_steps,
            channels,
            height,
            width,
        )

        frame_features = self.features(
            frames
        )

        frame_features = self.avgpool(
            frame_features
        ).flatten(1)

        # Restore the time dimension.
        frame_features = frame_features.reshape(
            batch_size,
            time_steps,
            -1,
        )

        # Produce one visual vector for the full clip.
        clip_features = frame_features.mean(
            dim=1
        )

        return clip_features

    def encode_operations(
        self,
        operation_indices: torch.Tensor,
        output_dtype: torch.dtype,
    ) -> torch.Tensor:
        """
        Convert operation IDs into one-hot vectors.

        Examples:

            COLLAR = 0 -> [1, 0, 0]
            POCKET = 1 -> [0, 1, 0]
            SLEEVE = 2 -> [0, 0, 1]
        """

        if operation_indices.ndim != 1:
            raise ValueError(
                "Expected operation_indices with "
                "shape [batch]."
            )

        if operation_indices.numel() == 0:
            raise ValueError(
                "The operation batch cannot be empty."
            )

        if operation_indices.dtype not in {
            torch.int8,
            torch.int16,
            torch.int32,
            torch.int64,
            torch.uint8,
        }:
            raise ValueError(
                "Operation indices must use an "
                "integer tensor type."
            )

        operation_indices = operation_indices.to(
            dtype=torch.int64
        )

        minimum_index = int(
            operation_indices.min().item()
        )

        maximum_index = int(
            operation_indices.max().item()
        )

        if minimum_index < 0:
            raise ValueError(
                "Operation indices cannot be negative."
            )

        if maximum_index >= self.num_operations:
            raise ValueError(
                "Operation index is outside the "
                f"supported range 0 to "
                f"{self.num_operations - 1}."
            )

        one_hot_operations = F.one_hot(
            operation_indices,
            num_classes=self.num_operations,
        )

        return one_hot_operations.to(
            dtype=output_dtype
        )

    def forward(
        self,
        clips: torch.Tensor,
        operation_indices: torch.Tensor,
    ) -> torch.Tensor:
        """
        Produce state-classification logits.

        Inputs:
            clips:
                [batch, time, 3, height, width]

            operation_indices:
                [batch]

        Output:
            [batch, num_classes]
        """

        visual_features = (
            self.extract_visual_features(
                clips
            )
        )

        if (
            operation_indices.shape[0]
            != visual_features.shape[0]
        ):
            raise ValueError(
                "Clip batch size and operation batch "
                "size do not match."
            )

        operation_features = (
            self.encode_operations(
                operation_indices,
                output_dtype=(
                    visual_features.dtype
                ),
            )
        )

        operation_features = (
            operation_features.to(
                device=visual_features.device
            )
        )

        combined_features = torch.cat(
            [
                visual_features,
                operation_features,
            ],
            dim=1,
        )

        if (
            combined_features.shape[1]
            != self.combined_feature_dim
        ):
            raise RuntimeError(
                "Unexpected combined feature size."
            )

        return self.classifier(
            combined_features
        )


def build_optimizer(
    model: OperationAwareTemporalMobileNetV3Small,
    backbone_learning_rate: float,
    classifier_learning_rate: float,
    weight_decay: float,
) -> torch.optim.Optimizer:
    """
    Build the same AdamW optimizer strategy used
    by the current baseline model.
    """

    return torch.optim.AdamW(
        [
            {
                "params": (
                    model.features.parameters()
                ),
                "lr": backbone_learning_rate,
            },
            {
                "params": (
                    model.classifier.parameters()
                ),
                "lr": classifier_learning_rate,
            },
        ],
        weight_decay=weight_decay,
    )