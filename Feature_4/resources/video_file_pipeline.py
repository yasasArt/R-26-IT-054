import cv2
import numpy as np
import sys
from pathlib import Path
from collections import Counter

import torch
from torchvision import transforms
import torchvision.models as models
from PIL import Image
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent
STATE_MODEL_PATH = BASE_DIR / "models" / "best_frame.pt"
STYLE_MODEL_PATH = BASE_DIR / "models" / "best.pt"
VIDEO_PATH = BASE_DIR / "dataset" / "videos" / "v20.mp4"

print("Loading models... Please wait.")

# 1. Loading Model 1 (State Detection) and Model 2 (Style Detection)
if not STATE_MODEL_PATH.exists():
    raise FileNotFoundError(f"State model not found: {STATE_MODEL_PATH}")
if not STYLE_MODEL_PATH.exists():
    raise FileNotFoundError(f"Style model not found: {STYLE_MODEL_PATH}")
if not VIDEO_PATH.exists():
    raise FileNotFoundError(f"Video file not found: {VIDEO_PATH}")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
state_model = models.mobilenet_v3_small(num_classes=3)
state_dict = torch.load(str(STATE_MODEL_PATH), map_location=device, weights_only=False)
state_model.load_state_dict(state_dict['model_state_dict'])
state_model = state_model.to(device)
state_model.eval()

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

model2_style = YOLO(str(STYLE_MODEL_PATH))

print("Models loaded successfully!")

# ==========================================
# Background Removal & Color Detection (GrabCut + HSV)
# ==========================================
def remove_background_and_get_colors(image_crop):
    if image_crop.size == 0:
        return [("UNKNOWN", 100.0)]

    # Resize crop for faster GrabCut processing
    img = cv2.resize(image_crop, (150, 150))
    h, w = img.shape[:2]

    # --- Step 1: GrabCut Algorithm to remove Background ---
    mask = np.zeros((h, w), np.uint8)
    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)
    
    # Define a rectangle leaving a small 2-pixel border for the algorithm to identify the background
    rect = (2, 2, w-4, h-4)
    
    try:
        # Apply GrabCut to separate foreground (garment) and background
        cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
        
        # mask == 2 or 0 means background, mask == 1 or 3 means garment
        fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    except:
        # Fallback if GrabCut fails
        fg_mask = np.ones((h, w), np.uint8)

    # Convert original to HSV for color detection
    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv_img[:, :, 0], hsv_img[:, :, 1], hsv_img[:, :, 2]

    # valid_pixels will ONLY contain the garment (no background)
    valid_pixels = fg_mask == 1
    
    # If the mask removed everything by mistake, fallback to the whole box
    if np.sum(valid_pixels) < 50:
        valid_pixels = np.ones((h, w), dtype=bool)

    # --- Step 2: Extract colors ONLY from the Garment pixels ---
    # Masks for black, white, and gray
    black_mask = (val < 40) & valid_pixels
    white_mask = (sat < 40) & (val > 200) & valid_pixels
    gray_mask = (sat < 40) & (val >= 40) & (val <= 200) & valid_pixels

    # Masks for other colors (Ignoring B&W/Gray)
    color_mask = valid_pixels & ~black_mask & ~white_mask & ~gray_mask
    
    red_mask = ((hue < 10) | (hue > 165)) & color_mask
    orange_mask = (hue >= 10) & (hue < 25) & color_mask
    yellow_mask = (hue >= 25) & (hue < 35) & color_mask
    green_mask = (hue >= 35) & (hue < 85) & color_mask
    blue_mask = (hue >= 85) & (hue < 135) & color_mask
    purple_pink_mask = (hue >= 135) & (hue <= 165) & color_mask

    # Calculate pixel counts for each color
    color_counts = {
        "BLACK": np.sum(black_mask),
        "WHITE": np.sum(white_mask),
        "GRAY": np.sum(gray_mask),
        "RED": np.sum(red_mask),
        "ORANGE": np.sum(orange_mask),
        "YELLOW": np.sum(yellow_mask),
        "GREEN": np.sum(green_mask),
        "BLUE": np.sum(blue_mask),
        "PURPLE/PINK": np.sum(purple_pink_mask)
    }

    # Calculate percentages based ONLY on the garment pixels (not the whole box)
    garment_total_pixels = np.sum(valid_pixels)
    final_colors = []
    
    if garment_total_pixels > 0:
        for name, count in color_counts.items():
            pct = (count / garment_total_pixels) * 100
            if pct > 5.0: # Ignore noise colors below 5%
                final_colors.append((name, pct))

    # Sort from highest percentage to lowest
    final_colors = sorted(final_colors, key=lambda x: x[1], reverse=True)

    if not final_colors:
        return [("UNKNOWN", 100.0)]
        
    return final_colors
# ==========================================

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print(f"Error: Could not open video file -> {VIDEO_PATH}")
    sys.exit(1)

highest_valid_score = 0.0
best_frame = None
frame_count = 0

current_state = 'NOT_READY'
state_confidence = 0.0
color_ui = (0, 255, 255)

print(f"\nPlaying and Analyzing video: {VIDEO_PATH}")
print("Press 'q' if you want to skip to the end.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break 
        
    frame_count += 1
    
    # Check AI state every 3 frames
    if frame_count % 3 == 0:
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        input_tensor = preprocess(pil_img).unsqueeze(0).to(device)

        with torch.no_grad():
            logits = state_model(input_tensor)
            probabilities = torch.nn.functional.softmax(logits, dim=1)[0]

        invalid_score = probabilities[0].item() * 100
        not_ready_score = probabilities[1].item() * 100
        valid_score = probabilities[2].item() * 100
        
        if valid_score > 35.0:
            current_state = 'VALID'
            state_confidence = valid_score
            color_ui = (0, 255, 0) 
        elif invalid_score > 50.0:
            current_state = 'INVALID'
            state_confidence = invalid_score
            color_ui = (0, 0, 255) 
        else:
            current_state = 'NOT_READY'
            state_confidence = not_ready_score
            color_ui = (0, 255, 255) 

        if valid_score > highest_valid_score:
            highest_valid_score = valid_score
            best_frame = frame.copy() 

    display_frame = frame.copy()
    cv2.putText(display_frame, f"State: {current_state} ({state_confidence:.1f}%)", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_ui, 2)
    cv2.imshow("Video Processing...", display_frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Skipping to the end...")
        break

cap.release()
cv2.destroyAllWindows()

# 3. Analyze the Best Frame after the video ends
if best_frame is not None and highest_valid_score > 35.0:
    print("\n" + "="*50)
    print(f"Best Frame Found with VALID Probability : {highest_valid_score:.2f}%")
    print("Running Style & Color Detection with Background Removal...")
    
    results = model2_style(best_frame, verbose=False)
    result = results[0]
    
    style_name = "Unknown"
    style_conf = 0.0
    cropped_garment = None
    
    if result.boxes is not None and len(result.boxes) > 0:
        box = result.boxes[0] 
        cls_index = int(box.cls[0].item())
        style_name = result.names[cls_index]
        style_conf = float(box.conf[0].item()) * 100
        
        # Get standard bounding box coordinates (GrabCut will handle the background removal)
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cropped_garment = best_frame[y1:y2, x1:x2]

    MIN_CONFIDENCE = 50.0 
    
    if style_conf >= MIN_CONFIDENCE and cropped_garment is not None:
        print(f"Detected Style      : ** {style_name.upper()} ** ({style_conf:.2f}%)")
        
        # --- Advanced Color Analysis (GrabCut + HSV) ---
        detected_colors = remove_background_and_get_colors(cropped_garment)
        
        main_color_name, main_color_pct = detected_colors[0]
        print(f"Main Color          : ** {main_color_name} ** ({main_color_pct:.1f}%)")
        
        style_text = f"Style: {style_name.upper()} ({style_conf:.1f}%)"
        main_color_text = f"MAIN COLOR: {main_color_name} ({main_color_pct:.1f}%)"
        
        other_colors_text = ""
        if len(detected_colors) > 1:
            other_colors_list = [f"{name}({pct:.0f}%)" for name, pct in detected_colors[1:]]
            other_colors_text = "Other Colors: " + " | ".join(other_colors_list)
            print(f"Other Colors        : {other_colors_text}")
            
        final_color = (0, 255, 0)
        
        cv2.putText(best_frame, style_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, final_color, 2)
        cv2.putText(best_frame, main_color_text, (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3) 
        
        if other_colors_text:
            cv2.putText(best_frame, other_colors_text, (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    else:
        print("Detected Style      : UNKNOWN / LOW CONFIDENCE")
        cv2.putText(best_frame, "UNKNOWN (Low Confidence)", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
        
    print("="*50 + "\n")
    
    cv2.imshow("Final Result: Best Frame, Style & Colors", best_frame)
    print("Press any key on the image window to close it...")
    cv2.waitKey(0) 
    cv2.destroyAllWindows()
    
else:
    print("\nWARNING: Could not find any clear (VALID) frame in this video.")