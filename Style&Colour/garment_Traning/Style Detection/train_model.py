import os
from ultralytics import YOLO

def main():

    model = YOLO("yolov8n.pt")
    
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(project_dir, "data.yaml")
    
    print(f"Dataset: {yaml_path}")
    

    results = model.train(
        data=yaml_path, 
        epochs=50, 
        imgsz=640,
        batch=16,
        workers=0 
    )
    
    print("Training successfully completed!")

if __name__ == '__main__':
    main()