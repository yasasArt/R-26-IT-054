import os
import sys
import torch
from ultralytics import YOLO


# --------------------------------------------------
# Configuration
# --------------------------------------------------

# Path to your trained YOLO model
MODEL_PATH = "./models/best.pt"

# Can be:
# 1. A single image: "sample_images/test1.jpg"
# 2. A folder:       "sample_images"
IMAGE_SOURCE = "sample_images"

# Prediction confidence threshold
CONFIDENCE_THRESHOLD = 0.25

# IoU threshold used during non-maximum suppression
IOU_THRESHOLD = 0.45


def main():
    # Check model
    if not os.path.isfile(MODEL_PATH):
        print(f"Error: Trained model was not found: {MODEL_PATH}")
        sys.exit(1)

    # Check image or folder
    if not os.path.exists(IMAGE_SOURCE):
        print(f"Error: Image source was not found: {IMAGE_SOURCE}")
        sys.exit(1)

    # Select GPU or CPU
    device = 0 if torch.cuda.is_available() else "cpu"

    print("=" * 60)
    print(f"PyTorch version : {torch.__version__}")
    print(f"CUDA available  : {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"GPU             : {torch.cuda.get_device_name(0)}")
    else:
        print("GPU was not detected. Prediction will use CPU.")

    print(f"Model           : {MODEL_PATH}")
    print(f"Image source    : {IMAGE_SOURCE}")
    print("=" * 60)

    # Load trained model
    model = YOLO(MODEL_PATH)

    # Run prediction
    results = model.predict(
        source=IMAGE_SOURCE,
        imgsz=640,
        conf=CONFIDENCE_THRESHOLD,
        iou=IOU_THRESHOLD,
        device=device,
        save=True,
        save_txt=True,
        save_conf=True,
        project="prediction_results",
        name="sample_test",
        exist_ok=True,
        verbose=True
    )

    print("\nPrediction results:")

    for result in results:
        image_name = os.path.basename(result.path)
        boxes = result.boxes

        print(f"\nImage: {image_name}")

        if boxes is None or len(boxes) == 0:
            print("  No objects detected.")
            continue

        for index, box in enumerate(boxes, start=1):
            class_id = int(box.cls.item())
            class_name = model.names[class_id]
            confidence = float(box.conf.item())

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            print(
                f"  Detection {index}: "
                f"class={class_name}, "
                f"confidence={confidence:.4f}, "
                f"box=({x1:.0f}, {y1:.0f}, {x2:.0f}, {y2:.0f})"
            )

    output_directory = os.path.abspath(
        os.path.join("prediction_results", "sample_test")
    )

    print("\nTesting successfully completed!")
    print(f"Annotated images saved in: {output_directory}")


if __name__ == "__main__":
    main()