from pathlib import Path
import random
import shutil
import csv

# Replace these paths with your three actual folder paths
source_folders = [
    Path("./Shirts"),
    Path("./T-Shirts"),
    Path("./trousers"),
]

# Destination folder
output_folder = Path("./shuffled videos")

# Supported video extensions
video_extensions = {
    ".mp4", ".mkv", ".avi", ".mov",
    ".wmv", ".flv", ".webm", ".m4v"
}

# A fixed seed makes the shuffle reproducible
random.seed(42)

output_folder.mkdir(parents=True, exist_ok=True)

videos = []

for folder in source_folders:
    if not folder.exists():
        print(f"Folder not found: {folder}")
        continue

    # Use rglob("*") to include videos inside subfolders
    for file_path in folder.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in video_extensions:
            videos.append(file_path)

print(f"Found {len(videos)} videos.")

# Shuffle all collected videos
random.shuffle(videos)

# Number formatting: v01 for fewer than 100 videos,
# v001 if there are 100 or more
number_width = max(2, len(str(len(videos))))

manifest_rows = []

for index, source_path in enumerate(videos, start=1):
    new_name = f"v{index:0{number_width}d}{source_path.suffix.lower()}"
    destination_path = output_folder / new_name

    # Copy without modifying the original video
    shutil.copy2(source_path, destination_path)

    manifest_rows.append({
        "new_name": new_name,
        "original_name": source_path.name,
        "original_path": str(source_path),
    })

    print(f"{source_path.name} -> {new_name}")

# Save the original-to-new filename mapping
manifest_path = output_folder / "video_mapping.csv"

with manifest_path.open("w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(
        csv_file,
        fieldnames=["new_name", "original_name", "original_path"]
    )
    writer.writeheader()
    writer.writerows(manifest_rows)

print("\nCompleted successfully.")
print(f"Shuffled videos: {output_folder}")
print(f"Filename mapping: {manifest_path}")