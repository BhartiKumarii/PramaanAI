#!/usr/bin/env python3
"""
Test face matching with real passport/ID images that contain faces
"""

import os
import sys
import base64
import json
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.face.enhanced_provider import EnhancedFaceProvider, EnhancedFaceDetector


def test_face_matching_with_passport():
    """Test face matching using the passport image"""

    passport_path = "/tmp/ID_DOCUMENT_DATASET/India/Passport/Indianpassportbiopage2025.jpg"

    if not os.path.exists(passport_path):
        print("Passport image not found!")
        return

    print("Testing Face Matching with Real Passport Image")
    print("=" * 60)

    # Initialize face components
    face_detector = EnhancedFaceDetector()
    face_provider = EnhancedFaceProvider()

    # Read passport image
    with open(passport_path, 'rb') as f:
        passport_bytes = f.read()

    print(f"Testing image: {passport_path}")
    print(f"Image size: {len(passport_bytes)} bytes")

    # Test face detection
    print("\nStep 1: Face Detection")
    print("-" * 30)

    detection = face_detector.detect(passport_bytes)
    print(f"Detection status: {detection.status}")
    print(f"Reason: {detection.reason}")
    print(f"Faces found: {len(detection.faces)}")

    for i, face in enumerate(detection.faces):
        print(f"  Face {i+1}:")
        print(f"    Confidence: {face.confidence:.3f}")
        print(f"    Location: {face.location}")
        print(f"    Touches edge: {face.touches_edge}")

    if detection.status == "SINGLE_FACE" or detection.status == "MULTIPLE_FACES":
        face = detection.faces[0]

        # Test quality assessment
        print("\nStep 2: Face Quality Assessment")
        print("-" * 30)

        quality = face_detector.assess_face_quality(passport_bytes, face.location)
        print(f"Quality metrics:")
        print(f"  Sharpness: {quality.sharpness:.2f}")
        print(f"  Brightness: {quality.brightness:.2f}")
        print(f"  Contrast: {quality.contrast:.2f}")
        print(f"  Size (pixels): {quality.size_pixels}")
        print(f"  Pose quality: {quality.pose_quality:.2f}")
        print(f"  Eye visibility: {quality.eye_visibility:.2f}")
        print(f"  Mouth visibility: {quality.mouth_visibility:.2f}")

        # Test spoof detection
        print("\nStep 3: Spoof Detection")
        print("-" * 30)

        spoof_indicators = face_detector.detect_spoof_indicators(passport_bytes, face.location)
        print(f"Spoof analysis:")
        print(f"  Screen reflection: {spoof_indicators.screen_reflection_score:.3f}")
        print(f"  Print texture: {spoof_indicators.print_texture_score:.3f}")
        print(f"  Depth consistency: {spoof_indicators.depth_consistency:.3f}")
        print(f"  Edge artifacts: {spoof_indicators.edge_artifacts:.3f}")
        print(f"  Motion blur: {spoof_indicators.motion_blur_score:.3f}")
        print(f"  Overall spoof probability: {spoof_indicators.overall_spoof_probability:.3f}")

        # Test self-matching (should have high similarity)
        print("\nStep 4: Self-Matching Test")
        print("-" * 30)

        match_result = face_provider.verify(passport_bytes, passport_bytes)
        print(f"Self-match result:")
        print(f"  Match: {match_result.match}")
        print(f"  Similarity: {match_result.similarity:.4f}")
        print(f"  Confidence: {match_result.confidence:.4f}")
        print(f"  Threshold: {face_provider.match_threshold}")
        print(f"  Reason: {match_result.reason}")

        # Test against other images if available
        print("\nStep 5: Cross-Image Testing")
        print("-" * 30)

        other_images = []
        dataset_dir = Path("/tmp/ID_DOCUMENT_DATASET")

        # Find other passport/ID images
        for country in ["India", "Nepal", "Bhutan"]:
            country_path = dataset_dir / country
            if country_path.exists():
                for img_type in ["Passport", "Visa", "DriverLicense"]:
                    type_path = country_path / img_type
                    if type_path.exists():
                        for img_file in type_path.glob("*.jpg"):
                            if img_file != Path(passport_path):
                                other_images.append(img_file)

        # Test with up to 3 other images
        for i, other_img_path in enumerate(other_images[:3]):
            print(f"\n  Testing against: {other_img_path.name}")

            try:
                with open(other_img_path, 'rb') as f:
                    other_bytes = f.read()

                cross_match = face_provider.verify(passport_bytes, other_bytes)
                print(f"    Match: {cross_match.match}")
                print(f"    Similarity: {cross_match.similarity:.4f}")
                print(f"    Confidence: {cross_match.confidence:.4f}")
                print(f"    Reason: {cross_match.reason[:100]}...")

            except Exception as e:
                print(f"    Error: {str(e)}")

    else:
        print("Cannot proceed - no faces detected")

        # Debug why detection failed
        print("\nDebug Information:")
        print("-" * 30)

        # Check if it's using the fallback detector
        if hasattr(face_detector, 'net') and face_detector.net == "contour_based":
            print("Using contour-based fallback detector")

            # Try manual analysis
            from PIL import Image
            import numpy as np
            import cv2
            import io

            pil_image = Image.open(io.BytesIO(passport_bytes)).convert('RGB')
            img_array = np.array(pil_image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            print(f"Image dimensions: {img_array.shape}")
            print(f"Image stats - min: {np.min(gray)}, max: {np.max(gray)}, mean: {np.mean(gray):.1f}")

            # Try contour detection manually
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            print(f"Found {len(contours)} contours")

            # Show largest contours
            large_contours = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w * h > 1000:  # Significant area
                    large_contours.append((x, y, w, h, w*h))

            large_contours.sort(key=lambda x: x[4], reverse=True)  # Sort by area
            print("Largest contours:")
            for i, (x, y, w, h, area) in enumerate(large_contours[:5]):
                print(f"  {i+1}. ({x}, {y}, {w}, {h}) area: {area}")


def main():
    """Main test function"""
    test_face_matching_with_passport()


if __name__ == "__main__":
    main()