from pathlib import Path
from ultralytics import YOLO


MODEL_PATH = "./runs/detect/runs/workstation_yolov8n_v2/weights/best.pt"
DATA_YAML = "./dataset/data.yaml"
IMG_SIZE = 640
DEVICE = "mps"


def main():
    model_path = Path(MODEL_PATH).expanduser().resolve()
    data_path = Path(DATA_YAML).expanduser().resolve()

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_path}")

    model = YOLO(str(model_path))
    metrics = model.val(
        data=str(data_path),
        split="test",
        imgsz=IMG_SIZE,
        device=DEVICE,
        plots=True,
        save_json=True,
    )

    print("========== YOLOv8 TEST RESULTS ==========")
    print(f"mAP50:      {metrics.box.map50:.4f}")
    print(f"mAP50-95:   {metrics.box.map:.4f}")
    print(f"Precision:  {metrics.box.mp:.4f}")
    print(f"Recall:     {metrics.box.mr:.4f}")
    print("=========================================")


if __name__ == "__main__":
    main()
