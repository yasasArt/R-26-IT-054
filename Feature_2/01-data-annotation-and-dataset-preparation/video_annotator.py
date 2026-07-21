from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from dataclasses import dataclass

try:
    import cv2
except ImportError:
    print("OpenCV is not installed. Please install it using 'pip install opencv-python'.")
    cv2 = None


IDLE_SETUP = "IDLE_SETUP"
SEWING = "SEWING"
NORMAL_PIECE = "NORMAL_PIECE"
VALID_STATES = {IDLE_SETUP, SEWING}
MARK_REPLACEMENT_TOLERANCE_SEC = 0.10


# waitKeyEx values vary by operating system and OpenCV GUI backend.
LEFT_ARROW_CODES = {81, 65361, 2424832, 63234}
RIGHT_ARROW_CODES = {83, 65363, 2555904, 63235}


@dataclass(frozen=True)
class StateMark:
    time_sec: float
    state: str


@dataclass
class AnnotationSnapshot:
    marks: list[StateMark]
    annotated_until_sec: float


class AnnotationTimeline:
    """Editable state-transition timeline with single-level action history."""

    def __init__(self) -> None:
        self.marks: list[StateMark] = []
        self.annotated_until_sec = 0.0
        self._history: list[AnnotationSnapshot] = []

    def _remember(self) -> None:
        self._history.append(
            AnnotationSnapshot(list(self.marks), self.annotated_until_sec)
        )

    def note_reviewed_time(self, time_sec: float) -> None:
        self.annotated_until_sec = max(self.annotated_until_sec, time_sec)

    def set_state(self, time_sec: float, state: str) -> bool:
        if state not in VALID_STATES:
            raise ValueError(f"Unsupported state: {state}")

        time_sec = max(0.0, time_sec)
        candidate = StateMark(time_sec, state)
        updated = list(self.marks)

        nearest_index = next(
            (
                index
                for index, mark in enumerate(updated)
                if abs(mark.time_sec - time_sec)
                <= MARK_REPLACEMENT_TOLERANCE_SEC
            ),
            None,
        )
        if nearest_index is None:
            updated.append(candidate)
        else:
            updated[nearest_index] = candidate

        updated = self._normalise(updated)
        if updated == self.marks:
            return False

        self._remember()
        self.marks = updated
        self.note_reviewed_time(time_sec)
        return True

    def reset(self) -> bool:
        if not self.marks and self.annotated_until_sec == 0.0:
            return False
        self._remember()
        self.marks = []
        self.annotated_until_sec = 0.0
        return True

    def undo(self) -> bool:
        if not self._history:
            return False
        snapshot = self._history.pop()
        self.marks = snapshot.marks
        self.annotated_until_sec = snapshot.annotated_until_sec
        return True

    def state_at(self, time_sec: float) -> str | None:
        state = None
        for mark in self.marks:
            if mark.time_sec > time_sec:
                break
            state = mark.state
        return state

    def segments(self, video_end_sec: float) -> list[tuple[float, float, str]]:
        if not self.marks:
            return []

        end_limit = min(video_end_sec, max(self.annotated_until_sec, 0.0))
        rows: list[tuple[float, float, str]] = []
        for index, mark in enumerate(self.marks):
            if mark.time_sec >= end_limit:
                continue
            next_time = (
                self.marks[index + 1].time_sec
                if index + 1 < len(self.marks)
                else end_limit
            )
            segment_end = min(next_time, end_limit)
            if segment_end > mark.time_sec:
                rows.append((mark.time_sec, segment_end, mark.state))
        return rows

    def events(self) -> list[tuple[int, float, str]]:
        rows: list[tuple[int, float, str]] = []
        piece_no = 0
        for previous, current in zip(self.marks, self.marks[1:]):
            if previous.state == SEWING and current.state == IDLE_SETUP:
                piece_no += 1
                rows.append((piece_no, current.time_sec, NORMAL_PIECE))
        return rows

    @staticmethod
    def _normalise(marks: list[StateMark]) -> list[StateMark]:
        ordered = sorted(marks, key=lambda mark: mark.time_sec)
        normalised: list[StateMark] = []
        for mark in ordered:
            if normalised and normalised[-1].state == mark.state:
                continue
            normalised.append(mark)
        return normalised


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Annotate IDLE_SETUP and SEWING states in one video."
    )
    parser.add_argument("video", type=Path, help="Path to the video to annotate")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for the CSV files. Default: "
            "<video directory>/annotations/<video name>/"
        ),
    )
    return parser.parse_args()


def format_time(seconds: float) -> str:
    total_milliseconds = max(0, round(seconds * 1000))
    minutes, milliseconds = divmod(total_milliseconds, 60_000)
    hours, minutes = divmod(minutes, 60)
    seconds_part, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}.{milliseconds:03d}"


def put_text(
    frame,
    text: str,
    line: int,
    color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    position = (18, 32 + line * 27)
    cv2.putText( # type: ignore
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX, # type: ignore
        0.65,
        (0, 0, 0),
        4,
        cv2.LINE_AA, # type: ignore
    )
    cv2.putText( # type: ignore
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX, # type: ignore
        0.65,
        color,
        2,
        cv2.LINE_AA, # type: ignore
    )


def draw_overlay(
    frame,
    video_name: str,
    current_sec: float,
    duration_sec: float,
    timeline: AnnotationTimeline,
    paused: bool,
    message: str,
) -> None:
    state = timeline.state_at(current_sec) or "UNLABELLED"
    state_color = (
        (0, 220, 0)
        if state == SEWING
        else (0, 200, 255) if state == IDLE_SETUP else (180, 180, 180)
    )
    put_text(frame, video_name, 0)
    put_text(
        frame,
        f"{format_time(current_sec)} / {format_time(duration_sec)}",
        1,
    )
    put_text(frame, f"State: {state}", 2, state_color)
    put_text(frame, f"Completed pieces: {len(timeline.events())}", 3)
    put_text(frame, "PAUSED" if paused else "PLAYING", 4, (255, 220, 0))
    put_text(
        frame,
        "S: sewing | I: idle/setup | arrows: +/-3s | Y: undo",
        5,
    )
    put_text(frame, "Space: play/pause | R: reset | Q: save and quit", 6)
    if message:
        put_text(frame, message, 7, (80, 255, 255))


def save_annotations(
    timeline: AnnotationTimeline,
    video_path: Path,
    output_dir: Path,
    duration_sec: float,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    segment_path = output_dir / "segment_annotation.csv"
    event_path = output_dir / "events.csv"

    with segment_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["video_name", "start_time_sec", "end_time_sec", "state"])
        for start, end, state in timeline.segments(duration_sec):
            writer.writerow(
                [video_path.name, f"{start:.3f}", f"{end:.3f}", state]
            )

    with event_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["video_name", "piece_no", "event_time_sec", "event_type"]
        )
        for piece_no, event_time, event_type in timeline.events():
            writer.writerow(
                [video_path.name, piece_no, f"{event_time:.3f}", event_type]
            )

    return segment_path, event_path


def main() -> int:
    args = parse_args()
    if cv2 is None:
        print(
            "OpenCV is required. Install it with: pip install opencv-python",
            file=sys.stderr,
        )
        return 2

    video_path = args.video.expanduser().resolve()
    if not video_path.is_file():
        print(f"Video not found: {video_path}", file=sys.stderr)
        return 2

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else video_path.parent / "annotations" / video_path.stem
    )

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        print(f"Could not open video: {video_path}", file=sys.stderr)
        return 2

    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        print("The video has invalid FPS or frame-count metadata.", file=sys.stderr)
        return 2

    duration_sec = frame_count / fps
    final_frame_index = max(0, frame_count - 1)
    current_frame_index = 0
    paused = True
    timeline = AnnotationTimeline()
    message = "Paused at the start. Press I or S to add the first state."
    window_name = f"Garment Video Annotator - {video_path.name}"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            current_frame_index = max(
                0, min(current_frame_index, final_frame_index)
            )
            capture.set(cv2.CAP_PROP_POS_FRAMES, current_frame_index)
            ok, frame = capture.read()
            if not ok:
                message = "Could not read this frame."
                paused = True
                current_frame_index = max(0, current_frame_index - 1)
                continue

            current_sec = current_frame_index / fps
            timeline.note_reviewed_time(min(duration_sec, current_sec + 1.0 / fps))
            display = frame.copy()
            draw_overlay(
                display,
                video_path.name,
                current_sec,
                duration_sec,
                timeline,
                paused,
                message,
            )
            cv2.imshow(window_name, display)

            delay_ms = 30 if paused else max(1, round(1000 / fps))
            key = cv2.waitKeyEx(delay_ms)

            if key != -1:
                char_code = key & 0xFF
                message = ""

                if char_code in (ord("s"), ord("S")):
                    changed = timeline.set_state(current_sec, SEWING)
                    message = (
                        f"SEWING starts at {format_time(current_sec)}"
                        if changed
                        else "SEWING is already active here."
                    )
                elif char_code in (ord("i"), ord("I")):
                    changed = timeline.set_state(current_sec, IDLE_SETUP)
                    message = (
                        f"IDLE_SETUP starts at {format_time(current_sec)}"
                        if changed
                        else "IDLE_SETUP is already active here."
                    )
                elif char_code in (ord("y"), ord("Y")):
                    message = (
                        "Previous annotation action restored."
                        if timeline.undo()
                        else "Nothing to undo."
                    )
                elif char_code in (ord("r"), ord("R")):
                    message = (
                        "All annotations reset. Press Y to undo the reset."
                        if timeline.reset()
                        else "Annotations are already empty."
                    )
                elif char_code == ord(" "):
                    paused = not paused
                    message = "Paused." if paused else "Playing."
                elif char_code in (ord("q"), ord("Q")):
                    segment_path, event_path = save_annotations(
                        timeline,
                        video_path,
                        output_dir,
                        duration_sec,
                    )
                    print("Annotations saved:")
                    print(f"  {segment_path}")
                    print(f"  {event_path}")
                    return 0
                elif char_code == 27:  # Escape
                    print("Exited without saving.")
                    return 1
                elif key in LEFT_ARROW_CODES:
                    current_frame_index -= round(3 * fps)
                    current_frame_index = max(0, current_frame_index)
                    message = "Moved backward 3 seconds."
                    continue
                elif key in RIGHT_ARROW_CODES:
                    current_frame_index += round(3 * fps)
                    current_frame_index = min(final_frame_index, current_frame_index)
                    message = "Moved forward 3 seconds."
                    continue

            if not paused:
                if current_frame_index >= final_frame_index:
                    paused = True
                    message = "End of video. Press Q to save."
                else:
                    current_frame_index += 1
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())