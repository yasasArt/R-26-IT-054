import cv2
import datetime
import sys
from ultralytics import YOLO

# --- CONFIGURATION ---
# model path for YOLOv8
MODEL_PATH = "models/best.pt"

# --- Thresholds to separate states ---
# minimum value for INVALID state (මුකුත් නැත)
MIN_CONFIDENCE_THRESHOLD = 0.50  # 50%
# maximum value for VALID state - if higher than this, it's VALID (හොඳින් පෙනේ)
HIGH_CONFIDENCE_THRESHOLD = 0.80  # 80%

# Load the trained model
try:
    model = YOLO(MODEL_PATH)
    print(f"Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"Error loading model from {MODEL_PATH}: {e}")
    sys.exit(1)

# Get the webcam feed
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    sys.exit(1)

# Setup basic screen text properties
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 1.0
thickness = 2
text_margin_x = 10
text_margin_y = 30

print("\nStarting live webcam pipeline. Press 'q' to quit.")
print("The style will be printed to the terminal ONLY on a VALID frame.")
print("Waiting for input...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    display_frame = frame.copy()
    
    # Run model inference
    results = model(frame, verbose=False)

    current_state = "INVALID"
    display_color = (0, 0, 255) # Red for INVALID state
    best_detection_info = None 

    # Process detections
    for r in results:
        best_box = None
        if len(r.boxes) > 0:
            best_box = r.boxes[0]

        if best_box is not None:
            conf_score = float(best_box.conf)
            class_idx = int(best_box.cls)
            class_name = model.names[class_idx]

            # --- State Machine Logic ---
            if conf_score > HIGH_CONFIDENCE_THRESHOLD:
                current_state = "VALID"
                display_color = (0, 255, 0) # Green 
                best_detection_info = (class_name, conf_score)
                break 
            elif conf_score > MIN_CONFIDENCE_THRESHOLD:
                current_state = "NOT READY"
                display_color = (0, 255, 255) # Yellow 
                best_detection_info = (class_name, conf_score)
                break

    # --- Terminal Output (only for VALID frames) ---
    if current_state == "VALID" and best_detection_info is not None:
        term_style_name, term_conf_value = best_detection_info
        current_time = datetime.datetime.now().strftime("[%H:%M:%S]")
        print(f"{current_time} Detected: ** {term_style_name.upper()} ** ({term_conf_value * 100:.2f}%) - Frame: VALID")

    # --- Draw State on Video Screen ---
    state_text = f"STATE: {current_state}"
    cv2.putText(display_frame, state_text, (text_margin_x, text_margin_y), 
                font, font_scale, display_color, thickness, cv2.LINE_AA)
    
    # --- Draw Bounding Box
    if best_detection_info is not None and best_box is not None:
        draw_style_name, draw_conf_value = best_detection_info # add name and confidence
        b = best_box.xyxy[0] 
        cv2.rectangle(display_frame, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), display_color, thickness)
        
        # precentage label multiply by 100 to convert to percentage
        label_text = f"{draw_style_name.upper()}: {draw_conf_value * 100:.1f}%"
        cv2.putText(display_frame, label_text, (int(b[0]), int(b[1]) - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, display_color, 2, cv2.LINE_AA)

    # Show the video feed
    cv2.imshow("Garment Pipeline Feed", display_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("\nPipeline stopped.")