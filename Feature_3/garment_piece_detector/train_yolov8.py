from pathlib import Path

import torch
from ultralytics import YOLO


def main():
    # Current project folder
    project_directory = Path(__file__).resolve().parent

    # Dataset data.yaml location
    dataset_yaml = project_directory / "dataset" / "data.yaml"

    # Training output location
    output_directory = project_directory / "training_results"

    print(f"Project directory: {project_directory}")
    print(f"Dataset YAML: {dataset_yaml}")

    # Check data.yaml
    if not dataset_yaml.exists():
        raise FileNotFoundError(
            f"\ndata.yaml was not found:\n{dataset_yaml}\n\n"
            "Check whether your Roboflow dataset is inside the dataset folder."
        )

    # Select GPU or CPU
    if torch.cuda.is_available():
        device = 0
        print(f"GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        device = "cpu"
        print("GPU not detected. Using CPU.")

    # For Roboflow segmentation/mask dataset
    model = YOLO("yolov8n-seg.pt")

    # If your annotations are bounding boxes, use this instead:
    # model = YOLO("yolov8n.pt")

    # Start training
    model.train(
        data=str(dataset_yaml),
        epochs=100,
        imgsz=640,
        batch=16,
        device=device,
        workers=0,  # Recommended for Windows
        project=str(output_directory),
        name="garment_yolov8",
        pretrained=True,
        optimizer="auto",
        patience=20,
        save=True,
        plots=True,
        amp=torch.cuda.is_available(),
        seed=42
    )

    best_model = (
        output_directory
        / "garment_yolov8"
        / "weights"
        / "best.pt"
    )

    print("\nTraining completed successfully!")
    print(f"Best model: {best_model}")


if __name__ == "__main__":
    main()