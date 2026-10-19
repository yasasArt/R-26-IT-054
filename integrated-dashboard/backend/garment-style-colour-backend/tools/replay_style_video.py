"""Replay a recorded folding-table video through the live style engine.

Use this to measure the style detector on real recordings without a webcam,
for example while tuning thresholds or preparing evaluation results:

    backend\\.venv\\Scripts\\python.exe backend\\garment-style-colour-backend\\tools\\replay_style_video.py ^
        "D:\\Style and colour videos\\videos\\shuffled videos\\v10.mp4" --calibrate-at 11 --out replay_v10

The engine needs a picture of the empty folding zone. In the live app it
learns this automatically when the camera starts (or when the operator
presses "Re-learn empty table"). For a recording that starts with a garment
already on the table, pass --calibrate-at with a time (seconds) at which the
table is empty.

Outputs: a timeline of state changes, every capture (time, style, confidence,
agreement) and, with --out, the captured crops plus an optional annotated
video (--save-video).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from style_engine import EngineConfig, StyleCaptureEngine, YoloStyleClassifier  # noqa: E402

DEFAULT_MODEL = BACKEND_DIR.parents[1] / "models" / "garment-style-colour" / "best.pt"

STATE_COLOURS = {
    "CALIBRATING": (200, 200, 200),
    "EMPTY": (180, 180, 180),
    "DETECTING": (0, 165, 255),
    "ANALYSING": (0, 255, 255),
    "UNCERTAIN": (0, 120, 255),
    "CAPTURED": (0, 220, 0),
    "WAITING_REMOVAL": (255, 0, 255),
}


def annotate(frame, result):
    out = frame.copy()
    if result.roi:
        x1, y1, x2, y2 = result.roi
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 100, 0), 2)
    colour = STATE_COLOURS.get(result.state, (255, 255, 255))
    if result.box:
        x1, y1, x2, y2 = result.box
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
        if result.style:
            cv2.putText(out, f"{result.style} {result.confidence or 0:.0f}%", (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    cv2.putText(out, f"{result.state}: {result.detail}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--fps", type=float, default=12.0, help="Frames per second the engine processes (default 12, a typical CPU rate).")
    parser.add_argument("--width", type=int, default=640, help="Resize frames to this width, like a 640x480 webcam (default 640).")
    parser.add_argument("--calibrate-at", type=float, default=None, help="Learn the empty table from the frame at this time (seconds).")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--out", type=Path, default=None, help="Folder for captured crops and summary.json.")
    parser.add_argument("--save-video", action="store_true", help="Also write an annotated MP4 into --out.")
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(str(args.model))
    classifier = YoloStyleClassifier(model, imgsz=args.imgsz)
    engine = StyleCaptureEngine(classifier, classifier.class_names, EngineConfig.from_env())

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        print(f"Could not open {args.video}")
        return 1
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(source_fps / args.fps)))

    def resize(frame):
        height = int(frame.shape[0] * args.width / frame.shape[1])
        return cv2.resize(frame, (args.width, height), interpolation=cv2.INTER_AREA)

    clock = 0.0
    if args.calibrate_at is not None:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(args.calibrate_at * source_fps))
        ok, frame = capture.read()
        if not ok:
            print("Could not read the calibration frame.")
            return 1
        frame = resize(frame)
        for _ in range(int(args.fps * 2)):
            engine.process(frame, clock)
            clock += 1.0 / args.fps
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        engine._empty_since = clock - 10  # the calibration frame was an empty table

    writer = None
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    captures = []
    last_state = None
    index = -1
    while True:
        ok, frame = capture.read()
        index += 1
        if not ok:
            break
        if index % step:
            continue
        frame = resize(frame)
        video_time = index / source_fps
        result = engine.process(frame, clock + video_time)

        if result.state != last_state:
            print(f"{video_time:7.1f}s  {result.state:<16} {result.detail}")
            last_state = result.state
        if result.capture is not None:
            cap = result.capture
            entry = {
                "time_s": round(video_time, 2),
                "style": cap.style,
                "confidence": round(cap.confidence * 100, 1),
                "agreement": round(cap.agreement * 100, 1),
                "class_scores": cap.class_scores,
            }
            captures.append(entry)
            print(f"{video_time:7.1f}s  >>> CAPTURE {cap.style} {entry['confidence']}% (agreement {entry['agreement']}%)")
            if args.out:
                cv2.imwrite(str(args.out / f"capture_{len(captures):02d}_{video_time:06.1f}s_{cap.style}.jpg"), cap.image)

        if args.out and args.save_video:
            annotated = annotate(frame, result)
            if writer is None:
                h, w = annotated.shape[:2]
                writer = cv2.VideoWriter(str(args.out / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w, h))
            writer.write(annotated)

    if writer is not None:
        writer.release()
    print(f"\n{len(captures)} capture(s) from {args.video.name}")
    if args.out:
        (args.out / "summary.json").write_text(json.dumps({"video": str(args.video), "captures": captures}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
