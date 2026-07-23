from __future__ import annotations

import csv
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


CLASS_NAMES = ("IDLE_SETUP", "SEWING")
CLASS_TO_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class ClipRecord:
    path: Path
    relative_path: str
    clip_name: str
    video_name: str
    split: str
    state: str
    start_time_sec: float
    end_time_sec: float


class ClipTransform:
    """Apply the same spatial/color augmentation to every frame in a clip."""

    def __init__(self, training: bool, input_size: int = 224) -> None:
        self.training = training
        self.input_size = input_size
        self.resize_size = int(round(input_size / 0.875))

    def __call__(self, frames: torch.Tensor) -> torch.Tensor:
        # frames: [time, channels, height, width], float in [0, 1]
        frames = TF.resize(
            frames,
            self.resize_size, # type: ignore
            interpolation=InterpolationMode.BILINEAR,
            antialias=True,
        )

        if self.training:
            height, width = frames.shape[-2:]
            max_top = max(0, height - self.input_size)
            max_left = max(0, width - self.input_size)
            top = random.randint(0, max_top) if max_top else 0
            left = random.randint(0, max_left) if max_left else 0
            frames = TF.crop(frames, top, left, self.input_size, self.input_size)

            if random.random() < 0.5:
                frames = TF.hflip(frames)

            brightness = random.uniform(0.90, 1.10)
            contrast = random.uniform(0.90, 1.10)
            saturation = random.uniform(0.90, 1.10)
            frames = TF.adjust_brightness(frames, brightness)
            frames = TF.adjust_contrast(frames, contrast)
            frames = TF.adjust_saturation(frames, saturation)
        else:
            frames = TF.center_crop(frames, [self.input_size, self.input_size])

        return TF.normalize(frames, IMAGENET_MEAN, IMAGENET_STD) # type: ignore


def _read_manifest(dataset_dir: Path, manifest_path: Path, split: str) -> list[ClipRecord]:
    required = {
        "split",
        "clip_name",
        "relative_clip_path",
        "video_name",
        "start_time_sec",
        "end_time_sec",
        "state",
        "status",
    }
    records: list[ClipRecord] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest is missing columns: {sorted(missing)}")
        for row in reader:
            if row["split"].strip().lower() != split:
                continue
            if row["status"].strip().upper() != "GENERATED":
                continue
            state = row["state"].strip().upper()
            if state not in CLASS_TO_INDEX:
                raise ValueError(f"Unsupported state {state!r} in {manifest_path}")
            relative_path = row["relative_clip_path"].strip()
            path = (dataset_dir / relative_path).resolve()
            try:
                path.relative_to(dataset_dir.resolve())
            except ValueError as exc:
                raise ValueError(f"Unsafe clip path in manifest: {relative_path}") from exc
            if not path.is_file():
                raise FileNotFoundError(f"Clip listed in manifest does not exist: {path}")
            records.append(
                ClipRecord(
                    path=path,
                    relative_path=relative_path,
                    clip_name=row["clip_name"].strip(),
                    video_name=row["video_name"].strip(),
                    split=split,
                    state=state,
                    start_time_sec=float(row["start_time_sec"]),
                    end_time_sec=float(row["end_time_sec"]),
                )
            )
    if not records:
        raise ValueError(f"No GENERATED clips found for split {split!r}")
    return records


def _decode_uniform_frames(path: Path, frames_per_clip: int) -> torch.Tensor:
    capture = cv2.VideoCapture(str(path))
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            raise RuntimeError(f"Video reports no frames: {path}")
        indices = np.linspace(0, frame_count - 1, frames_per_clip).round().astype(int)
        decoded: list[torch.Tensor] = []
        for frame_index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError(f"Could not decode frame {frame_index} from {path}")
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            decoded.append(torch.from_numpy(frame).permute(2, 0, 1))
    finally:
        capture.release()
    return torch.stack(decoded).float().div_(255.0)


class GarmentClipDataset(Dataset[tuple[torch.Tensor, int, dict[str, Any]]]):
    def __init__(
        self,
        dataset_dir: str | Path,
        split: str,
        frames_per_clip: int = 8,
        input_size: int = 224,
    ) -> None:
        self.dataset_dir = Path(dataset_dir).expanduser().resolve()
        self.split = split.strip().lower()
        if self.split not in {"train", "validation", "test"}:
            raise ValueError("split must be train, validation, or test")
        self.frames_per_clip = frames_per_clip
        self.transform = ClipTransform(self.split == "train", input_size)
        self.records = _read_manifest(
            self.dataset_dir, self.dataset_dir / "clip_manifest.csv", self.split
        )

    @property
    def class_counts(self) -> dict[str, int]:
        return {
            state: sum(record.state == state for record in self.records)
            for state in CLASS_NAMES
        }

    @property
    def source_videos(self) -> set[str]:
        return {record.video_name for record in self.records}

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, dict[str, Any]]:
        record = self.records[index]
        frames = self.transform(_decode_uniform_frames(record.path, self.frames_per_clip))
        metadata = {
            "clip_name": record.clip_name,
            "relative_clip_path": record.relative_path,
            "video_name": record.video_name,
            "start_time_sec": record.start_time_sec,
            "end_time_sec": record.end_time_sec,
        }
        return frames, CLASS_TO_INDEX[record.state], metadata


def assert_no_video_leakage(*datasets: GarmentClipDataset) -> None:
    for left_index, left in enumerate(datasets):
        for right in datasets[left_index + 1 :]:
            overlap = left.source_videos.intersection(right.source_videos)
            if overlap:
                raise ValueError(
                    f"Source-video leakage between {left.split} and {right.split}: "
                    f"{sorted(overlap)}"
                )

