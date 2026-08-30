from pathlib import Path

import cv2


IMAGE_PATH = Path(
    "data/measurement_dataset/sample_best_frames/sample_01.jpg"
)


def main():
    image = cv2.imread(str(IMAGE_PATH))

    if image is None:
        print(f"ERROR: Image එක සොයාගත නොහැක: {IMAGE_PATH}")
        return

    image_height, image_width = image.shape[:2]

    print("----- Camera and Image Information -----")
    print("Camera height: 120 cm")
    print(f"Image width: {image_width} pixels")
    print(f"Image height: {image_height} pixels")
    print(f"Image resolution: {image_width} x {image_height}")


if __name__ == "__main__":
    main()