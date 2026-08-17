from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path


SPLIT_VIDEOS = {
    "train": [
        "v01", "v03", "v04", "v05", "v06", "v07", "v08", "v09", "v12", "v13",
        "v14", "v15", "v16", "v17", "v18", "v20", "v22", "v23", "v25", "v26",
    ],
    "val": ["v02", "v21", "v24", "v27"],
    "test": ["v10", "v11", "v19", "v28"],
}
VALID_STATES = ("READY", "NOT_READY", "INVALID")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path, help="Final Phase 1 CSV")
    parser.add_argument("--frames-root", required=True, type=Path, help="Folder containing v01, v02, ...")
    parser.add_argument("--output-root", required=True, type=Path, help="New dataset output folder")
    parser.add_argument(
        "--mode", choices=("manifest", "copy", "hardlink", "symlink"), default="manifest",
        help="manifest validates only; other modes also organize images",
    )
    return parser.parse_args()


def video_to_split() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for split, videos in SPLIT_VIDEOS.items():
        for video in videos:
            if video in mapping:
                raise ValueError(f"Video {video} appears in more than one split")
            mapping[video] = split
    return mapping


def read_annotations(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        required = {"video_id", "frame_id", "state"}
        missing = required.difference(headers)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise ValueError("Annotation CSV has no data rows")
    return rows, headers


def find_image(frames_root: Path, video_id: str, frame_id: str) -> Path | None:
    folder = frames_root / video_id
    for ext in IMAGE_EXTENSIONS:
        candidate = folder / f"{frame_id}{ext}"
        if candidate.is_file():
            return candidate
        upper = folder / f"{frame_id}{ext.upper()}"
        if upper.is_file():
            return upper
    return None


def transfer(source: Path, destination: Path, mode: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source.stat().st_size == destination.stat().st_size:
            return "EXISTS_SAME_SIZE"
        raise FileExistsError(f"Destination exists with different size: {destination}")
    if mode == "copy":
        shutil.copy2(source, destination)
    elif mode == "hardlink":
        os.link(source, destination)
    elif mode == "symlink":
        destination.symlink_to(source.resolve())
    return mode.upper()


def write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    split_map = video_to_split()
    rows, original_headers = read_annotations(args.annotations)
    args.output_root.mkdir(parents=True, exist_ok=True)
    frames_root_available = args.frames_root.is_dir()
    if args.mode != "manifest" and not frames_root_available:
        raise FileNotFoundError(f"Frames root does not exist: {args.frames_root}")

    errors: list[str] = []
    seen_frames: set[str] = set()
    input_videos = {row["video_id"] for row in rows}
    unknown_videos = sorted(input_videos.difference(split_map))
    missing_videos = sorted(set(split_map).difference(input_videos))
    if unknown_videos:
        errors.append(f"Videos without a split: {unknown_videos}")
    if missing_videos:
        errors.append(f"Split videos absent from CSV: {missing_videos}")

    manifest: list[dict[str, object]] = []
    missing_images: list[dict[str, object]] = []
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    event_states: dict[tuple[str, str], set[str]] = defaultdict(set)
    garment_splits: dict[str, set[str]] = defaultdict(set)

    for row_number, row in enumerate(rows, start=2):
        video_id = row["video_id"]
        frame_id = row["frame_id"]
        state = row["state"].upper()
        event_id = row.get("event_id", "")
        split = split_map.get(video_id, "UNASSIGNED")

        if state not in VALID_STATES:
            errors.append(f"Row {row_number}: invalid state {state!r}")
        if frame_id in seen_frames:
            errors.append(f"Row {row_number}: duplicate frame_id {frame_id}")
        seen_frames.add(frame_id)
        if not frame_id.startswith(f"{video_id}_"):
            errors.append(f"Row {row_number}: frame_id {frame_id} does not match {video_id}")

        source = find_image(args.frames_root, video_id, frame_id) if frames_root_available else None
        extension = source.suffix.lower() if source else ".jpg"
        relative_source = f"{video_id}/{frame_id}{extension}"
        relative_destination = f"{split}/{state}/{frame_id}{extension}"
        status = "FOUND" if source else ("MISSING" if frames_root_available else "NOT_CHECKED")

        if source is None and frames_root_available:
            missing_images.append({
                "video_id": video_id, "event_id": event_id, "frame_id": frame_id,
                "state": state, "split": split, "expected_path": relative_source,
            })
        elif args.mode != "manifest":
            destination = args.output_root / relative_destination
            status = transfer(source, destination, args.mode)

        counts[split][state] += 1
        counts[split]["TOTAL"] += 1
        if event_id:
            event_states[(split, event_id)].add(state)
        garment_id = row.get("garment_id", "")
        if garment_id:
            garment_splits[garment_id].add(split)

        output_row = dict(row)
        output_row.update({
            "state": state,
            "split": split,
            "source_path": relative_source,
            "dataset_path": relative_destination,
            "image_status": status,
        })
        manifest.append(output_row)

    garment_leaks = {g: sorted(s) for g, s in garment_splits.items() if len(s) > 1}
    if garment_leaks:
        errors.append(f"garment_id leakage across splits: {garment_leaks}")

    summary_rows: list[dict[str, object]] = []
    for split in ("train", "val", "test"):
        total = counts[split]["TOTAL"]
        event_ids = {e for s, e in event_states if s == split}
        ready_events = {e for (s, e), states in event_states.items() if s == split and "READY" in states}
        summary_rows.append({
            "split": split,
            "videos": len(SPLIT_VIDEOS[split]),
            "video_ids": ", ".join(SPLIT_VIDEOS[split]),
            "frames": total,
            "READY": counts[split]["READY"],
            "NOT_READY": counts[split]["NOT_READY"],
            "INVALID": counts[split]["INVALID"],
            "READY_percent": round(100 * counts[split]["READY"] / total, 4) if total else 0,
            "events": len(event_ids),
            "events_with_READY": len(ready_events),
            "events_without_READY": len(event_ids - ready_events),
        })

    manifest_headers = list(dict.fromkeys(original_headers + [
        "split", "source_path", "dataset_path", "image_status"
    ]))
    write_csv(args.output_root / "split_manifest.csv", manifest_headers, manifest)
    write_csv(
        args.output_root / "split_summary.csv",
        ["split", "videos", "video_ids", "frames", "READY", "NOT_READY", "INVALID",
         "READY_percent", "events", "events_with_READY", "events_without_READY"],
        summary_rows,
    )
    write_csv(
        args.output_root / "missing_frames.csv",
        ["video_id", "event_id", "frame_id", "state", "split", "expected_path"],
        missing_images,
    )

    config = {
        "seed": 42,
        "split_unit": "video_id",
        "splits": SPLIT_VIDEOS,
        "classes": list(VALID_STATES),
        "input_annotations_sha256": hashlib.sha256(args.annotations.read_bytes()).hexdigest(),
        "mode": args.mode,
        "frame_check_status": "completed" if frames_root_available else "not_run_frames_root_unavailable",
        "missing_image_count": len(missing_images),
        "validation_errors": errors,
    }
    (args.output_root / "split_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    print(json.dumps({"summary": summary_rows, "missing_images": len(missing_images), "errors": errors}, indent=2))
    if errors:
        print("Dataset preparation stopped because validation errors were found.", file=sys.stderr)
        return 2
    if args.mode != "manifest" and missing_images:
        print("Some images were not organized. Review missing_frames.csv.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())