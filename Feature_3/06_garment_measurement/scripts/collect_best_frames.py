import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import pandas as pd


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_ROOT = PROJECT_ROOT.parent

SOURCE_DIR = (
    VIDEOS_ROOT
    / "02_model_development"
    / "best_frame_selector"
    / "outputs"
    / "sample_run"
    / "selected_frames"
)

EXTRACTION_RESULTS_PATH = (
    VIDEOS_ROOT
    / "02_model_development"
    / "best_frame_selector"
    / "outputs"
    / "sample_run"
    / "extraction_results.csv"
)

EXTRACTION_SUMMARY_PATH = (
    VIDEOS_ROOT
    / "02_model_development"
    / "best_frame_selector"
    / "outputs"
    / "sample_run"
    / "extraction_summary.json"
)

DESTINATION_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw_best_frames"
)

MANIFEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "best_frames_manifest.csv"
)

SUMMARY_PATH = (
    PROJECT_ROOT
    / "data"
    / "best_frames_collection_summary.json"
)


# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------

VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png"
}

FILENAME_PATTERN = re.compile(
    r"^(v\d+)_event_(\d+)_best\.(jpg|jpeg|png)$",
    re.IGNORECASE
)


def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def read_image_information(image_path):
    image = cv2.imread(str(image_path))

    if image is None:
        return None

    height, width = image.shape[:2]

    if len(image.shape) == 2:
        channels = 1
    else:
        channels = image.shape[2]

    return {
        "width_px": int(width),
        "height_px": int(height),
        "channels": int(channels)
    }


def extract_identifiers(file_name):
    match = FILENAME_PATTERN.match(file_name)

    if match is None:
        return None

    video_id = match.group(1).lower()
    event_number = int(match.group(2))

    event_id = (
        f"{video_id}_E{event_number:03d}"
    )

    return {
        "video_id": video_id,
        "event_number": event_number,
        "event_id": event_id
    }


def read_extraction_results():
    if not EXTRACTION_RESULTS_PATH.exists():
        return {
            "exists": False,
            "row_count": 0,
            "columns": []
        }

    try:
        dataframe = pd.read_csv(
            EXTRACTION_RESULTS_PATH,
            encoding="utf-8-sig"
        )

        return {
            "exists": True,
            "row_count": int(len(dataframe)),
            "columns": list(dataframe.columns)
        }

    except Exception as error:
        return {
            "exists": True,
            "row_count": 0,
            "columns": [],
            "read_error": str(error)
        }


def read_extraction_summary():
    if not EXTRACTION_SUMMARY_PATH.exists():
        return {
            "exists": False
        }

    try:
        with EXTRACTION_SUMMARY_PATH.open(
            "r",
            encoding="utf-8-sig"
        ) as file:
            data = json.load(file)

        return {
            "exists": True,
            "content": data
        }

    except Exception as error:
        return {
            "exists": True,
            "read_error": str(error)
        }


def collect_best_frames():
    print("==========================================")
    print(" Best-Frame Collection and Verification")
    print("==========================================")

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Source folder: {SOURCE_DIR}")
    print(f"Destination folder: {DESTINATION_DIR}")

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(
            "Best-frame source folder එක සොයාගත "
            f"නොහැක:\n{SOURCE_DIR}"
        )

    DESTINATION_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    image_paths = sorted(
        path
        for path in SOURCE_DIR.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower()
            in VALID_EXTENSIONS
        )
    )

    print(f"\nSource images found: {len(image_paths)}")

    if not image_paths:
        raise RuntimeError(
            "Source folder එකේ images නැහැ."
        )

    manifest_rows = []
    hash_to_file_name = {}

    copied_count = 0
    already_present_count = 0
    duplicate_count = 0
    invalid_name_count = 0
    corrupted_count = 0
    conflict_count = 0

    for index, source_path in enumerate(
        image_paths,
        start=1
    ):
        print(
            f"[{index:03d}/{len(image_paths):03d}] "
            f"{source_path.name}"
        )

        identifiers = extract_identifiers(
            source_path.name
        )

        base_row = {
            "source_file_name": source_path.name,
            "source_path": str(source_path.resolve()),
            "destination_path": "",
            "video_id": "",
            "event_id": "",
            "event_number": "",
            "width_px": "",
            "height_px": "",
            "channels": "",
            "file_size_bytes": (
                source_path.stat().st_size
            ),
            "sha256": "",
            "status": "",
            "duplicate_of": "",
            "usable_for_segmentation": False
        }

        if identifiers is None:
            base_row["status"] = (
                "INVALID_FILENAME_SKIPPED"
            )

            invalid_name_count += 1
            manifest_rows.append(base_row)
            continue

        base_row.update(identifiers)

        image_information = read_image_information(
            source_path
        )

        if image_information is None:
            base_row["status"] = (
                "CORRUPTED_IMAGE_SKIPPED"
            )

            corrupted_count += 1
            manifest_rows.append(base_row)
            continue

        base_row.update(image_information)

        file_hash = calculate_sha256(source_path)
        base_row["sha256"] = file_hash

        if file_hash in hash_to_file_name:
            base_row["status"] = (
                "DUPLICATE_CONTENT_SKIPPED"
            )
            base_row["duplicate_of"] = (
                hash_to_file_name[file_hash]
            )

            duplicate_count += 1
            manifest_rows.append(base_row)
            continue

        hash_to_file_name[file_hash] = (
            source_path.name
        )

        destination_path = (
            DESTINATION_DIR
            / source_path.name
        )

        base_row["destination_path"] = str(
            destination_path.resolve()
        )

        if destination_path.exists():
            existing_hash = calculate_sha256(
                destination_path
            )

            if existing_hash == file_hash:
                base_row["status"] = (
                    "ALREADY_PRESENT"
                )
                base_row[
                    "usable_for_segmentation"
                ] = True

                already_present_count += 1

            else:
                base_row["status"] = (
                    "NAME_CONFLICT_SKIPPED"
                )

                conflict_count += 1

        else:
            shutil.copy2(
                source_path,
                destination_path
            )

            base_row["status"] = "COPIED"
            base_row[
                "usable_for_segmentation"
            ] = True

            copied_count += 1

        manifest_rows.append(base_row)

    manifest_dataframe = pd.DataFrame(
        manifest_rows
    )

    manifest_dataframe.to_csv(
        MANIFEST_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    valid_rows = manifest_dataframe[
        manifest_dataframe[
            "usable_for_segmentation"
        ] == True
    ].copy()

    resolution_counter = Counter(
        f"{int(row.width_px)}x{int(row.height_px)}"
        for row in valid_rows.itertuples()
    )

    video_counter = Counter(
        str(video_id)
        for video_id
        in valid_rows["video_id"].tolist()
    )

    extraction_results_information = (
        read_extraction_results()
    )

    extraction_summary_information = (
        read_extraction_summary()
    )

    summary = {
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "project_root": str(PROJECT_ROOT.resolve()),
        "source_directory": str(
            SOURCE_DIR.resolve()
        ),
        "destination_directory": str(
            DESTINATION_DIR.resolve()
        ),
        "source_images_found": len(image_paths),
        "copied_images": copied_count,
        "already_present_images": (
            already_present_count
        ),
        "usable_unique_images": int(
            len(valid_rows)
        ),
        "duplicate_content_images": (
            duplicate_count
        ),
        "invalid_filename_images": (
            invalid_name_count
        ),
        "corrupted_images": corrupted_count,
        "name_conflicts": conflict_count,
        "video_count": len(video_counter),
        "images_per_video": dict(
            sorted(video_counter.items())
        ),
        "resolutions": dict(
            sorted(resolution_counter.items())
        ),
        "manifest_path": str(
            MANIFEST_PATH.resolve()
        ),
        "extraction_results": (
            extraction_results_information
        ),
        "extraction_summary": (
            extraction_summary_information
        )
    }

    with SUMMARY_PATH.open(
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
    print(" Collection Summary")
    print("==========================================")

    print(
        f"Source images: {len(image_paths)}"
    )
    print(f"Copied: {copied_count}")
    print(
        f"Already present: "
        f"{already_present_count}"
    )
    print(
        f"Usable unique images: "
        f"{len(valid_rows)}"
    )
    print(f"Duplicates skipped: {duplicate_count}")
    print(
        f"Invalid filenames skipped: "
        f"{invalid_name_count}"
    )
    print(
        f"Corrupted images skipped: "
        f"{corrupted_count}"
    )
    print(f"Name conflicts: {conflict_count}")
    print(f"Videos represented: {len(video_counter)}")

    print("\nResolutions:")

    for resolution, count in sorted(
        resolution_counter.items()
    ):
        print(f"  {resolution}: {count}")

    print(f"\nManifest saved: {MANIFEST_PATH}")
    print(f"Summary saved: {SUMMARY_PATH}")

    if (
        corrupted_count == 0
        and conflict_count == 0
        and len(valid_rows) > 0
    ):
        print(
            "\nSTEP 2 SUCCESSFUL — "
            "Best frames are ready."
        )
    else:
        print(
            "\nSTEP 2 COMPLETED WITH WARNINGS — "
            "Check the manifest."
        )


if __name__ == "__main__":
    collect_best_frames()