import cv2
import numpy as np
import requests 
import sys
import base64
import threading
from flask import Flask, Response
from flask_cors import CORS
from ultralytics import YOLO

# --- CONFIGURATION (UPDATED FOR FACTORY CONDITIONS) ---
MODEL_PATH = "models/best.pt"              

MIN_CONFIDENCE = 0.80          # 80% දක්වා වැඩි කළා (ෆෝන්/පොත් සහ බොරු දේවල් ප්‍රතික්ෂේප කිරීමට)
STABILITY_FRAMES = 12          
COOLDOWN_FRAMES = 45           
MIN_AREA_RATIO = 0.20          # 20% දක්වා වැඩි කළා (ගුලි කරපු ඇඳුම්, පෑන්, පොත් ප්‍රතික්ෂේප කිරීමට)
MAX_MOVEMENT = 30              # ඇඳුම නිශ්චලව පවතින බව තහවුරු කිරීමට ඉඩ දෙන උපරිම චලනය (පික්සල්)

print("Loading Fast YOLO Model... Please wait.")
try:
    model = YOLO(MODEL_PATH)
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    sys.exit(1)

# ==========================================
# Video Streaming Server (Flask)
# ==========================================
app = Flask(__name__)
CORS(app)

global_frame = None
lock = threading.Lock()

def generate_frames():
    global global_frame
    while True:
        with lock:
            if global_frame is None:
                continue
            ret, buffer = cv2.imencode('.jpg', global_frame)
            if not ret:
                continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ==========================================
# Background Removal Function
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
def run_opencv_pipeline():
    global global_frame
    cap = cv2.VideoCapture(1)
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

    roi_area = (roi_x2 - roi_x1) * (roi_y2 - roi_y1)
    MIN_GARMENT_AREA = roi_area * MIN_AREA_RATIO

    stable_count = 0
    current_tracking_style = ""
    cooldown_timer = 0
    last_center = None  # අලුතින් එකතු කළ Motion Tracker විචල්‍යය

    best_frame_during_tracking = None
    best_conf_during_tracking = 0.0
    best_box_during_tracking = None

    font = cv2.FONT_HERSHEY_SIMPLEX

    print("\n" + "="*50)
    print("🏭 AI PIPELINE: MOTION TRACKING & STRICT FILTERING ACTIVE")
    print("="*50 + "\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        display_frame = frame.copy()
        current_state = "NOT READY"
        box_color = (0, 255, 255) 

        cv2.rectangle(display_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 100, 0), 2, cv2.LINE_AA)
        cv2.putText(display_frame, "FOLDING ZONE", (roi_x1, roi_y1 - 10), font, 0.5, (255, 100, 0), 1)

        if cooldown_timer > 0:
            cooldown_timer -= 1
            current_state = "VALID (SAVED)"
            box_color = (255, 0, 255) 
            last_center = None
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
                
                # Bounding Box එකේ හරි මැද ලක්ෂ්‍යය (Center Point)
                cx = (bx1 + bx2) // 2
                cy = (by1 + by2) // 2

                # Motion Calculation (චලනය ගණනය කිරීම)
                movement = 0
                if last_center is not None:
                    movement = np.sqrt((cx - last_center[0])**2 + (cy - last_center[1])**2)
                last_center = (cx, cy)
                
                full_x1, full_y1 = roi_x1 + bx1, roi_y1 + by1
                full_x2, full_y2 = roi_x1 + bx2, roi_y1 + by2

                # නීතිය 1: Confidence සහ Size එක හරිද? (පොත්/ෆෝන්/ගුලි වූ ඇඳුම් ප්‍රතික්ෂේප කිරීම)
                if conf >= MIN_CONFIDENCE and box_area >= MIN_GARMENT_AREA:
                    
                    # නීතිය 2: ඇඳුම මේසය මත නිශ්චලද? (Motion Tracking)
                    if movement > MAX_MOVEMENT:
                        current_state = "MOVING..."
                        box_color = (0, 165, 255) # Orange Color
                        stable_count = 0 # චලනය වන නිසා Tracking එක Reset වේ
                        
                        cv2.rectangle(display_frame, (full_x1, full_y1), (full_x2, full_y2), box_color, 2)
                        cv2.putText(display_frame, "MOVING...", (full_x1, full_y1 - 5), font, 0.6, box_color, 2)
                    
                    else:
                        # ඇඳුම නිවැරදියි සහ නිශ්චලයි (Ready to capture)
                        garment_valid = True
                        current_state = "VALID"
                        box_color = (0, 255, 0) 

                        cv2.rectangle(display_frame, (full_x1, full_y1), (full_x2, full_y2), box_color, 2)
                        cv2.putText(display_frame, f"{detected_style.upper()} ({conf*100:.1f}%)", (full_x1, full_y1 - 5), font, 0.6, box_color, 2)

                        if detected_style == current_tracking_style:
                            stable_count += 1
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

                        # Best Frame එක අල්ලා ගැනීම
                        if stable_count >= STABILITY_FRAMES:
                            fx1, fy1, fx2, fy2 = best_box_during_tracking
                            garment_crop = best_frame_during_tracking[fy1:fy2, fx1:fx2]
                            colors = extract_colors(garment_crop)
                            
                            _, buffer = cv2.imencode('.jpg', garment_crop)
                            img_base64 = base64.b64encode(buffer).decode('utf-8')
                            
                            main_color = colors[0][0]
                            formatted_colors = [f"{c[0]}: {c[1]:.1f}%" for c in colors]
                            other_colors_str = " | ".join(formatted_colors[1:]) if len(colors) > 1 else "NONE"

                            api_data = {
                                "style_name": detected_style.upper(),
                                "main_color": main_color,
                                "other_colors": other_colors_str if other_colors_str != "NONE" else "",
                                "confidence": round(best_conf_during_tracking * 100, 2),
                                "image_base64": img_base64
                            }
                            
                            try:
                                requests.post("http://127.0.0.1:8000/api/garments/", json=api_data)
                            except:
                                pass

                            cooldown_timer = COOLDOWN_FRAMES
                            stable_count = 0
                            current_tracking_style = ""
                            last_center = None
                
                else:
                    # Size එක මදි හෝ Confidence අඩුනම් (උදා: ෆෝන්, පොත්, ගුලි කරපු ඇඳුම්)
                    current_state = "INVALID (ADJUST GARMENT)"
                    box_color = (0, 0, 255) 
                    cv2.rectangle(display_frame, (full_x1, full_y1), (full_x2, full_y2), box_color, 2)
                    cv2.putText(display_frame, "INVALID", (full_x1, full_y1 - 5), font, 0.6, box_color, 2)
                    stable_count = 0
                    current_tracking_style = ""
                    last_center = None

            if not garment_valid and current_state not in ["INVALID (ADJUST GARMENT)", "MOVING..."]:
                current_state = "NOT READY"
                box_color = (0, 255, 255)
                stable_count = 0
                current_tracking_style = ""
                last_center = None

        cv2.putText(display_frame, f"STATE: {current_state}", (20, 40), font, 0.8, box_color, 2, cv2.LINE_AA)

        with lock:
            global_frame = display_frame.copy()

        cv2.waitKey(1)

    cap.release()

if __name__ == '__main__':
    t = threading.Thread(target=run_opencv_pipeline)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)