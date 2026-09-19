#!/usr/bin/env python3
"""Debug face matching pipeline with comprehensive logging"""

import sys
import os
sys.path.append('/home/bharti/PramaanAI')

from app.services.verification.comprehensive_engine import ComprehensiveVerificationEngine
from app.db.session import SessionLocal
from PIL import Image
import io

def test_face_matching_debug():
    """Test face matching with debug logging"""

    # Create a simple test image (solid color square)
    print("Creating test images...")

    # Create a simple test image - 200x200 gray square
    test_img = Image.new('RGB', (200, 200), color=(128, 128, 128))

    # Add some variation to make it more face-like
    for x in range(80, 120):
        for y in range(70, 110):
            # Add "eyes"
            if (85 <= x <= 95 and 80 <= y <= 90) or (105 <= x <= 115 and 80 <= y <= 90):
                test_img.putpixel((x, y), (50, 50, 50))
            # Add "mouth"
            elif 90 <= x <= 110 and 95 <= y <= 105:
                test_img.putpixel((x, y), (50, 50, 50))

    # Convert to bytes
    img_buffer = io.BytesIO()
    test_img.save(img_buffer, format='JPEG')
    test_image_bytes = img_buffer.getvalue()

    print(f"Test image size: {len(test_image_bytes)} bytes")

    # Create a slightly different version for document
    doc_img = test_img.copy()
    # Add slight variation
    for x in range(75, 125):
        for y in range(75, 125):
            pixel = doc_img.getpixel((x, y))
            # Slightly brighten
            new_pixel = (min(255, pixel[0] + 10), min(255, pixel[1] + 10), min(255, pixel[2] + 10))
            doc_img.putpixel((x, y), new_pixel)

    doc_buffer = io.BytesIO()
    doc_img.save(doc_buffer, format='JPEG')
    doc_image_bytes = doc_buffer.getvalue()

    print(f"Document image size: {len(doc_image_bytes)} bytes")

    # Test with database session
    print("\nInitializing verification engine...")
    db = SessionLocal()
    engine = ComprehensiveVerificationEngine(db)

    # Test face matching directly
    print("\n" + "="*50)
    print("TESTING FACE MATCHING DIRECTLY")
    print("="*50)

    result = engine.face_provider.verify(doc_image_bytes, test_image_bytes)
    print(f"\nFace matching result:")
    print(f"  Match: {result.match}")
    print(f"  Similarity: {result.similarity}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Reason: {result.reason}")

    # Test with same image
    print("\n" + "="*50)
    print("TESTING SAME IMAGE")
    print("="*50)

    same_result = engine.face_provider.verify(test_image_bytes, test_image_bytes)
    print(f"\nSame image result:")
    print(f"  Match: {same_result.match}")
    print(f"  Similarity: {same_result.similarity}")
    print(f"  Confidence: {same_result.confidence}")
    print(f"  Reason: {same_result.reason}")

    db.close()
    print("\nTest completed!")

if __name__ == "__main__":
    test_face_matching_debug()