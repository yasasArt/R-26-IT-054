import os
import cv2
import numpy as np
from tensorflow.keras.models import load_model
from ultralytics import YOLO

print("Loading models... Please wait.")

# 1. Load Model 1 (Keras - Best Frame Selection)
model1_best_frame = load_model('models/best_frame_model.h5')

# 2. Load Model 2 (YOLOv8 - Style Recognition)
model2_style = YOLO('models/best.pt')

# Target folder containing video frames
video_frames_folder = 'dataset/frames/v24/' 

highest_valid_score = 0.0
best_frame_path = None

print(f"\nAnalyzing frames in directory: {video_frames_folder}")

# 3. Pass frames through Model 1 to find the Best Frame
for img_name in sorted(os.listdir(video_frames_folder)):
    if img_name.endswith(('.png', '.jpg', '.jpeg')):
        img_path = os.path.join(video_frames_folder, img_name)
        img = cv2.imread(img_path)
        
        if img is not None:
            # Preprocess for Model 1
            img_resized = cv2.resize(img, (224, 224))
            img_normalized = img_resized / 255.0
            img_expanded = np.expand_dims(img_normalized, axis=0)
            
            # Predict state using Model 1
            prediction1 = model1_best_frame.predict(img_expanded, verbose=0)
            valid_score = prediction1[0][2] # Index 2 is 'VALID'
            
            if valid_score > highest_valid_score:
                highest_valid_score = valid_score
                best_frame_path = img_path

# 4. Pass the selected Best Frame to Model 2 (YOLOv8)
if best_frame_path is not None and highest_valid_score > 0.5:
    print("\n" + "="*50)
    print(f"Selected Best Frame : {best_frame_path}")
    print(f"VALID Probability   : {highest_valid_score * 100:.2f}%")
    
    print("Running Style Detection (Model 2)...")
    results = model2_style(best_frame_path, verbose=False)
    
    result = results[0]
    style_name = "Unknown"
    confidence = 0.0
    
    # Extract YOLO results
    if result.probs is not None:
        top1_index = result.probs.top1
        style_name = result.names[top1_index]
        confidence = result.probs.top1conf.item() * 100
    elif result.boxes is not None and len(result.boxes) > 0:
        box = result.boxes[0] 
        cls_index = int(box.cls[0].item())
        style_name = result.names[cls_index]
        confidence = float(box.conf[0].item()) * 100
        
    MIN_CONFIDENCE = 60.0 
    
    if confidence >= MIN_CONFIDENCE:
        print(f"Detected Style      : ** {style_name.upper()} ** ({confidence:.2f}%)")
    else:
        print(f"Detected Style : '{style_name}' with only {confidence:.2f}% confidence.")
        
    print("="*50 + "\n")
else:
    print("\nWARNING: Could not find a clear (VALID) frame in this sequence.")