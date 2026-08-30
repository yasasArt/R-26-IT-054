import os
import pandas as pd
from sklearn.model_selection import train_test_split
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# 1. දත්ත (Data) සකස් කරගැනීම
csv_path = 'dataset/labels.csv'
frames_dir = 'dataset/frames/'

print("loading CSV file and preparing DataFrame...")
df = pd.read_csv(csv_path)

# රූපය තිබෙන සම්පූර්ණ path එක අලුත් column එකක් විදිහට DataFrame එකට එකතු කිරීම
# උදා: dataset/frames/v01/v01_001.jpg
df['filepath'] = df.apply(lambda row: os.path.join(frames_dir, str(row['video_id']), str(row['frame_id']) + '.jpg'), axis=1)

# Training (80%) සහ Validation (20%) විදිහට දත්ත බෙදීම
train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)

print(f"Training images : {len(train_df)}")
print(f"Validation images : {len(val_df)}")

# 2. Data Generators සකස් කිරීම (Memory Error එක වළක්වා ගැනීමට)
# rescale=1./255 මගින් අපි කලින් කරපු Feature Scaling (Normalization) එක ස්වයංක්‍රීයව සිදු වේ
datagen = ImageDataGenerator(rescale=1./255)

print("\nCreating Training Generator...")
train_generator = datagen.flow_from_dataframe(
    dataframe=train_df,
    x_col="filepath",
    y_col="state", # අපේ labels තියෙන column එක (VALID, INVALID, NOT_READY)
    target_size=(224, 224),
    batch_size=32, # එකවර RAM එකට ගන්නේ රූප 32ක් පමණි
    class_mode="categorical"
)

print("Creating Validation Generator...")
val_generator = datagen.flow_from_dataframe(
    dataframe=val_df,
    x_col="filepath",
    y_col="state",
    target_size=(224, 224),
    batch_size=32,
    class_mode="categorical"
)

# 3. Model එක නිර්මාණය කිරීම
print("\nModel is being created...")
base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
base_model.trainable = False 

model = Sequential([
    base_model,
    GlobalAveragePooling2D(),
    Dropout(0.5), 
    Dense(3, activation='softmax') # Classes 3ක් ඇති නිසා (VALID, INVALID, NOT_READY)
])

model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

# 4. Model එක Train කිරීම
print("\nTraining is starting! (This will take some time)...")
# Generator භාවිතයෙන් model එක train කිරීම
history = model.fit(
    train_generator,
    epochs=10,
    validation_data=val_generator
)

# 5. Train කළ Model එක Save කරගැනීම
if not os.path.exists('models'):
    os.makedirs('models')

model.save('models/best_frame_model.h5')
print("\nModel is saved successfully as 'models/best_frame_model.h5'!")