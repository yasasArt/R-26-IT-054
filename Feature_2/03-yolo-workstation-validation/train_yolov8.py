from pathlib import Path
from ultralytics import YOLO


DATA_YAML = "./dataset/data.yaml"
BASE_MODEL = "yolov8n.pt"
EPOCHS = 50
IMG_SIZE = 640
BATCH_SIZE = 8
DEVICE = "mps"
PROJECT_DIR = "runs"
EXPERIMENT_NAME = "workstation_yolov8n_v2"


def main():
    data_path = Path(DATA_YAML).resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_path}")

    print("YOLOv8 Workstation Detector Training")
    print(f"Dataset: {data_path}")
    print(f"Base model: {BASE_MODEL}")
    print(f"Epochs: {EPOCHS}, Image size: {IMG_SIZE}, Batch: {BATCH_SIZE}, Device: {DEVICE}")

    model = YOLO(BASE_MODEL)
    results = model.train(
        data=str(data_path),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device=DEVICE,
        project=PROJECT_DIR,
        name=EXPERIMENT_NAME,
        patience=20,
        save=True,
        plots=True,
        verbose=True,
    )

    print("Training completed successfully!")
    print(f"Training results saved to: {results.save_dir}") # type: ignore
    print(f"Best model: {results.save_dir}/weights/best.pt") # type: ignore
    print(f"Last model: {results.save_dir}/weights/last.pt") # type: ignore


if __name__ == "__main__":
    main()
