#!/usr/bin/env python3
"""Test face matching with real Aadhaar card images"""

import sys
import os
sys.path.append('/home/bharti/PramaanAI')

from app.services.verification.comprehensive_engine import ComprehensiveVerificationEngine
from app.db.session import SessionLocal
from PIL import Image
import io
import glob

def test_with_real_images():
    """Test face matching with real Aadhaar card images"""

    # Find available test images
    image_files = glob.glob('/home/bharti/PramaanAI/data/processed/*.jpg')
    if len(image_files) < 1:
        print("No test images found!")
        return

    print(f"Found {len(image_files)} test images")

    # Use first image as both document and selfie (should give high similarity)
    test_image_path = image_files[0]
    print(f"Using test image: {test_image_path}")

    # Load the image
    with open(test_image_path, 'rb') as f:
        image_bytes = f.read()

    print(f"Image size: {len(image_bytes)} bytes")

    # Create a slightly modified version for "selfie"
    # (In real testing, these would be different images of the same person)
    with Image.open(test_image_path) as img:
        # Create a slightly modified version
        modified_img = img.copy()
        width, height = modified_img.size

        # Add slight brightness variation (simulate different lighting)
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(modified_img)
        modified_img = enhancer.enhance(1.1)  # 10% brighter

        # Convert back to bytes
        buffer = io.BytesIO()
        modified_img.save(buffer, format='JPEG', quality=90)
        modified_bytes = buffer.getvalue()

    print(f"Modified image size: {len(modified_bytes)} bytes")

    # Initialize verification engine
    print("\nInitializing verification engine...")
    db = SessionLocal()
    try:
        engine = ComprehensiveVerificationEngine(db)

        # Test 1: Same image (should be very high similarity)
        print("\n" + "="*60)
        print("TEST 1: SAME IMAGE (should be ~1.0 similarity)")
        print("="*60)

        result1 = engine.face_provider.verify(image_bytes, image_bytes)
        print(f"\nSame image result:")
        print(f"  Match: {result1.match}")
        print(f"  Similarity: {result1.similarity}")
        print(f"  Confidence: {result1.confidence}")
        print(f"  Reason: {result1.reason}")

        # Test 2: Slightly modified version (should be high similarity)
        print("\n" + "="*60)
        print("TEST 2: SLIGHTLY MODIFIED VERSION")
        print("="*60)

        result2 = engine.face_provider.verify(image_bytes, modified_bytes)
        print(f"\nModified image result:")
        print(f"  Match: {result2.match}")
        print(f"  Similarity: {result2.similarity}")
        print(f"  Confidence: {result2.confidence}")
        print(f"  Reason: {result2.reason}")

        # Test 3: Different image (should be lower similarity)
        if len(image_files) >= 2:
            print("\n" + "="*60)
            print("TEST 3: DIFFERENT PERSON (should be low similarity)")
            print("="*60)

            with open(image_files[1], 'rb') as f:
                different_bytes = f.read()

            result3 = engine.face_provider.verify(image_bytes, different_bytes)
            print(f"\nDifferent person result:")
            print(f"  Match: {result3.match}")
            print(f"  Similarity: {result3.similarity}")
            print(f"  Confidence: {result3.confidence}")
            print(f"  Reason: {result3.reason}")

    finally:
        db.close()

    print("\nTest completed!")

if __name__ == "__main__":
    test_with_real_images()