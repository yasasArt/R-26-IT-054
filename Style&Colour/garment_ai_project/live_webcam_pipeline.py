import cv2
import numpy as np
import requests 
import sys
import base64
import threading
import os
import urllib.request
from flask import Flask, Response
from flask_cors import CORS
from ultralytics import YOLO

import torch
from torchvision import transforms
import torchvision.models as models  
from PIL import Image

# --- CONFIGURATION ---
STYLE_MODEL_PATH = "models/best.pt"              
BEST_FRAME_MODEL_PATH = "models/best_frame.pt"   

EXPECTED_BEST_CLASS_INDEX = 0  
BEST_FRAME_CONFIDENCE = 0.50   

MIN_CONFIDENCE = 0.70          
COOLDOWN_FRAMES = 35           
MIN_AREA_RATIO = 0.15          

print("Loading AI Models... Please wait.")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

try:
    yolo_model = YOLO(STYLE_MODEL_PATH)
    print("✅ YOLO Style Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading YOLO model: {e}")
    sys.exit(1)

try:
    best_frame_model = models.mobilenet_v3_small(num_classes=3) 
    state_dict = torch.load(BEST_FRAME_MODEL_PATH, map_location=device, weights_only=False)
    best_frame_model.load_state_dict(state_dict['model_state_dict'])
    best_frame_model = best_frame_model.to(device)
    best_frame_model.eval() 
    print("✅ MobileNetV3 Best Frame Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading MobileNetV3 model: {e}")
    sys.exit(1)

# --- FACE DETECTOR SETUP ---
cascade_filename = 'haarcascade_frontalface_default.xml'
if not os.path.exists(cascade_filename):
    print("📥 Downloading Face Detection Model...")
    url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
    urllib.request.urlretrieve(url, cascade_filename)
face_cascade = cv2.CascadeClassifier(cascade_filename)

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def check_best_frame(frame_bgr):
    img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    input_tensor = preprocess(pil_img).unsqueeze(0).to(device)

    with torch.no_grad():
        output = best_frame_model(input_tensor)
        probabilities = torch.nn.functional.softmax(output[0], dim=0)
        top_prob, top_class = torch.max(probabilities, 0)

    return top_class.item(), top_prob.item()

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
# ADVANCED CIELAB COLOR DETECTION (BEST OPTION)
# ==========================================
def extract_colors(image_crop):
    if image_crop is None or image_crop.size == 0:
        return [("UNKNOWN", 100.0)]

    # 1. පසුබිම (Table/Shadows) මකා දැමීමට හරියටම ඇඳුමේ මැද කොටස පමණක් ගැනීම (50% Center Crop)
    h, w = image_crop.shape[:2]
    ch, cw = int(h * 0.5), int(w * 0.5) 
    y1, x1 = (h - ch) // 2, (w - cw) // 2
    center_crop = image_crop[y1:y1+ch, x1:x1+cw]

    if center_crop.size == 0:
        center_crop = image_crop

    # 2. රෙදි වල ඇති ඝනකම (Texture) නිසා ඇතිවන Noise එක නැති කිරීමට Blur කිරීම
    blurred = cv2.GaussianBlur(center_crop, (5, 5), 0)

    # 3. වර්ණ වඩාත් නිවැරදිව හඳුනාගැනීමට රූපය LAB Color Space එකට හැරවීම (Human Vision Model)
    img_lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    
    pixels_lab = img_lab.reshape(-1, 3)
    pixels_float = np.float32(pixels_lab)

    # 4. K-Means Clustering (ප්‍රධාන වර්ණ 3ක් සෙවීම)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    k = 3
    _, labels, centers = cv2.kmeans(pixels_float, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    counts = np.bincount(labels.flatten())
    total = np.sum(counts)
    
    # 5. අපගේ වර්ණ මාලාව (RGB වලින් දී LAB වලට පරිවර්තනය කර ගලපයි)
    PALETTE_RGB = {
        "BLUE": (62, 111, 216), "NAVY": (31, 53, 104), "RED": (220, 50, 50),
        "BLACK": (35, 35, 35), "WHITE": (240, 240, 240), "GREEN": (63, 200, 100),
        "OLIVE": (107, 122, 79), "AMBER": (245, 178, 74), "YELLOW": (240, 210, 50),
        "ORANGE": (232, 130, 50), "GREY": (130, 130, 130), "BEIGE": (216, 201, 168),
        "BROWN": (138, 90, 50), "PURPLE": (138, 90, 201), "PINK": (232, 130, 176)
    }

    # Palette එක LAB Space එකට Convert කිරීම
    palette_lab = {}
    for name, rgb in PALETTE_RGB.items():
        rgb_arr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]]) # OpenCV BGR format
        lab_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_BGR2LAB)
        palette_lab[name] = lab_arr[0][0]

    # CIELAB දුර (Delta E වලට ආසන්න අගයක්) මැනීම මගින් නිවැරදිම වර්ණය සෙවීම
    def closest_color_lab(lab_val):
        min_dist = float('inf')
        best_name = "UNKNOWN"
        for name, p_lab in palette_lab.items():
            # LAB Space Euclidean Distance
            dist = sum((float(a) - float(b)) ** 2 for a, b in zip(lab_val, p_lab))
            if dist < min_dist:
                min_dist = dist
                best_name = name
        return best_name

    raw_colors = []
    for i in range(k):
        pct = (counts[i] / total) * 100
        # 5% ට වඩා අඩු සුළු වර්ණ (Noise) සම්පූර්ණයෙන්ම අතහරින්න
        if pct > 5.0: 
            color_name = closest_color_lab(centers[i])
            raw_colors.append((color_name, pct))

    # එකම පාට දෙපාරක් ආවොත් ඒවා එකට එකතු කිරීම
    final_colors_dict = {}
    for name, pct in raw_colors:
        final_colors_dict[name] = final_colors_dict.get(name, 0) + pct

    final_colors = list(final_colors_dict.items())
    final_colors.sort(key=lambda x: x[1], reverse=True)

    if not final_colors:
        return [("UNKNOWN", 100.0)]
        
    return final_colors

# ==========================================
# MAIN FACTORY PIPELINE
# ==========================================
def run_opencv_pipeline():
    global global_frame
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

    MIN_GARMENT_AREA = (roi_x2 - roi_x1) * (roi_y2 - roi_y1) * MIN_AREA_RATIO
    cooldown_timer = 0
    stable_count = 0  
    font = cv2.FONT_HERSHEY_SIMPLEX

    print("\n" + "="*50)
    print("🏭 AI PIPELINE: CLEAN FEED & HUMAN REJECTION ACTIVE")
    print("="*50 + "\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        display_frame = frame.copy()
        current_state = "WAITING FOR GARMENT..."
        box_color = (0, 255, 255) 

        cv2.rectangle(display_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255, 100, 0), 2, cv2.LINE_AA)
        cv2.putText(display_frame, "FOLDING ZONE", (roi_x1, roi_y1 - 10), font, 0.5, (255, 100, 0), 1)

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_frame, 1.3, 5, minSize=(50, 50))
        human_detected = len(faces) > 0
        
        if human_detected:
            current_state = "HUMAN DETECTED - PAUSED"
            box_color = (0, 0, 255)
            for (fx, fy, fw, fh) in faces:
                cv2.rectangle(display_frame, (fx, fy), (fx+fw, fy+fh), (0, 0, 255), 3)
                cv2.putText(display_frame, "PERSON IGNORED", (fx, fy - 5), font, 0.6, (0, 0, 255), 2)

        if cooldown_timer > 0:
            cooldown_timer -= 1
            stable_count = 0
            current_state = "VALID (SAVED)"
            box_color = (255, 0, 255) 
            # (තිරයේ Thumbnail පෙන්වීම මෙතැනින් ඉවත් කර ඇත)
            
        elif not human_detected: 
            roi_frame = frame[roi_y1:roi_y2, roi_x1:roi_x2]
            results = yolo_model(roi_frame, verbose=False)
            garment_detected = False
            
            if len(results[0].boxes) > 0:
                best_box = results[0].boxes[0]
                conf = float(best_box.conf)
                
                if conf >= MIN_CONFIDENCE:
                    cls_id = int(best_box.cls)
                    detected_style = yolo_model.names[cls_id]
                    
                    bx1, by1, bx2, by2 = map(int, best_box.xyxy[0].cpu().numpy())
                    box_area = (bx2 - bx1) * (by2 - by1)

                    if box_area >= MIN_GARMENT_AREA:
                        garment_detected = True
                        stable_count += 1
                        
                        full_x1, full_y1 = roi_x1 + bx1, roi_y1 + by1
                        full_x2, full_y2 = roi_x1 + bx2, roi_y1 + by2
                        
                        box_color = (0, 255, 0)
                        cv2.rectangle(display_frame, (full_x1, full_y1), (full_x2, full_y2), box_color, 2)
                        cv2.putText(display_frame, f"VALID: {detected_style.upper()} ({conf*100:.1f}%)", (full_x1, full_y1 - 5), font, 0.6, box_color, 2)
                        
                        garment_crop = frame[full_y1:full_y2, full_x1:full_x2]
                        class_idx, prob = check_best_frame(garment_crop)

                        is_best_frame = (class_idx == EXPECTED_BEST_CLASS_INDEX and prob >= BEST_FRAME_CONFIDENCE)

                        if is_best_frame or stable_count >= 10:
                            current_state = "BEST FRAME PROCESSED!"
                            
                            # Backend එකට දත්ත යැවීම
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
                                "confidence": round(conf * 100, 2),
                                "image_base64": img_base64
                            }
                            
                            try:
                                requests.post("http://127.0.0.1:8000/api/garments/", json=api_data)
                            except:
                                pass

                            cooldown_timer = COOLDOWN_FRAMES
                            stable_count = 0
                        else:
                            current_state = "VERIFYING FRAME..."
            
            if not garment_detected:
                stable_count = 0

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