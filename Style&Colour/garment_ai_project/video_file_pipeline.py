import cv2
import numpy as np
import sys
from tensorflow.keras.models import load_model
from ultralytics import YOLO

print("Loading models... Please wait.")

# 1. මොඩල දෙකම Load කරගැනීම
model1_state = load_model('models/best_frame_model.h5')
model2_style = YOLO('models/best.pt')

print("Models loaded successfully!")

# --- ඔයාගේ වීඩියෝ එකේ නම මෙතනට දෙන්න ---
VIDEO_PATH = "dataset/videos/v25.mp4" 

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print(f"Error: Could not open video file -> {VIDEO_PATH}")
    sys.exit(1)

highest_valid_score = 0.0
best_frame = None

# --- වේගවත් කිරීම සඳහා අලුතෙන් එකතු කළ ආරම්භක අගයන් ---
frame_count = 0
current_state = 'NOT_READY'
state_confidence = 0.0
color = (0, 255, 255)

print(f"\nPlaying and Analyzing video: {VIDEO_PATH}")
print("Press 'q' if you want to skip to the end.")

# 2. වීඩියෝව Play වන අතරතුර Model 1 හරහා රාමු පරීක්ෂා කිරීම
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break # වීඩියෝව අවසන් වූ විට loop එකෙන් ඉවත් වේ
        
    frame_count += 1
    
    # --- වෙනස 1: වීඩියෝවේ වේගය පවත්වා ගැනීමට රාමු 3කට වරක් පමණක් AI පරීක්ෂාව කිරීම ---
    if frame_count % 3 == 0:
        # Model 1 සඳහා රූපය සකස් කිරීම
        img_resized = cv2.resize(frame, (224, 224))
        img_normalized = img_resized / 255.0
        img_expanded = np.expand_dims(img_normalized, axis=0)
        
        # --- වෙනස 2: predict() වෙනුවට ඉතා වේගවත් numpy ක්‍රමය භාවිතා කිරීම ---
        prediction1 = model1_state(img_expanded, training=False).numpy()
        
        invalid_score = prediction1[0][0] * 100
        not_ready_score = prediction1[0][1] * 100
        valid_score = prediction1[0][2] * 100
        
        # --- තිරයේ පෙන්වීම සඳහා State එක තෝරාගැනීම ---
        if valid_score > 35.0:
            current_state = 'VALID'
            state_confidence = valid_score
            color = (0, 255, 0) # Green
        elif invalid_score > 50.0:
            current_state = 'INVALID'
            state_confidence = invalid_score
            color = (0, 0, 255) # Red
        else:
            current_state = 'NOT_READY'
            state_confidence = not_ready_score
            color = (0, 255, 255) # Yellow

        # වැඩිම VALID ලකුණ ඇති රාමුව (Best Frame) මතක තබා ගැනීම
        if valid_score > highest_valid_score:
            highest_valid_score = valid_score
            best_frame = frame.copy() # රාමුව කොපි කර තබාගනී

    # වීඩියෝව මත State එක ලිවීම (AI එක check නොකරන රාමු වලදීමත් කලින් State එකම පෙන්වයි)
    display_frame = frame.copy()
    cv2.putText(display_frame, f"State: {current_state} ({state_confidence:.1f}%)", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    # Play වන වීඩියෝව තිරයේ පෙන්වීම
    cv2.imshow("Video Processing...", display_frame)
    
    # වීඩියෝ එක Skip කරන්න ඕනේ නම් 'q' ඔබන්න
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Skipping to the end...")
        break

# Video window එක close කිරීම
cap.release()
cv2.destroyAllWindows()

# 3. වීඩියෝව අවසන් වූ පසු, Best Frame එක Model 2 (YOLO) වෙත ලබා දීම
if best_frame is not None and highest_valid_score > 35.0:
    print("\n" + "="*50)
    print(f"Best Frame Found with VALID Probability : {highest_valid_score:.2f}%")
    print("Running Style Detection on the Best Frame...")
    
    results = model2_style(best_frame, verbose=False)
    result = results[0]
    
    style_name = "Unknown"
    confidence = 0.0
    
    # YOLO ප්‍රතිඵල ලබාගැනීම
    if result.probs is not None:
        top1_index = result.probs.top1
        style_name = result.names[top1_index]
        confidence = float(result.probs.top1conf.item()) * 100
    elif result.boxes is not None and len(result.boxes) > 0:
        box = result.boxes[0] 
        cls_index = int(box.cls[0].item())
        style_name = result.names[cls_index]
        confidence = float(box.conf[0].item()) * 100
        
    MIN_CONFIDENCE = 50.0 
    
    # අවසාන ප්‍රතිඵලය තීරණය කිරීම
    if confidence >= MIN_CONFIDENCE:
        print(f"Detected Style      : ** {style_name.upper()} ** ({confidence:.2f}%)")
        display_text = f"Final Style: {style_name.upper()} ({confidence:.1f}%)"
        final_color = (0, 255, 0)
    else:
        print(f"Detected Style      : ** UNKNOWN / LOW CONFIDENCE **")
        print(f"Note: Model guessed '{style_name}' with only {confidence:.2f}% confidence.")
        display_text = "UNKNOWN (Low Confidence)"
        final_color = (0, 0, 255)
        
    print("="*50 + "\n")
    
    # 4. අවසාන Best Frame එක සහ Style එක අලුත් Window එකක පෙන්වීම
    cv2.putText(best_frame, display_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, final_color, 3)
    cv2.imshow("Final Result: Best Frame & Style", best_frame)
    
    print("Press any key on the image window to close it...")
    cv2.waitKey(0) 
    cv2.destroyAllWindows()
    
else:
    print("\nWARNING: Could not find any clear (VALID) frame in this video.")