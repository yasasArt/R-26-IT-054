from pathlib import Path

import torch
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent

# New dataset test images
TEST_IMAGES = (
    PROJECT_ROOT
    / "dataset"
    / "test"
    / "images"
)

# Training results directory
TRAINING_RESULTS = (
    PROJECT_ROOT
    / "training_results"
)

# Find every trained best.pt model
model_files = list(
    TRAINING_RESULTS.rglob("best.pt")
)

if not model_files:
    raise FileNotFoundError(
        "training_results folder එක ඇතුළේ "
        "best.pt model එකක් හමු වුණේ නැහැ."
    )

# Select newest trained model
MODEL_PATH = max(
    model_files,
    key=lambda path: path.stat().st_mtime
)

if not TEST_IMAGES.exists():
    raise FileNotFoundError(
        f"Test images folder එක හමු වුණේ නැහැ:\n"
        f"{TEST_IMAGES}"
    )

# GPU selection
if torch.cuda.is_available():
    device = 0
    device_name = torch.cuda.get_device_name(0)
else:
    device = "cpu"
    device_name = "CPU"


print("=" * 65)
print("New YOLO Dataset Testing")
print("=" * 65)
print(f"Selected model : {MODEL_PATH}")
print(f"Test images    : {TEST_IMAGES}")
print(f"Device         : {device_name}")
print("=" * 65)


# Load newest model
model = YOLO(str(MODEL_PATH))

# Run prediction
results = model.predict(
    source=str(TEST_IMAGES),
    imgsz=640,
    conf=0.50,
    device=device,
    save=True,
    save_txt=True,
    save_conf=True,
    retina_masks=True,
    project=str(TRAINING_RESULTS),
    name="new_dataset_test_predictions",
    exist_ok=True,
    verbose=False
)


detected_images = 0
not_detected_images = 0
total_detections = 0
mask_detections = 0


for result in results:
    image_name = Path(result.path).name

    if result.boxes is None:
        detection_count = 0
    else:
        detection_count = len(result.boxes)

    if detection_count == 0:
        not_detected_images += 1
        print(f"[NOT DETECTED] {image_name}")
        continue

    detected_images += 1
    total_detections += detection_count

    confidence_values = (
        result.boxes.conf.cpu().tolist()
    )

    best_confidence = max(confidence_values)

    if result.masks is not None:
        mask_status = "Mask detected"
        mask_detections += 1
    else:
        mask_status = "Mask not detected"

    print(
        f"[DETECTED] {image_name} | "
        f"Garments: {detection_count} | "
        f"Confidence: {best_confidence:.4f} | "
        f"{mask_status}"
    )


RESULT_DIRECTORY = (
    TRAINING_RESULTS
    / "new_dataset_test_predictions"
)


print("\n" + "=" * 65)
print("Testing Completed")
print("=" * 65)
print(f"Total test images   : {len(results)}")
print(f"Detected images     : {detected_images}")
print(f"Not detected images : {not_detected_images}")
print(f"Total detections    : {total_detections}")
print(f"Images with masks   : {mask_detections}")
print(f"Results saved at    : {RESULT_DIRECTORY}")