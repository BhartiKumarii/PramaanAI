#!/usr/bin/env python3
"""
Fix face detection issues by improving the detection algorithm
and adding fallback methods for document images.
"""

import cv2
import numpy as np
from PIL import Image
import io
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_different_face_detectors(image_path):
    """Test different face detection methods"""
    print(f"Testing face detection methods on: {image_path}")

    # Load image
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    pil_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img_array = np.array(pil_image)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

    print(f"Image size: {img_array.shape}")

    # Test 1: Current Haar cascade (default)
    try:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces1 = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
        print(f"Method 1 (Haar default): Found {len(faces1)} faces")
        for i, (x, y, w, h) in enumerate(faces1):
            print(f"  Face {i+1}: ({x}, {y}, {w}, {h})")
    except Exception as e:
        print(f"Method 1 failed: {e}")

    # Test 2: More sensitive Haar cascade settings
    try:
        faces2 = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30), maxSize=(300, 300))
        print(f"Method 2 (Haar sensitive): Found {len(faces2)} faces")
        for i, (x, y, w, h) in enumerate(faces2):
            print(f"  Face {i+1}: ({x}, {y}, {w}, {h})")
    except Exception as e:
        print(f"Method 2 failed: {e}")

    # Test 3: Profile face detector
    try:
        profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
        faces3 = profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        print(f"Method 3 (Profile): Found {len(faces3)} faces")
        for i, (x, y, w, h) in enumerate(faces3):
            print(f"  Face {i+1}: ({x}, {y}, {w}, {h})")
    except Exception as e:
        print(f"Method 3 failed: {e}")

    # Test 4: Alternative face cascade
    try:
        alt_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt.xml')
        faces4 = alt_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        print(f"Method 4 (Alt frontal): Found {len(faces4)} faces")
        for i, (x, y, w, h) in enumerate(faces4):
            print(f"  Face {i+1}: ({x}, {y}, {w}, {h})")
    except Exception as e:
        print(f"Method 4 failed: {e}")

    # Test 5: Enhanced preprocessing
    try:
        # Enhance contrast and normalize
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)

        # Try on enhanced image
        faces5 = face_cascade.detectMultiScale(enhanced, scaleFactor=1.05, minNeighbors=3, minSize=(25, 25), maxSize=(400, 400))
        print(f"Method 5 (Enhanced preprocessing): Found {len(faces5)} faces")
        for i, (x, y, w, h) in enumerate(faces5):
            print(f"  Face {i+1}: ({x}, {y}, {w}, {h})")
    except Exception as e:
        print(f"Method 5 failed: {e}")

    # Test 6: Multiple scales
    try:
        all_faces = []
        for scale in [1.03, 1.05, 1.1, 1.2]:
            for neighbors in [3, 4, 5]:
                faces_temp = face_cascade.detectMultiScale(gray, scaleFactor=scale, minNeighbors=neighbors, minSize=(20, 20), maxSize=(500, 500))
                all_faces.extend(faces_temp)

        # Remove duplicates (simple overlap check)
        unique_faces = []
        for face in all_faces:
            is_duplicate = False
            for existing in unique_faces:
                # Check if faces overlap significantly
                overlap = calculate_overlap(face, existing)
                if overlap > 0.5:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_faces.append(face)

        print(f"Method 6 (Multiple scales): Found {len(unique_faces)} unique faces")
        for i, (x, y, w, h) in enumerate(unique_faces):
            print(f"  Face {i+1}: ({x}, {y}, {w}, {h})")
    except Exception as e:
        print(f"Method 6 failed: {e}")

def calculate_overlap(face1, face2):
    """Calculate overlap between two face rectangles"""
    x1, y1, w1, h1 = face1
    x2, y2, w2, h2 = face2

    # Calculate intersection
    x_left = max(x1, x2)
    y_top = max(y1, y2)
    x_right = min(x1 + w1, x2 + w2)
    y_bottom = min(y1 + h1, y2 + h2)

    if x_right <= x_left or y_bottom <= y_top:
        return 0

    intersection = (x_right - x_left) * (y_bottom - y_top)
    area1 = w1 * h1
    area2 = w2 * h2
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0

def main():
    """Test face detection on sample images"""
    data_dir = Path("./data/processed")
    if data_dir.exists():
        image_files = list(data_dir.glob("*.jpg"))[:3]  # Test first 3 images

        for img_file in image_files:
            print("=" * 80)
            test_different_face_detectors(img_file)
            print()
    else:
        print("No sample images found")

if __name__ == "__main__":
    main()