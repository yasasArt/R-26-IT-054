import cv2
import numpy as np
import requests 
import sys
from ultralytics import YOLO

# --- CONFIGURATION ---
MODEL_PATH = "models/best.pt"              

MIN_CONFIDENCE = 0.75          # Confidence එක 75% දක්වා වැඩි කළා (අත්/වෙනත් දේවල් අයින් කිරීමට)
STABILITY_FRAMES = 12          
COOLDOWN_FRAMES = 45           
MIN_AREA_RATIO = 0.15          # ඇඳුම අනිවාර්යයෙන්ම Folding Zone එකෙන් 15% ක් වත් ආවරණය කළ යුතුයි (අකුලපු ඇඳුම්/අත් ප්‍රතික්ෂේප කිරීමට)

print("Loading Fast YOLO Model... Please wait.")
try:
    model = YOLO(MODEL_PATH)
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    sys.exit(1)

# ==========================================
# Background Removal & Advanced Color Detection
# ==========================================
def extract_colors(image_crop):
    if image_crop is None or image_crop.size == 0:
        return [("UNKNOWN", 100.0)]

    img = cv2.resize(image_crop, (150, 150))
    h, w = img.shape[:2]

    mask = np.zeros((h, w), np.uint8)
    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)
    rect = (2, 2, w-4, h-4)
    
    try:
        cv2.grabCut(img, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
        fg_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    except:
        fg_mask = np.ones((h, w), np.uint8)

    hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv_img[:, :, 0], hsv_img[:, :, 1], hsv_img[:, :, 2]

    valid_pixels = fg_mask == 1
    if np.sum(valid_pixels) < 50:
        valid_pixels = np.ones((h, w), dtype=bool)

    black_mask = (val < 40) & valid_pixels
    white_mask = (sat < 15) & (val > 200) & valid_pixels
    gray_mask = (sat < 20) & (val >= 40) & (val <= 200) & valid_pixels

    color_mask = valid_pixels & ~black_mask & ~white_mask & ~gray_mask
    
    red_mask = ((hue < 10) | (hue > 165)) & color_mask
    orange_mask = (hue >= 10) & (hue < 25) & color_mask
    yellow_mask = (hue >= 25) & (hue < 35) & color_mask
    green_mask = (hue >= 35) & (hue < 85) & color_mask
    blue_mask = (hue >= 85) & (hue < 135) & color_mask
    purple_pink_mask = (hue >= 135) & (hue <= 165) & color_mask

    color_counts = {
        "BLACK": np.sum(black_mask), "WHITE": np.sum(white_mask), "GRAY": np.sum(gray_mask),
        "RED": np.sum(red_mask), "ORANGE": np.sum(orange_mask), "YELLOW": np.sum(yellow_mask),
        "GREEN": np.sum(green_mask), "BLUE": np.sum(blue_mask), "PURPLE/PINK": np.sum(purple_pink_mask)
    }

    total_garment_pixels = np.sum(valid_pixels)
    final_colors = []
    
    if total_garment_pixels > 0:
        for name, count in color_counts.items():
            pct = (count / total_garment_pixels) * 100
            if pct > 1.0: 
                final_colors.append((name, pct))

    final_colors = sorted(final_colors, key=lambda x: x[1], reverse=True)
    if not final_colors:
        return [("UNKNOWN", 100.0)]
        
    return final_colors

# ==========================================
# MAIN FACTORY PIPELINE
# ==========================================
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    sys.exit(1)

frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
if frame_w == 0: frame_w, frame_h = 640, 480

roi_x1 = int(frame_w * 0.15)
roi_y1 = int(frame_h * 0.20)
roi_x2 = int(frame_w * 0.85)
roi_y2 = int(frame_h * 0.95)

# ඇඳුමේ අවම ප්‍රමාණය ගණනය කිරීම
roi_area = (roi_x2 - roi_x1) * (roi_y2 - roi_y1)
MIN_GARMENT_AREA = roi_area * MIN_AREA_RATIO

stable_count = 0
current_tracking_style = ""
cooldown_timer = 0

# 100% පැහැදිලි රූපය තබා ගැනීමට Variables
best_frame_during_tracking = None
best_conf_during_tracking = 0.0
best_box_during_tracking = None

dash_img = None
dash_style = ""
dash_colors_text = []

font = cv2.FONT_HERSHEY_SIMPLEX

print("\n" + "="*50)
print("🏭 PACKING AREA PIPELINE ACTIVE")
print("Camera MUST point down at the table.")
print("="*50 + "\n")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break

    display_frame = frame.copy()
    current_state = "NOT READY"
    box_color = (0, 255, 255) # Yellow

    cv2.rectangle(display_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 100, 0), 2, cv2.LINE_AA)
    cv2.putText(display_frame, "FOLDING ZONE", (roi_x1, roi_y1 - 10), font, 0.5, (255, 100, 0), 1)

    if cooldown_timer > 0:
        cooldown_timer -= 1
        current_state = "VALID (SAVED)"
        box_color = (255, 0, 255) # Purple
    else:
        roi_frame = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        results = model(roi_frame, verbose=False)
        garment_valid = False
        
        if len(results[0].boxes) > 0:
            best_box = results[0].boxes[0]
            conf = float(best_box.conf)
            cls_id = int(best_box.cls)
            detected_style = model.names[cls_id]
            
            bx1, by1, bx2, by2 = map(int, best_box.xyxy[0].cpu().numpy())
            box_area = (bx2 - bx1) * (by2 - by1)
            
            full_x1, full_y1 = roi_x1 + bx1, roi_y1 + by1
            full_x2, full_y2 = roi_x1 + bx2, roi_y1 + by2

            # තර්කය: Confidence එක 75% ට වැඩිද සහ ඇඳුම දිගෑරලා (ලොකුවට) තියෙනවද?
            if conf >= MIN_CONFIDENCE and box_area >= MIN_GARMENT_AREA:
                garment_valid = True
                current_state = "VALID"
                box_color = (0, 255, 0) # Green

                cv2.rectangle(display_frame, (full_x1, full_y1), (full_x2, full_y2), box_color, 2)
                cv2.putText(display_frame, f"{detected_style.upper()} ({conf*100:.1f}%)", (full_x1, full_y1 - 5), font, 0.6, box_color, 2)

                if detected_style == current_tracking_style:
                    stable_count += 1
                    # VALID වෙලාවේ තියෙන පැහැදිලිම (Best) Frame එක Save කරගැනීම
                    if conf > best_conf_during_tracking:
                        best_conf_during_tracking = conf
                        best_frame_during_tracking = frame.copy()
                        best_box_during_tracking = (full_x1, full_y1, full_x2, full_y2)
                else:
                    current_tracking_style = detected_style
                    stable_count = 1
                    best_conf_during_tracking = conf
                    best_frame_during_tracking = frame.copy()
                    best_box_during_tracking = (full_x1, full_y1, full_x2, full_y2)

                if stable_count >= STABILITY_FRAMES:
                    fx1, fy1, fx2, fy2 = best_box_during_tracking
                    garment_crop = best_frame_during_tracking[fy1:fy2, fx1:fx2]
                    colors = extract_colors(garment_crop)
                    
                    main_color = colors[0][0]
                    formatted_colors = [f"{c[0]}: {c[1]:.1f}%" for c in colors]
                    other_colors_str = " | ".join(formatted_colors[1:]) if len(colors) > 1 else "NONE"

                    dash_img = cv2.resize(garment_crop, (200, 200))
                    dash_style = detected_style.upper()
                    dash_colors_text = formatted_colors

                    api_data = {
                        "style_name": dash_style,
                        "main_color": main_color,
                        "other_colors": other_colors_str if other_colors_str != "NONE" else "",
                        "confidence": round(best_conf_during_tracking * 100, 2)
                    }
                    
                    db_status = "⚠️ FAILED (Check Backend)"
                    try:
                        res = requests.post("http://127.0.0.1:8000/api/garments/", json=api_data)
                        if res.status_code == 200:
                            db_status = "✅ SAVED SUCCESS"
                    except:
                        pass

                    # ==========================================
                    # BEAUTIFUL TERMINAL OUTPUT
                    # ==========================================
                    print("\n" + "-" * 45)
                    print(" 🎉 NEW GARMENT PACKED SUCCESSFULLY!")
                    print("-" * 45)
                    print(f" 👕 Style        : {dash_style} ({best_conf_during_tracking*100:.1f}%)")
                    print(f" 🎨 Main Color   : {main_color}")
                    print(f" 🌈 Other Colors : {other_colors_str}")
                    print(f" 💾 Database     : {db_status}")
                    print("-"*45 + "\n")

                    cooldown_timer = COOLDOWN_FRAMES
                    stable_count = 0
                    current_tracking_style = ""
            
            else:
                # අතක් දැම්මොත් හෝ අකුලපු ඇඳුමක් තිබ්බොත් INVALID වේ
                current_state = "INVALID (ADJUST GARMENT)"
                box_color = (0, 0, 255) # Red
                cv2.rectangle(display_frame, (full_x1, full_y1), (full_x2, full_y2), box_color, 2)
                cv2.putText(display_frame, "INVALID", (full_x1, full_y1 - 5), font, 0.6, box_color, 2)
                stable_count = 0
                current_tracking_style = ""

        # ඇඳුමක් නැතිනම් NOT READY වේ
        if not garment_valid and current_state != "INVALID (ADJUST GARMENT)":
            current_state = "NOT READY"
            box_color = (0, 255, 255)
            stable_count = 0
            current_tracking_style = ""

    # Header State Text
    cv2.putText(display_frame, f"STATE: {current_state}", (20, 40), font, 0.8, box_color, 2, cv2.LINE_AA)

    # ==========================================
    # LIVE DASHBOARD (Side Panel)
    # ==========================================
    sidebar_width = 250
    overlay = display_frame.copy()
    cv2.rectangle(overlay, (frame_w - sidebar_width, 0), (frame_w, frame_h), (30, 30, 30), -1)
    display_frame = cv2.addWeighted(overlay, 0.8, display_frame, 0.2, 0)
    
    cv2.putText(display_frame, "LAST SCANNED:", (frame_w - sidebar_width + 10, 30), font, 0.6, (200, 200, 200), 1)

    if dash_img is not None:
        img_x, img_y = frame_w - sidebar_width + 25, 50
        display_frame[img_y:img_y+200, img_x:img_x+200] = dash_img
        cv2.rectangle(display_frame, (img_x, img_y), (img_x+200, img_y+200), (0, 255, 0), 2)
        
        text_y = img_y + 230
        cv2.putText(display_frame, f"STYLE: {dash_style}", (img_x, text_y), font, 0.6, (0, 255, 0), 2)
        
        text_y += 30
        for color_txt in dash_colors_text:
            cv2.putText(display_frame, color_txt, (img_x, text_y), font, 0.5, (255, 255, 255), 1)
            text_y += 25

    cv2.imshow("PACKING STATION AI", display_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()