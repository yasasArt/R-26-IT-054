#!/usr/bin/env python3
"""Phase 4 validation-only temporal best-frame selector.

This program joins the corrected annotation CSV to Phase 3B validation
probabilities, computes image-quality/temporal features, tunes temporal rules
using validation events only, and selects one frame (or NO_SUITABLE_FRAME) per
event. It never reads a test split.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


VALID_STATES = {"INVALID", "NOT_READY", "READY"}
NO_FRAME = "NO_SUITABLE_FRAME"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tune and evaluate a temporal best-frame selector on validation events only."
    )
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--threshold-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--frames-root",
        type=Path,
        default=None,
        help="Optional extracted_frames root. Used when image_path values are stale.",
    )
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument(
        "--minimum-positive-event-coverage",
        type=float,
        default=0.70,
        help="Minimum fraction of READY-containing events that must return a frame during tuning.",
    )
    parser.add_argument(
        "--reuse-features",
        action="store_true",
        help="Reuse output-dir/frame_features.csv when it matches the current validation rows.",
    )
    parser.add_argument(
        "--copy-selected",
        action="store_true",
        help="Copy chosen temporal-selector images into output-dir/selected_frames.",
    )
    parser.add_argument("--contact-sheet-columns", type=int, default=5)
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader), list(reader.fieldnames)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)


def require_columns(columns: list[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {', '.join(missing)}")


def frame_number(frame_id: str) -> int:
    try:
        return int(frame_id.rsplit("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Cannot parse numeric suffix from frame_id={frame_id!r}") from exc


def fnum(value: str, field: str, frame_id: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} for {frame_id}: {value!r}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"Non-finite {field} for {frame_id}: {value!r}")
    return parsed


def validate_inputs(
    annotations: list[dict[str, str]], predictions: list[dict[str, str]], output_dir: Path
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    ann_by_frame: dict[str, dict[str, str]] = {}
    duplicate_annotations: list[str] = []
    for row in annotations:
        fid = row["frame_id"].strip()
        if fid in ann_by_frame:
            duplicate_annotations.append(fid)
        ann_by_frame[fid] = row

    prediction_ids = [row["frame_id"].strip() for row in predictions]
    duplicate_predictions = [fid for fid, count in Counter(prediction_ids).items() if count > 1]
    issues: list[dict[str, str]] = []
    joined: list[dict[str, Any]] = []
    val_videos = {row["video_id"].strip() for row in predictions}

    for fid in duplicate_annotations:
        issues.append({"issue": "DUPLICATE_ANNOTATION", "frame_id": fid, "video_id": "", "state": "", "event_id": ""})
    for fid in duplicate_predictions:
        issues.append({"issue": "DUPLICATE_PREDICTION", "frame_id": fid, "video_id": "", "state": "", "event_id": ""})

    for pred in predictions:
        fid = pred["frame_id"].strip()
        ann = ann_by_frame.get(fid)
        if ann is None:
            issues.append({"issue": "PREDICTION_WITHOUT_ANNOTATION", "frame_id": fid, "video_id": pred["video_id"], "state": pred["actual_state"], "event_id": ""})
            continue
        video_id = pred["video_id"].strip()
        state = ann["state"].strip().upper()
        event_id = ann["event_id"].strip()
        if ann["video_id"].strip() != video_id:
            issues.append({"issue": "VIDEO_ID_MISMATCH", "frame_id": fid, "video_id": video_id, "state": state, "event_id": event_id})
        if state not in VALID_STATES:
            issues.append({"issue": "INVALID_STATE", "frame_id": fid, "video_id": video_id, "state": state, "event_id": event_id})
        if pred["actual_state"].strip().upper() != state:
            issues.append({"issue": "PREDICTION_ANNOTATION_STATE_MISMATCH", "frame_id": fid, "video_id": video_id, "state": state, "event_id": event_id})
        if state != "INVALID" and not event_id:
            issues.append({"issue": "NON_INVALID_WITH_BLANK_EVENT_ID", "frame_id": fid, "video_id": video_id, "state": state, "event_id": ""})
        if event_id and not event_id.startswith(video_id + "_E"):
            issues.append({"issue": "EVENT_VIDEO_MISMATCH", "frame_id": fid, "video_id": video_id, "state": state, "event_id": event_id})
        joined.append(
            {
                "video_id": video_id,
                "event_id": event_id,
                "frame_id": fid,
                "frame_number": frame_number(fid),
                "image_path": pred["image_path"].strip(),
                "actual_state": state,
                "p_invalid": fnum(pred["p_invalid"], "p_invalid", fid),
                "p_not_ready": fnum(pred["p_not_ready"], "p_not_ready", fid),
                "p_ready": fnum(pred["p_ready"], "p_ready", fid),
            }
        )

    annotation_val_ids = {
        row["frame_id"].strip() for row in annotations if row["video_id"].strip() in val_videos
    }
    missing_predictions = sorted(annotation_val_ids - set(prediction_ids))
    for fid in missing_predictions:
        ann = ann_by_frame[fid]
        issues.append({"issue": "VALIDATION_ANNOTATION_WITHOUT_PREDICTION", "frame_id": fid, "video_id": ann["video_id"], "state": ann["state"], "event_id": ann["event_id"]})

    write_csv(
        output_dir / "annotation_integrity_issues.csv",
        issues,
        ["issue", "video_id", "event_id", "frame_id", "state"],
    )
    return joined, issues


def resolve_image(row: dict[str, Any], frames_root: Path | None) -> Path:
    candidates: list[Path] = []
    raw = Path(row["image_path"])
    candidates.append(raw)
    if frames_root is not None:
        for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"):
            candidates.extend(
                [
                    frames_root / row["video_id"] / f"{row['frame_id']}{ext}",
                    frames_root / f"{row['frame_id']}{ext}",
                ]
            )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Image not found for {row['frame_id']}. CSV path={row['image_path']!r}; "
        "provide --frames-root pointing to extracted_frames."
    )


def grayscale_array(path: Path, size: int) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("L").resize((size, size), Image.Resampling.BILINEAR)
        return np.asarray(image, dtype=np.float32)


def laplacian_variance(gray: np.ndarray) -> float:
    center = gray[1:-1, 1:-1]
    lap = (
        -4.0 * center
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    return float(np.var(lap))


def compute_features(
    joined: list[dict[str, Any]], frames_root: Path | None, image_size: int
) -> list[dict[str, Any]]:
    rows = sorted(joined, key=lambda row: (row["video_id"], row["frame_number"]))
    previous_by_video: dict[str, np.ndarray] = {}
    previous_number: dict[str, int] = {}
    for index, row in enumerate(rows, start=1):
        path = resolve_image(row, frames_root)
        gray = grayscale_array(path, image_size)
        row["resolved_image_path"] = str(path.resolve())
        row["sharpness"] = laplacian_variance(gray)
        prev = previous_by_video.get(row["video_id"])
        consecutive = previous_number.get(row["video_id"]) == row["frame_number"] - 1
        row["motion"] = float(np.mean(np.abs(gray - prev))) if prev is not None and consecutive else math.nan
        previous_by_video[row["video_id"]] = gray
        previous_number[row["video_id"]] = row["frame_number"]
        if index % 250 == 0 or index == len(rows):
            print(f"Computed image features: {index}/{len(rows)}", flush=True)
    return rows


FEATURE_FIELDS = [
    "video_id", "event_id", "frame_id", "frame_number", "resolved_image_path",
    "actual_state", "p_invalid", "p_not_ready", "p_ready", "sharpness", "motion",
]


def load_or_compute_features(
    joined: list[dict[str, Any]], output_dir: Path, frames_root: Path | None,
    image_size: int, reuse: bool,
) -> list[dict[str, Any]]:
    cache = output_dir / "frame_features.csv"
    expected_ids = {row["frame_id"] for row in joined}
    if reuse and cache.is_file():
        cached, fields = read_csv(cache)
        require_columns(fields, set(FEATURE_FIELDS), "frame_features.csv")
        if {row["frame_id"] for row in cached} == expected_ids:
            converted: list[dict[str, Any]] = []
            for row in cached:
                converted.append(
                    {
                        **row,
                        "frame_number": int(row["frame_number"]),
                        "p_invalid": float(row["p_invalid"]),
                        "p_not_ready": float(row["p_not_ready"]),
                        "p_ready": float(row["p_ready"]),
                        "sharpness": float(row["sharpness"]),
                        "motion": float(row["motion"]) if row["motion"] else math.nan,
                    }
                )
            print(f"Reused image features: {cache}")
            return converted
        print("Feature cache does not match current validation frames; recomputing.")
    features = compute_features(joined, frames_root, image_size)
    write_csv(cache, features, FEATURE_FIELDS)
    return features


def trailing_mean(values: list[float], window: int) -> list[float]:
    result: list[float] = []
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= window:
            running -= values[i - window]
        result.append(running / min(i + 1, window))
    return result


def percentile(values: list[float], q: float) -> float:
    clean = np.asarray([x for x in values if math.isfinite(x)], dtype=np.float64)
    if not len(clean):
        raise ValueError("Cannot calculate percentile from an empty feature set")
    return float(np.percentile(clean, q))


def longest_ready_run_center(rows: list[dict[str, Any]]) -> int | None:
    best: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for row in rows:
        if row["actual_state"] == "READY":
            if current and row["frame_number"] != current[-1]["frame_number"] + 1:
                if len(current) > len(best):
                    best = current
                current = []
            current.append(row)
        else:
            if len(current) > len(best):
                best = current
            current = []
    if len(current) > len(best):
        best = current
    if not best:
        return None
    return int(round((best[0]["frame_number"] + best[-1]["frame_number"]) / 2))


def robust_quality(value: float, values: list[float], higher_is_better: bool) -> float:
    clean = [x for x in values if math.isfinite(x)]
    if not clean or not math.isfinite(value):
        return 0.0
    low, high = percentile(clean, 5), percentile(clean, 95)
    scaled = 0.5 if high <= low else float(np.clip((value - low) / (high - low), 0.0, 1.0))
    return scaled if higher_is_better else 1.0 - scaled


@dataclass(frozen=True)
class Config:
    smoothing_window: int
    consecutive_frames: int
    max_p_invalid: float
    sharpness_percentile: int
    motion_percentile: int
    sharpness_min: float
    motion_max: float


def select_temporal(
    event_rows: list[dict[str, Any]], config: Config, ready_threshold: float
) -> dict[str, Any] | None:
    ordered = sorted(event_rows, key=lambda row: row["frame_number"])
    smoothed = trailing_mean([row["p_ready"] for row in ordered], config.smoothing_window)
    consecutive = 0
    candidates: list[dict[str, Any]] = []
    sharp_values = [row["sharpness"] for row in ordered]
    motion_values = [row["motion"] for row in ordered]
    for row, smooth in zip(ordered, smoothed):
        confidence_ok = smooth >= ready_threshold and row["p_invalid"] <= config.max_p_invalid
        consecutive = consecutive + 1 if confidence_ok else 0
        quality_ok = row["sharpness"] >= config.sharpness_min and (
            not math.isfinite(row["motion"]) or row["motion"] <= config.motion_max
        )
        if confidence_ok and consecutive >= config.consecutive_frames and quality_ok:
            sharp_q = robust_quality(row["sharpness"], sharp_values, True)
            motion_q = robust_quality(row["motion"], motion_values, False)
            stability_q = min(consecutive / (2.0 * config.consecutive_frames), 1.0)
            score = 0.70 * smooth + 0.20 * sharp_q + 0.10 * stability_q
            candidates.append(
                {
                    **row,
                    "p_ready_smoothed": smooth,
                    "consecutive_acceptable": consecutive,
                    "sharpness_quality": sharp_q,
                    "motion_quality": motion_q,
                    "temporal_score": score,
                }
            )
    return max(candidates, key=lambda row: (row["temporal_score"], row["p_ready"], -row["frame_number"])) if candidates else None


def select_baseline(event_rows: list[dict[str, Any]], threshold: float | None) -> dict[str, Any] | None:
    candidates = event_rows if threshold is None else [row for row in event_rows if row["p_ready"] >= threshold]
    return max(candidates, key=lambda row: (row["p_ready"], -row["frame_number"])) if candidates else None


def evaluate_method(
    events: dict[str, list[dict[str, Any]]], selector, method: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selections: list[dict[str, Any]] = []
    positive = 0
    negative = 0
    success = 0
    false_selection = 0
    positive_selected = 0
    negative_selected = 0
    positive_no_selection = 0
    negative_no_selection = 0
    distances: list[int] = []
    for event_id in sorted(events):
        rows = events[event_id]
        has_ready = any(row["actual_state"] == "READY" for row in rows)
        positive += int(has_ready)
        negative += int(not has_ready)
        chosen = selector(rows)
        center = longest_ready_run_center(rows)
        if chosen is None:
            positive_no_selection += int(has_ready)
            negative_no_selection += int(not has_ready)
            selections.append(
                {
                    "method": method, "video_id": rows[0]["video_id"], "event_id": event_id,
                    "event_has_ready": has_ready, "selection_status": NO_FRAME,
                    "selected_frame_id": "", "selected_frame_number": "", "selected_actual_state": "",
                    "p_ready": "", "p_ready_smoothed": "", "sharpness": "", "motion": "",
                    "temporal_score": "", "ready_run_center_frame": center if center is not None else "",
                    "distance_to_ready_run_center_frames": "",
                }
            )
            continue
        correct = chosen["actual_state"] == "READY"
        positive_selected += int(has_ready)
        negative_selected += int(not has_ready)
        success += int(correct)
        false_selection += int(not correct)
        distance = abs(chosen["frame_number"] - center) if correct and center is not None else None
        if distance is not None:
            distances.append(distance)
        selections.append(
            {
                "method": method, "video_id": chosen["video_id"], "event_id": event_id,
                "event_has_ready": has_ready,
                "selection_status": "SUCCESS_READY" if correct else "FALSE_SELECTION",
                "selected_frame_id": chosen["frame_id"], "selected_frame_number": chosen["frame_number"],
                "selected_actual_state": chosen["actual_state"], "p_ready": chosen["p_ready"],
                "p_ready_smoothed": chosen.get("p_ready_smoothed", ""), "sharpness": chosen["sharpness"],
                "motion": chosen["motion"], "temporal_score": chosen.get("temporal_score", ""),
                "ready_run_center_frame": center if center is not None else "",
                "distance_to_ready_run_center_frames": distance if distance is not None else "",
                "resolved_image_path": chosen["resolved_image_path"],
            }
        )
    total = len(events)
    selected_count = success + false_selection
    metrics = {
        "method": method,
        "events_total": total,
        "positive_events": positive,
        "negative_events": negative,
        "successful_ready_selections": success,
        "false_selections": false_selection,
        "positive_events_no_selection": positive_no_selection,
        "negative_events_correctly_no_selection": negative_no_selection,
        "positive_event_coverage": positive_selected / positive if positive else 0.0,
        "successful_event_selection_rate": success / positive if positive else 0.0,
        "false_selection_rate_all_events": false_selection / total if total else 0.0,
        "negative_event_false_selection_rate": negative_selected / negative if negative else 0.0,
        "selected_frame_precision": success / selected_count if selected_count else 0.0,
        "no_suitable_frame_accuracy": negative_no_selection / negative if negative else 0.0,
        "median_distance_to_ready_run_center_frames": float(np.median(distances)) if distances else None,
        "mean_distance_to_ready_run_center_frames": float(np.mean(distances)) if distances else None,
    }
    return metrics, selections


def create_contact_sheet(selections: list[dict[str, Any]], output_path: Path, columns: int) -> None:
    chosen = [row for row in selections if row["selected_frame_id"]]
    if not chosen:
        return
    thumb_w, thumb_h, label_h = 260, 180, 54
    rows_count = math.ceil(len(chosen) / columns)
    canvas = Image.new("RGB", (columns * thumb_w, rows_count * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, row in enumerate(chosen):
        col, grid_row = index % columns, index // columns
        x, y = col * thumb_w, grid_row * (thumb_h + label_h)
        try:
            with Image.open(row["resolved_image_path"]) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w - 8, thumb_h - 8), Image.Resampling.LANCZOS)
                canvas.paste(image, (x + (thumb_w - image.width) // 2, y + (thumb_h - image.height) // 2))
        except OSError:
            draw.rectangle((x + 4, y + 4, x + thumb_w - 4, y + thumb_h - 4), outline="red", width=2)
        label = f"{row['event_id']} | {row['selected_frame_id']}\n{row['selection_status']} | state={row['selected_actual_state']}"
        draw.multiline_text((x + 5, y + thumb_h + 3), label, fill="black", font=font, spacing=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=92)


def main() -> int:
    args = parse_args()
    if not 0.0 <= args.minimum_positive_event_coverage <= 1.0:
        raise ValueError("--minimum-positive-event-coverage must be between 0 and 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    annotations, ann_fields = read_csv(args.annotations)
    predictions, pred_fields = read_csv(args.predictions)
    require_columns(ann_fields, {"video_id", "event_id", "frame_id", "state"}, "annotations")
    require_columns(
        pred_fields,
        {"video_id", "frame_id", "image_path", "actual_state", "p_invalid", "p_not_ready", "p_ready"},
        "predictions",
    )
    with args.threshold_json.open("r", encoding="utf-8") as handle:
        threshold_data = json.load(handle)
    if threshold_data.get("test_split_used") is not False:
        raise ValueError("Threshold metadata does not confirm test_split_used=false")
    ready_threshold = float(threshold_data["selected_threshold"])
    if not bool(threshold_data.get("gate_pass")):
        raise ValueError("Phase 3B threshold gate did not pass")

    joined, issues = validate_inputs(annotations, predictions, args.output_dir)
    blocking = [issue for issue in issues if issue["issue"] != ""]
    if blocking:
        counts = Counter(issue["issue"] for issue in blocking)
        print("Phase 4 stopped by annotation/prediction integrity checks.", file=sys.stderr)
        for name, count in sorted(counts.items()):
            print(f"  {name}: {count}", file=sys.stderr)
        print(f"Review: {args.output_dir / 'annotation_integrity_issues.csv'}", file=sys.stderr)
        return 2

    print(f"Validation frames: {len(joined)}")
    print(f"Validation videos: {', '.join(sorted({row['video_id'] for row in joined}))}")
    print(f"Frozen READY threshold: {ready_threshold:.2f}")
    print("Test split used: No")

    features = load_or_compute_features(
        joined, args.output_dir, args.frames_root, args.image_size, args.reuse_features
    )
    event_rows = [row for row in features if row["event_id"]]
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in event_rows:
        events[row["event_id"]].append(row)
    if not events:
        raise ValueError("No event-linked validation frames were found")

    ready_rows = [row for row in event_rows if row["actual_state"] == "READY"]
    ready_sharpness = [row["sharpness"] for row in ready_rows]
    ready_motion = [row["motion"] for row in ready_rows]
    configs: list[Config] = []
    for window in (3, 5):
        for consecutive in (2, 3):
            for max_invalid in (0.15, 0.25, 0.35):
                for sharp_q in (0, 5, 10, 15):
                    for motion_q in (85, 90, 95, 100):
                        configs.append(
                            Config(
                                smoothing_window=window,
                                consecutive_frames=consecutive,
                                max_p_invalid=max_invalid,
                                sharpness_percentile=sharp_q,
                                motion_percentile=motion_q,
                                sharpness_min=percentile(ready_sharpness, sharp_q),
                                motion_max=percentile(ready_motion, motion_q),
                            )
                        )

    tuning_rows: list[dict[str, Any]] = []
    selection_cache: dict[int, list[dict[str, Any]]] = {}
    for index, config in enumerate(configs):
        metrics, selections = evaluate_method(
            events,
            lambda rows, c=config: select_temporal(rows, c, ready_threshold),
            "temporal_selector",
        )
        row = {**config.__dict__, **metrics}
        row["coverage_gate_pass"] = metrics["positive_event_coverage"] >= args.minimum_positive_event_coverage
        tuning_rows.append(row)
        selection_cache[index] = selections

    eligible = [
        (index, row) for index, row in enumerate(tuning_rows) if row["coverage_gate_pass"]
    ]
    if not eligible:
        best_coverage = max(row["positive_event_coverage"] for row in tuning_rows)
        raise RuntimeError(
            f"No temporal configuration met minimum positive-event coverage "
            f"{args.minimum_positive_event_coverage:.2f}; best={best_coverage:.4f}."
        )
    best_index, best_tuning = max(
        eligible,
        key=lambda item: (
            item[1]["selected_frame_precision"],
            item[1]["successful_event_selection_rate"],
            item[1]["no_suitable_frame_accuracy"],
            -item[1]["false_selection_rate_all_events"],
            -item[1]["smoothing_window"],
            -item[1]["consecutive_frames"],
        ),
    )
    selected_config = configs[best_index]
    temporal_selections = selection_cache[best_index]

    argmax_metrics, argmax_selections = evaluate_method(
        events, lambda rows: select_baseline(rows, None), "single_frame_max_probability"
    )
    threshold_metrics, threshold_selections = evaluate_method(
        events, lambda rows: select_baseline(rows, ready_threshold), f"threshold_{ready_threshold:.2f}"
    )
    temporal_metrics, temporal_selections = evaluate_method(
        events,
        lambda rows: select_temporal(rows, selected_config, ready_threshold),
        "temporal_selector",
    )
    comparison = [argmax_metrics, threshold_metrics, temporal_metrics]
    phase4_gate_pass = (
        temporal_metrics["positive_event_coverage"] >= args.minimum_positive_event_coverage
        and temporal_metrics["selected_frame_precision"] >= threshold_metrics["selected_frame_precision"]
        and temporal_metrics["false_selections"] <= threshold_metrics["false_selections"]
        and temporal_metrics["no_suitable_frame_accuracy"] >= threshold_metrics["no_suitable_frame_accuracy"]
    )

    tuning_fields = list(tuning_rows[0].keys())
    write_csv(args.output_dir / "temporal_tuning_grid.csv", tuning_rows, tuning_fields)
    selection_fields = [
        "method", "video_id", "event_id", "event_has_ready", "selection_status",
        "selected_frame_id", "selected_frame_number", "selected_actual_state", "p_ready",
        "p_ready_smoothed", "sharpness", "motion", "temporal_score",
        "ready_run_center_frame", "distance_to_ready_run_center_frames", "resolved_image_path",
    ]
    all_selections = argmax_selections + threshold_selections + temporal_selections
    write_csv(args.output_dir / "event_selections_all_methods.csv", all_selections, selection_fields)
    write_csv(args.output_dir / "temporal_event_selections.csv", temporal_selections, selection_fields)
    write_csv(args.output_dir / "method_comparison.csv", comparison, list(comparison[0].keys()))

    selected_config_json = {
        "phase": "Phase 4 temporal selector validation tuning",
        "test_split_used": False,
        "validation_videos": sorted({row["video_id"] for row in features}),
        "validation_frames": len(features),
        "validation_events": len(events),
        "events_with_ready": sum(any(r["actual_state"] == "READY" for r in rows) for rows in events.values()),
        "events_without_ready": sum(not any(r["actual_state"] == "READY" for r in rows) for rows in events.values()),
        "frozen_ready_threshold": ready_threshold,
        "minimum_positive_event_coverage": args.minimum_positive_event_coverage,
        "selection_rule": {
            **selected_config.__dict__,
            "score": "0.70*p_ready_smoothed + 0.20*sharpness_quality + 0.10*stability_quality",
            "smoothing": "causal trailing mean, reset at each event",
            "quality_threshold_source": "percentiles of corrected validation READY frames",
        },
        "validation_metrics": temporal_metrics,
        "baseline_comparison": comparison,
        "phase4_gate_pass": phase4_gate_pass,
        "phase4_gate_rule": (
            "Temporal selector must meet minimum positive-event coverage and be no worse than "
            "the frozen-threshold baseline for selected-frame precision, false selections, and "
            "no-suitable-frame accuracy."
        ),
        "important_note": (
            "Distance is measured to the midpoint of the longest annotated READY run. "
            "It is a proxy, not distance to an expert-preferred frame."
        ),
        "next_action": (
            "Manually review temporal_event_selections.csv/contact sheet, then freeze Phase 4 "
            "settings before one-time test evaluation."
            if phase4_gate_pass
            else "Do not evaluate test yet. Review validation selections and adjust the Phase 4 rule/grid."
        ),
    }
    write_json(args.output_dir / "selected_temporal_config.json", selected_config_json)
    write_json(args.output_dir / "phase4_summary.json", selected_config_json)
    create_contact_sheet(
        temporal_selections,
        args.output_dir / "temporal_selected_frames_contact_sheet.jpg",
        args.contact_sheet_columns,
    )

    if args.copy_selected:
        selected_dir = args.output_dir / "selected_frames"
        selected_dir.mkdir(parents=True, exist_ok=True)
        for row in temporal_selections:
            if not row["selected_frame_id"]:
                continue
            source = Path(row["resolved_image_path"])
            destination = selected_dir / f"{row['event_id']}__{row['selected_frame_id']}{source.suffix.lower()}"
            shutil.copy2(source, destination)

    print("\nPhase 4 validation temporal tuning complete")
    print(f"Validation events: {len(events)}")
    print(f"Selected smoothing window: {selected_config.smoothing_window}")
    print(f"Selected consecutive frames: {selected_config.consecutive_frames}")
    print(f"Selected max INVALID probability: {selected_config.max_p_invalid:.2f}")
    print(f"Sharpness minimum: {selected_config.sharpness_min:.4f} (READY p{selected_config.sharpness_percentile})")
    print(f"Motion maximum: {selected_config.motion_max:.4f} (READY p{selected_config.motion_percentile})")
    print(f"Successful READY event selection rate: {temporal_metrics['successful_event_selection_rate']:.4f}")
    print(f"Selected-frame precision: {temporal_metrics['selected_frame_precision']:.4f}")
    print(f"No-suitable-frame accuracy: {temporal_metrics['no_suitable_frame_accuracy']:.4f}")
    print(f"False selections: {temporal_metrics['false_selections']}")
    print(f"Phase 4 gate passed: {phase4_gate_pass}")
    print(f"Outputs: {args.output_dir.resolve()}")
    print("The test split was not used.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)