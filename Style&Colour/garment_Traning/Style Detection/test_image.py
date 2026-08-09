import cv2
from ultralytics import YOLO

def main():
    # 1. ඔයා Train කරපු අලුත් මොඩලය (best.pt) Load කරගන්න
    # සටහන: ඔයාගේ best.pt තියෙන හරියටම path එක මෙතනට දෙන්න.
    model_path = "./runs/yolov8n_gpu/weights/best.pt" 
    
    try:
        model = YOLO(model_path)
        print("Trained model loaded successfully!")
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # 2. පරීක්ෂා කරන්න අවශ්‍ය පින්තූරයේ නම හෝ Path එක
    image_path = "./test_photo.jpg" # ඔයාගේ පින්තූරයේ නම මෙතනට දෙන්න
    
    print(f"\nAnalyzing image: {image_path} ...")

    # 3. පින්තූරය මොඩලයට ලබා දී ප්‍රතිඵල ලබාගැනීම
    # conf=0.5 යනු 50% කට වඩා විශ්වාස නම් පමණක් ප්‍රතිඵලය ලබා දෙන ලෙසයි
    results = model.predict(source=image_path, conf=0.5)

    # 4. ප්‍රතිඵලය තිරයේ පෙන්වීම
    for result in results:
        # රූපය මත කොටු ඇඳ තිරයේ පෙන්වයි
        result.show() 
        
        # ඔයාට අඳුරගත්තු දේවල් මොනවාද කියලා Terminal එකේ Print කරගන්න ඕනේ නම්:
        print("\n--- Detection Results ---")
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            class_name = model.names[class_id]
            confidence = float(box.conf[0].item()) * 100
            print(f"Detected: {class_name} ({confidence:.2f}%)")

if __name__ == '__main__':
    main()