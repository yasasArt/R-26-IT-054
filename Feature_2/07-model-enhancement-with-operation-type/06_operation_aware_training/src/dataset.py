from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
from torchvision.transforms import functional as TF
from torchvision.transforms.functional import InterpolationMode


# ---------------------------------------------------------
# State-label configuration
# ---------------------------------------------------------

CLASS_NAMES = (
    "IDLE_SETUP",
    "SEWING",
)

CLASS_TO_INDEX = {
    name: index
    for index, name in enumerate(CLASS_NAMES)
}

IMAGENET_MEAN = (
    0.485,
    0.456,
    0.406,
)

IMAGENET_STD = (
    0.229,
    0.224,
    0.225,
)


# ---------------------------------------------------------
# Clip record
# ---------------------------------------------------------

@dataclass(frozen=True)
class OperationAwareClipRecord:
    """
    Stores the metadata required for one training clip.
    """

    path: Path
    relative_path: str
    clip_name: str
    video_name: str
    split: str
    state: str
    state_index: int
    operation_type: str
    operation_index: int
    start_time_sec: float
    end_time_sec: float


# ---------------------------------------------------------
# Operation mapping
# ---------------------------------------------------------

def load_operation_mapping(
    mapping_path: str | Path,
) -> tuple[dict[str, int], tuple[str, ...]]:
    """
    Load and validate operation_mapping.json.
    """

    path = Path(mapping_path).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"Operation mapping was not found: {path}"
        )

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in operation mapping: {path}"
        ) from error

    operation_to_index = data.get(
        "operation_to_index"
    )

    index_to_operation = data.get(
        "index_to_operation"
    )

    if not isinstance(operation_to_index, dict):
        raise ValueError(
            "operation_to_index must be a JSON object."
        )

    if not isinstance(index_to_operation, list):
        raise ValueError(
            "index_to_operation must be a JSON list."
        )

    clean_mapping: dict[str, int] = {}

    for operation, index in operation_to_index.items():
        operation_name = str(operation).strip().upper()

        if not isinstance(index, int):
            raise ValueError(
                f"Operation index for {operation_name} "
                f"must be an integer."
            )

        clean_mapping[operation_name] = index

    expected_indices = list(
        range(len(clean_mapping))
    )

    actual_indices = sorted(
        clean_mapping.values()
    )

    if actual_indices != expected_indices:
        raise ValueError(
            "Operation indices must start at zero "
            "and remain consecutive."
        )

    clean_index_to_operation = tuple(
        str(operation).strip().upper()
        for operation in index_to_operation
    )

    if len(clean_index_to_operation) != len(
        clean_mapping
    ):
        raise ValueError(
            "operation_to_index and "
            "index_to_operation have different sizes."
        )

    for operation, index in clean_mapping.items():
        if clean_index_to_operation[index] != operation:
            raise ValueError(
                "Operation mapping directions do not match."
            )

    return (
        clean_mapping,
        clean_index_to_operation,
    )


# ---------------------------------------------------------
# Clip transformations
# ---------------------------------------------------------

class ClipTransform:
    """
    Apply the same transformation to every frame in a clip.

    This implementation is intentionally identical to the
    original dataset pipeline.
    """

    def __init__(
        self,
        training: bool,
        input_size: int = 224,
    ) -> None:
        self.training = training
        self.input_size = input_size
        self.resize_size = int(
            round(input_size / 0.875)
        )

    def __call__(
        self,
        frames: torch.Tensor,
    ) -> torch.Tensor:

        # Input shape:
        # [time, channels, height, width]
        #
        # Pixel values:
        # floating-point values between 0 and 1.

        frames = TF.resize(
            frames,
            self.resize_size, # type: ignore
            interpolation=InterpolationMode.BILINEAR,
            antialias=True,
        )

        if self.training:
            height, width = frames.shape[-2:]

            max_top = max(
                0,
                height - self.input_size,
            )

            max_left = max(
                0,
                width - self.input_size,
            )

            top = (
                random.randint(0, max_top)
                if max_top
                else 0
            )

            left = (
                random.randint(0, max_left)
                if max_left
                else 0
            )

            frames = TF.crop(
                frames,
                top,
                left,
                self.input_size,
                self.input_size,
            )

            if random.random() < 0.5:
                frames = TF.hflip(frames)

            brightness = random.uniform(
                0.90,
                1.10,
            )

            contrast = random.uniform(
                0.90,
                1.10,
            )

            saturation = random.uniform(
                0.90,
                1.10,
            )

            frames = TF.adjust_brightness(
                frames,
                brightness,
            )

            frames = TF.adjust_contrast(
                frames,
                contrast,
            )

            frames = TF.adjust_saturation(
                frames,
                saturation,
            )

        else:
            frames = TF.center_crop(
                frames,
                [
                    self.input_size,
                    self.input_size,
                ],
            )

        return TF.normalize(
            frames,
            IMAGENET_MEAN, # type: ignore
            IMAGENET_STD, # type: ignore
        )


# ---------------------------------------------------------
# Manifest reading
# ---------------------------------------------------------

def read_operation_aware_manifest(
    dataset_dir: Path,
    manifest_path: Path,
    split: str,
    operation_to_index: dict[str, int],
) -> list[OperationAwareClipRecord]:
    """
    Read one split from enhanced_clip_manifest.csv.
    """

    required_columns = {
        "split",
        "clip_name",
        "relative_clip_path",
        "video_name",
        "operation_type",
        "start_time_sec",
        "end_time_sec",
        "state",
        "status",
    }

    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Enhanced clip manifest was not found: "
            f"{manifest_path}"
        )

    records: list[OperationAwareClipRecord] = []

    with manifest_path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as manifest_file:

        reader = csv.DictReader(manifest_file)

        missing_columns = required_columns.difference(
            reader.fieldnames or []
        )

        if missing_columns:
            raise ValueError(
                "Enhanced clip manifest is missing columns: "
                f"{sorted(missing_columns)}"
            )

        for row_number, row in enumerate(
            reader,
            start=2,
        ):
            row_split = row["split"].strip().lower()

            if row_split != split:
                continue

            if row["status"].strip().upper() != "GENERATED":
                continue

            state = row["state"].strip().upper()

            if state not in CLASS_TO_INDEX:
                raise ValueError(
                    f"Unsupported state {state!r} "
                    f"at manifest row {row_number}."
                )

            operation_type = (
                row["operation_type"]
                .strip()
                .upper()
            )

            if operation_type not in operation_to_index:
                raise ValueError(
                    f"Unsupported operation "
                    f"{operation_type!r} at manifest "
                    f"row {row_number}."
                )

            relative_path = (
                row["relative_clip_path"].strip()
            )

            clip_path = (
                dataset_dir
                / relative_path
            ).resolve()

            try:
                clip_path.relative_to(
                    dataset_dir.resolve()
                )

            except ValueError as error:
                raise ValueError(
                    f"Unsafe clip path at manifest "
                    f"row {row_number}: {relative_path}"
                ) from error

            if not clip_path.is_file():
                raise FileNotFoundError(
                    f"Clip listed in the manifest "
                    f"does not exist: {clip_path}"
                )

            try:
                start_time_sec = float(
                    row["start_time_sec"]
                )

                end_time_sec = float(
                    row["end_time_sec"]
                )

            except ValueError as error:
                raise ValueError(
                    f"Invalid clip time at manifest "
                    f"row {row_number}."
                ) from error

            records.append(
                OperationAwareClipRecord(
                    path=clip_path,
                    relative_path=relative_path,
                    clip_name=row[
                        "clip_name"
                    ].strip(),
                    video_name=row[
                        "video_name"
                    ].strip(),
                    split=split,
                    state=state,
                    state_index=CLASS_TO_INDEX[
                        state
                    ],
                    operation_type=operation_type,
                    operation_index=(
                        operation_to_index[
                            operation_type
                        ]
                    ),
                    start_time_sec=start_time_sec,
                    end_time_sec=end_time_sec,
                )
            )

    if not records:
        raise ValueError(
            f"No GENERATED clips were found "
            f"for split {split!r}."
        )

    return records


# ---------------------------------------------------------
# Frame decoding
# ---------------------------------------------------------

def decode_uniform_frames(
    path: Path,
    frames_per_clip: int,
) -> torch.Tensor:
    """
    Uniformly sample frames from one video clip.

    This function is identical to the original loader.
    """

    capture = cv2.VideoCapture(
        str(path)
    )

    try:
        frame_count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        if frame_count <= 0:
            raise RuntimeError(
                f"Video reports no frames: {path}"
            )

        frame_indices = np.linspace(
            0,
            frame_count - 1,
            frames_per_clip,
        ).round().astype(int)

        decoded_frames: list[
            torch.Tensor
        ] = []

        for frame_index in frame_indices:
            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                int(frame_index),
            )

            success, frame = capture.read()

            if not success or frame is None:
                raise RuntimeError(
                    f"Could not decode frame "
                    f"{frame_index} from {path}"
                )

            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            tensor = torch.from_numpy(
                frame
            ).permute(
                2,
                0,
                1,
            )

            decoded_frames.append(
                tensor
            )

    finally:
        capture.release()

    return (
        torch.stack(decoded_frames)
        .float()
        .div_(255.0)
    )


# ---------------------------------------------------------
# Operation-aware dataset
# ---------------------------------------------------------

class OperationAwareGarmentClipDataset(
    Dataset[
        tuple[
            torch.Tensor,
            int,
            int,
            dict[str, Any],
        ]
    ]
):
    """
    Dataset that returns video frames, state label,
    operation ID and clip metadata.
    """

    def __init__(
        self,
        dataset_dir: str | Path,
        manifest_path: str | Path,
        operation_mapping_path: str | Path,
        split: str,
        frames_per_clip: int = 8,
        input_size: int = 224,
    ) -> None:

        self.dataset_dir = (
            Path(dataset_dir)
            .expanduser()
            .resolve()
        )

        self.manifest_path = (
            Path(manifest_path)
            .expanduser()
            .resolve()
        )

        self.split = split.strip().lower()

        if self.split not in {
            "train",
            "validation",
            "test",
        }:
            raise ValueError(
                "split must be train, validation, "
                "or test."
            )

        if frames_per_clip <= 0:
            raise ValueError(
                "frames_per_clip must be "
                "greater than zero."
            )

        if input_size <= 0:
            raise ValueError(
                "input_size must be "
                "greater than zero."
            )

        if not self.dataset_dir.is_dir():
            raise FileNotFoundError(
                f"Clip dataset directory "
                f"was not found: "
                f"{self.dataset_dir}"
            )

        (
            self.operation_to_index,
            self.index_to_operation,
        ) = load_operation_mapping(
            operation_mapping_path
        )

        self.frames_per_clip = (
            frames_per_clip
        )

        self.input_size = input_size

        self.transform = ClipTransform(
            training=self.split == "train",
            input_size=input_size,
        )

        self.records = (
            read_operation_aware_manifest(
                dataset_dir=self.dataset_dir,
                manifest_path=self.manifest_path,
                split=self.split,
                operation_to_index=(
                    self.operation_to_index
                ),
            )
        )

    @property
    def class_counts(self) -> dict[str, int]:
        """
        Number of clips belonging to each state.
        """

        return {
            state: sum(
                record.state == state
                for record in self.records
            )
            for state in CLASS_NAMES
        }

    @property
    def operation_counts(self) -> dict[str, int]:
        """
        Number of clips belonging to each operation.
        """

        return {
            operation: sum(
                record.operation_type
                == operation
                for record in self.records
            )
            for operation
            in self.index_to_operation
        }

    @property
    def source_videos(self) -> set[str]:
        """
        Unique source videos used by this dataset.
        """

        return {
            record.video_name
            for record in self.records
        }

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(
        self,
        index: int,
    ) -> tuple[
        torch.Tensor,
        int,
        int,
        dict[str, Any],
    ]:
        record = self.records[index]

        frames = decode_uniform_frames(
            record.path,
            self.frames_per_clip,
        )

        frames = self.transform(
            frames
        )

        metadata = {
            "clip_name": record.clip_name,
            "relative_clip_path": (
                record.relative_path
            ),
            "video_name": record.video_name,
            "state": record.state,
            "operation_type": (
                record.operation_type
            ),
            "start_time_sec": (
                record.start_time_sec
            ),
            "end_time_sec": (
                record.end_time_sec
            ),
        }

        return (
            frames,
            record.state_index,
            record.operation_index,
            metadata,
        )


# ---------------------------------------------------------
# Leakage validation
# ---------------------------------------------------------

def assert_no_video_leakage(
    *datasets: OperationAwareGarmentClipDataset,
) -> None:
    """
    Confirm that a source video does not appear
    in more than one dataset split.
    """

    for left_index, left_dataset in enumerate(
        datasets
    ):
        for right_dataset in datasets[
            left_index + 1:
        ]:
            overlap = (
                left_dataset.source_videos
                .intersection(
                    right_dataset.source_videos
                )
            )

            if overlap:
                raise ValueError(
                    "Source-video leakage between "
                    f"{left_dataset.split} and "
                    f"{right_dataset.split}: "
                    f"{sorted(overlap)}"
                )