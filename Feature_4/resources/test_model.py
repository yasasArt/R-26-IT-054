import numpy as np
import cv2
from tensorflow.keras.models import load_model

print("Model එක Load වෙමින් පවතී...")
# 1. අපි Train කරපු Model එක load කරගැනීම
model = load_model('models/best_frame_model.h5')

# Classes ටික අකාරාදී පිළිවෙලට (INVALID, NOT_READY, VALID)
class_labels = {0: 'INVALID', 1: 'NOT_READY', 2: 'VALID'}

# 2. Test කරන්න ඕනේ පින්තූරය තෝරාගැනීම 
# (මෙතනට ඔයාගේ folder එකේ තියෙන කැමති පින්තූරයක path එකක් දෙන්න)
test_image_path = 'dataset/frames/v01/v01_001.jpg' 

print(f"Test Image Path: {test_image_path}")

# 3. පින්තූරය මොඩලයට ගැලපෙන සේ සකස් කිරීම
img = cv2.imread(test_image_path)

if img is not None:
    img_resized = cv2.resize(img, (224, 224))
    img_normalized = img_resized / 255.0
    # Model එකට දෙන්න ඕනේ (Batch, Height, Width, Channels) විදිහට නිසා dimension එකක් වැඩි කරනවා
    img_expanded = np.expand_dims(img_normalized, axis=0) 

    # 4. Model එකෙන් Prediction එක ලබා ගැනීම
    prediction = model.predict(img_expanded)
    
    # වැඩිම සම්භාවිතාවක් තියෙන class එක තෝරාගැනීම
    predicted_class_index = np.argmax(prediction)
    predicted_label = class_labels[predicted_class_index]
    
    # ප්‍රතිශතය ගණනය කිරීම
    confidence = prediction[0][predicted_class_index] * 100

    print("\n" + "="*40)
    print(f"final result : {predicted_label}")
    print(f"confidence  : {confidence:.2f}%")
    print("="*40 + "\n")
else:
    print("Error: Test image not found. Please check the image path.")