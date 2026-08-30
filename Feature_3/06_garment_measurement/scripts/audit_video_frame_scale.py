import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_ROOT = PROJECT_ROOT.parent

ORIGINAL_VIDEOS_DIR = (
    VIDEOS_ROOT
    / "02_model_development"
    / "best_frame_selector"
    / "sample_videos"
)

MANIFEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "best_frames_manifest.csv"
)

AUDIT_CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "video_frame_scale_audit.csv"
)

AUDIT_SUMMARY_PATH = (
    PROJECT_ROOT
    / "data"
    / "video_frame_scale_audit_summary.json"
)

VALID_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv"
}


def decode_fourcc(fourcc_value):
    try:
        return "".join(
            chr(
                (int(fourcc_value) >> (8 * index))
                & 0xFF
            )
            for index in range(4)
        ).strip()
    except Exception:
        return "UNKNOWN"


def inspect_video(video_path):
    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        return {
            "readable": False,
            "error": "Video could not be opened"
        }

    width = int(
        capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    )
    height = int(
        capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )
    fps = float(
        capture.get(cv2.CAP_PROP_FPS)
    )
    frame_count = int(
        capture.get(cv2.CAP_PROP_FRAME_COUNT)
    )
    fourcc = capture.get(
        cv2.CAP_PROP_FOURCC
    )

    success, first_frame = capture.read()
    capture.release()

    if success and first_frame is not None:
        decoded_height, decoded_width = (
            first_frame.shape[:2]
        )
    else:
        decoded_width = 0
        decoded_height = 0

    if fps > 0:
        duration_seconds = frame_count / fps
    else:
        duration_seconds = 0.0

    return {
        "readable": True,
        "reported_width_px": width,
        "reported_height_px": height,
        "decoded_width_px": int(decoded_width),
        "decoded_height_px": int(decoded_height),
        "fps": round(fps, 4),
        "frame_count": frame_count,
        "duration_seconds": round(
            duration_seconds,
            3
        ),
        "codec": decode_fourcc(fourcc)
    }


def find_original_videos():
    video_map = {}
    duplicate_video_ids = defaultdict(list)

    if not ORIGINAL_VIDEOS_DIR.exists():
        raise FileNotFoundError(
            "Original video folder එක සොයාගත "
            f"නොහැක:\n{ORIGINAL_VIDEOS_DIR}"
        )

    video_paths = sorted(
        path
        for path in ORIGINAL_VIDEOS_DIR.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower()
            in VALID_VIDEO_EXTENSIONS
        )
    )

    for video_path in video_paths:
        video_id = video_path.stem.lower()

        if video_id in video_map:
            duplicate_video_ids[video_id].append(
                str(video_path.resolve())
            )
        else:
            video_map[video_id] = video_path

    return (
        video_map,
        duplicate_video_ids,
        video_paths
    )


def relative_difference(value_one, value_two):
    denominator = max(
        abs(value_one),
        abs(value_two),
        1e-9
    )

    return abs(
        value_one - value_two
    ) / denominator


def classify_scale(
    frame_width,
    frame_height,
    video_width,
    video_height
):
    if min(
        frame_width,
        frame_height,
        video_width,
        video_height
    ) <= 0:
        return {
            "scale_status": "INVALID_DIMENSIONS",
            "scale_x": None,
            "scale_y": None,
            "scale_difference_percent": None,
            "aspect_ratio_difference_percent": None
        }

    if (
        frame_width == video_width
        and frame_height == video_height
    ):
        return {
            "scale_status": "ORIGINAL_RESOLUTION",
            "scale_x": 1.0,
            "scale_y": 1.0,
            "scale_difference_percent": 0.0,
            "aspect_ratio_difference_percent": 0.0
        }

    scale_x = video_width / frame_width
    scale_y = video_height / frame_height

    frame_aspect = frame_width / frame_height
    video_aspect = video_width / video_height

    direct_scale_difference = (
        relative_difference(scale_x, scale_y)
        * 100
    )

    direct_aspect_difference = (
        relative_difference(
            frame_aspect,
            video_aspect
        )
        * 100
    )

    if (
        direct_scale_difference <= 2.0
        and direct_aspect_difference <= 2.0
    ):
        return {
            "scale_status": "UNIFORM_RESIZE",
            "scale_x": round(scale_x, 6),
            "scale_y": round(scale_y, 6),
            "scale_difference_percent": round(
                direct_scale_difference,
                4
            ),
            "aspect_ratio_difference_percent": round(
                direct_aspect_difference,
                4
            )
        }

    rotated_scale_x = video_height / frame_width
    rotated_scale_y = video_width / frame_height

    rotated_frame_aspect = (
        frame_width / frame_height
    )
    rotated_video_aspect = (
        video_height / video_width
    )

    rotated_scale_difference = (
        relative_difference(
            rotated_scale_x,
            rotated_scale_y
        )
        * 100
    )

    rotated_aspect_difference = (
        relative_difference(
            rotated_frame_aspect,
            rotated_video_aspect
        )
        * 100
    )

    if (
        rotated_scale_difference <= 2.0
        and rotated_aspect_difference <= 2.0
    ):
        return {
            "scale_status": (
                "ROTATED_UNIFORM_RESIZE"
            ),
            "scale_x": round(
                rotated_scale_x,
                6
            ),
            "scale_y": round(
                rotated_scale_y,
                6
            ),
            "scale_difference_percent": round(
                rotated_scale_difference,
                4
            ),
            "aspect_ratio_difference_percent": round(
                rotated_aspect_difference,
                4
            )
        }

    return {
        "scale_status": (
            "CROP_OR_NON_UNIFORM_RESIZE"
        ),
        "scale_x": round(scale_x, 6),
        "scale_y": round(scale_y, 6),
        "scale_difference_percent": round(
            direct_scale_difference,
            4
        ),
        "aspect_ratio_difference_percent": round(
            direct_aspect_difference,
            4
        )
    }


def main():
    print("==========================================")
    print(" Video and Best-Frame Scale Audit")
    print("==========================================")

    print(f"Original videos: {ORIGINAL_VIDEOS_DIR}")
    print(f"Manifest: {MANIFEST_PATH}")

    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest එක සොයාගත නොහැක:\n"
            f"{MANIFEST_PATH}"
        )

    manifest = pd.read_csv(
        MANIFEST_PATH,
        encoding="utf-8-sig",
        dtype={
            "video_id": str,
            "event_id": str
        }
    )

    manifest = manifest[
        manifest["usable_for_segmentation"]
        .astype(str)
        .str.lower()
        .eq("true")
    ].copy()

    (
        video_map,
        duplicate_video_ids,
        all_video_paths
    ) = find_original_videos()

    print(
        f"Original video files found: "
        f"{len(all_video_paths)}"
    )
    print(
        f"Usable best frames: {len(manifest)}"
    )

    video_information_cache = {}
    audit_rows = []

    for index, row in enumerate(
        manifest.itertuples(),
        start=1
    ):
        video_id = str(row.video_id).lower()

        print(
            f"[{index:03d}/{len(manifest):03d}] "
            f"{row.source_file_name}"
        )

        audit_row = {
            "video_id": video_id,
            "event_id": row.event_id,
            "best_frame_file": (
                row.source_file_name
            ),
            "best_frame_width_px": int(
                float(row.width_px)
            ),
            "best_frame_height_px": int(
                float(row.height_px)
            ),
            "original_video_path": "",
            "video_width_px": "",
            "video_height_px": "",
            "video_fps": "",
            "video_frame_count": "",
            "video_duration_seconds": "",
            "video_codec": "",
            "scale_x": "",
            "scale_y": "",
            "scale_difference_percent": "",
            "aspect_ratio_difference_percent": "",
            "scale_status": ""
        }

        if video_id not in video_map:
            audit_row["scale_status"] = (
                "ORIGINAL_VIDEO_NOT_FOUND"
            )
            audit_rows.append(audit_row)
            continue

        video_path = video_map[video_id]

        if video_id not in video_information_cache:
            video_information_cache[video_id] = (
                inspect_video(video_path)
            )

        video_information = (
            video_information_cache[video_id]
        )

        audit_row["original_video_path"] = str(
            video_path.resolve()
        )

        if not video_information["readable"]:
            audit_row["scale_status"] = (
                "ORIGINAL_VIDEO_UNREADABLE"
            )
            audit_rows.append(audit_row)
            continue

        video_width = video_information[
            "decoded_width_px"
        ]

        video_height = video_information[
            "decoded_height_px"
        ]

        if video_width <= 0 or video_height <= 0:
            video_width = video_information[
                "reported_width_px"
            ]
            video_height = video_information[
                "reported_height_px"
            ]

        audit_row.update({
            "video_width_px": video_width,
            "video_height_px": video_height,
            "video_fps": video_information["fps"],
            "video_frame_count": (
                video_information["frame_count"]
            ),
            "video_duration_seconds": (
                video_information[
                    "duration_seconds"
                ]
            ),
            "video_codec": (
                video_information["codec"]
            )
        })

        scale_result = classify_scale(
            frame_width=audit_row[
                "best_frame_width_px"
            ],
            frame_height=audit_row[
                "best_frame_height_px"
            ],
            video_width=video_width,
            video_height=video_height
        )

        audit_row.update(scale_result)
        audit_rows.append(audit_row)

    audit_dataframe = pd.DataFrame(audit_rows)

    AUDIT_CSV_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    audit_dataframe.to_csv(
        AUDIT_CSV_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    status_counter = Counter(
        audit_dataframe[
            "scale_status"
        ].tolist()
    )

    video_resolution_counter = Counter(
        (
            f"{row.video_width_px}"
            f"x{row.video_height_px}"
        )
        for row in audit_dataframe.itertuples()
        if str(row.video_width_px) != ""
    )

    frame_resolutions_by_video = (
        audit_dataframe.groupby("video_id")
        .apply(
            lambda group: sorted(
                set(
                    zip(
                        group[
                            "best_frame_width_px"
                        ],
                        group[
                            "best_frame_height_px"
                        ]
                    )
                )
            ),
            include_groups=False
        )
        .to_dict()
    )

    videos_with_multiple_frame_resolutions = {
        video_id: [
            f"{width}x{height}"
            for width, height in resolutions
        ]
        for video_id, resolutions
        in frame_resolutions_by_video.items()
        if len(resolutions) > 1
    }

    summary = {
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "original_videos_directory": str(
            ORIGINAL_VIDEOS_DIR.resolve()
        ),
        "original_video_files_found": len(
            all_video_paths
        ),
        "usable_best_frames_audited": int(
            len(audit_dataframe)
        ),
        "scale_status_counts": dict(
            sorted(status_counter.items())
        ),
        "video_resolution_counts_by_frame": dict(
            sorted(video_resolution_counter.items())
        ),
        "videos_with_multiple_best_frame_resolutions": (
            videos_with_multiple_frame_resolutions
        ),
        "duplicate_video_ids": dict(
            duplicate_video_ids
        ),
        "audit_csv_path": str(
            AUDIT_CSV_PATH.resolve()
        )
    }

    with AUDIT_SUMMARY_PATH.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\n==========================================")
    print(" Audit Summary")
    print("==========================================")

    print(
        f"Best frames audited: "
        f"{len(audit_dataframe)}"
    )

    print("\nScale status counts:")

    for status, count in sorted(
        status_counter.items()
    ):
        print(f"  {status}: {count}")

    print(
        "\nVideos with multiple best-frame "
        "resolutions:"
    )

    if videos_with_multiple_frame_resolutions:
        for video_id, resolutions in sorted(
            videos_with_multiple_frame_resolutions.items()
        ):
            print(
                f"  {video_id}: "
                f"{', '.join(resolutions)}"
            )
    else:
        print("  None")

    print(f"\nAudit CSV: {AUDIT_CSV_PATH}")
    print(
        f"Audit summary: {AUDIT_SUMMARY_PATH}"
    )

    dangerous_statuses = {
        "CROP_OR_NON_UNIFORM_RESIZE",
        "ORIGINAL_VIDEO_NOT_FOUND",
        "ORIGINAL_VIDEO_UNREADABLE",
        "INVALID_DIMENSIONS"
    }

    dangerous_count = sum(
        count
        for status, count
        in status_counter.items()
        if status in dangerous_statuses
    )

    if dangerous_count == 0:
        print(
            "\nSTEP 3 PASSED — "
            "Frame scaling is recoverable."
        )
    else:
        print(
            "\nSTEP 3 NEEDS REVIEW — "
            "Some frame scales cannot be "
            "recovered safely."
        )


if __name__ == "__main__":
    main()