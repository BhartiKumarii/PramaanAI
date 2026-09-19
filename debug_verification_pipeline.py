#!/usr/bin/env python3
"""
Debug script to trace the entire verification pipeline and identify issues
with face matching, liveness detection, document forensics, and deepfake detection.
"""

import os
import sys
import base64
import json
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.face.enhanced_provider import EnhancedFaceProvider, EnhancedFaceDetector
from app.services.liveness.advanced_provider import AdvancedLivenessProvider
from app.services.tampering.forensics_provider import ComprehensiveForensicsProvider
from app.services.deepfake.advanced_provider import AdvancedDeepfakeProvider
from app.services.verification.comprehensive_engine import ComprehensiveVerificationEngine
from app.db.session import SessionLocal


def load_sample_images():
    """Load sample images for testing"""
    # Find first available document images
    data_dir = Path("./data/processed")
    if data_dir.exists():
        image_files = list(data_dir.glob("*.jpg")) + list(data_dir.glob("*.png")) + list(data_dir.glob("*.jpeg"))
        if image_files:
            print(f"Found {len(image_files)} images in {data_dir}")
            return image_files[:2]  # Use first 2 images

    print("No sample images found")
    return []


def debug_face_matching(image1_path: Path, image2_path: Path):
    """Debug face matching step by step"""
    print("\n" + "="*60)
    print("DEBUGGING FACE MATCHING PIPELINE")
    print("="*60)

    # Read image files
    with open(image1_path, 'rb') as f:
        img1_bytes = f.read()
    with open(image2_path, 'rb') as f:
        img2_bytes = f.read()

    print(f"\nImage 1: {image1_path} ({len(img1_bytes)} bytes)")
    print(f"Image 2: {image2_path} ({len(img2_bytes)} bytes)")

    # Initialize face components
    face_detector = EnhancedFaceDetector()
    face_provider = EnhancedFaceProvider()

    print("\nStep 1: Face Detection")
    print("-" * 30)

    # Detect faces in both images
    detection1 = face_detector.detect(img1_bytes)
    detection2 = face_detector.detect(img2_bytes)

    print(f"Image 1 detection: {detection1.status}")
    print(f"  Reason: {detection1.reason}")
    print(f"  Faces found: {len(detection1.faces)}")
    for i, face in enumerate(detection1.faces):
        print(f"    Face {i+1}: confidence={face.confidence:.3f}, location={face.location}, touches_edge={face.touches_edge}")

    print(f"\nImage 2 detection: {detection2.status}")
    print(f"  Reason: {detection2.reason}")
    print(f"  Faces found: {len(detection2.faces)}")
    for i, face in enumerate(detection2.faces):
        print(f"    Face {i+1}: confidence={face.confidence:.3f}, location={face.location}, touches_edge={face.touches_edge}")

    if detection1.status == "SINGLE_FACE" and detection2.status == "SINGLE_FACE":
        print("\nStep 2: Face Quality Assessment")
        print("-" * 30)

        face1 = detection1.faces[0]
        face2 = detection2.faces[0]

        quality1 = face_detector.assess_face_quality(img1_bytes, face1.location)
        quality2 = face_detector.assess_face_quality(img2_bytes, face2.location)

        print(f"Image 1 quality:")
        print(f"  Sharpness: {quality1.sharpness:.2f}")
        print(f"  Brightness: {quality1.brightness:.2f}")
        print(f"  Contrast: {quality1.contrast:.2f}")
        print(f"  Size (pixels): {quality1.size_pixels}")
        print(f"  Pose quality: {quality1.pose_quality:.2f}")

        print(f"\nImage 2 quality:")
        print(f"  Sharpness: {quality2.sharpness:.2f}")
        print(f"  Brightness: {quality2.brightness:.2f}")
        print(f"  Contrast: {quality2.contrast:.2f}")
        print(f"  Size (pixels): {quality2.size_pixels}")
        print(f"  Pose quality: {quality2.pose_quality:.2f}")

        print("\nStep 3: Embedding Extraction & Similarity")
        print("-" * 30)

        # Test face verification
        match_result = face_provider.verify(img1_bytes, img2_bytes)

        print(f"Face verification result:")
        print(f"  Match: {match_result.match}")
        print(f"  Similarity: {match_result.similarity}")
        print(f"  Confidence: {match_result.confidence}")
        print(f"  Threshold: {face_provider.match_threshold}")
        print(f"  Reason: {match_result.reason}")

    else:
        print("\nCannot proceed with face matching - face detection failed")


def debug_liveness_detection(image_path: Path):
    """Debug liveness detection"""
    print("\n" + "="*60)
    print("DEBUGGING LIVENESS DETECTION")
    print("="*60)

    with open(image_path, 'rb') as f:
        img_bytes = f.read()

    print(f"\nTesting image: {image_path} ({len(img_bytes)} bytes)")

    liveness_provider = AdvancedLivenessProvider()

    try:
        result = liveness_provider.analyze(img_bytes)
        print(f"\nLiveness analysis result:")
        print(f"  Status: {result.status}")
        print(f"  Score: {result.score}")
        print(f"  Reason: {result.reason}")
    except Exception as e:
        print(f"\nLiveness detection ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


def debug_document_forensics(image_path: Path):
    """Debug document forensics"""
    print("\n" + "="*60)
    print("DEBUGGING DOCUMENT FORENSICS")
    print("="*60)

    with open(image_path, 'rb') as f:
        img_bytes = f.read()

    print(f"\nTesting image: {image_path} ({len(img_bytes)} bytes)")

    forensics_provider = ComprehensiveForensicsProvider()

    try:
        result = forensics_provider.analyze(img_bytes)
        print(f"\nForensics analysis result:")
        print(f"  Tampering risk: {result.tampering_risk}")
        print(f"  Findings count: {len(result.findings)}")

        for i, finding in enumerate(result.findings[:5]):  # Show first 5 findings
            print(f"    Finding {i+1}:")
            print(f"      Type: {finding.type}")
            print(f"      Confidence: {finding.confidence}")
            print(f"      Reason: {finding.reason}")
            print(f"      Location: {finding.location}")
    except Exception as e:
        print(f"\nDocument forensics ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


def debug_deepfake_detection(image_path: Path):
    """Debug deepfake detection"""
    print("\n" + "="*60)
    print("DEBUGGING DEEPFAKE DETECTION")
    print("="*60)

    with open(image_path, 'rb') as f:
        img_bytes = f.read()

    print(f"\nTesting image: {image_path} ({len(img_bytes)} bytes)")

    deepfake_provider = AdvancedDeepfakeProvider()

    try:
        result = deepfake_provider.analyze(img_bytes)
        print(f"\nDeepfake analysis result:")
        print(f"  Status: {result.status}")
        print(f"  Score: {result.score}")
        print(f"  Reason: {result.reason}")
    except Exception as e:
        print(f"\nDeepfake detection ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


def debug_comprehensive_verification(doc_image_path: Path, selfie_image_path: Path):
    """Debug the complete verification engine"""
    print("\n" + "="*60)
    print("DEBUGGING COMPREHENSIVE VERIFICATION ENGINE")
    print("="*60)

    with open(doc_image_path, 'rb') as f:
        doc_bytes = f.read()
    with open(selfie_image_path, 'rb') as f:
        selfie_bytes = f.read()

    print(f"\nDocument image: {doc_image_path} ({len(doc_bytes)} bytes)")
    print(f"Selfie image: {selfie_image_path} ({len(selfie_bytes)} bytes)")

    # Mock OCR fields for testing
    ocr_fields = {
        "name": "TEST USER",
        "date_of_birth": "01/01/1990",
        "document_number": "123456789012",
        "nationality": "INDIAN",
        "gender": "M",
        "issue_date": "01/01/2020",
        "expiry_date": "01/01/2030"
    }

    print(f"Mock OCR fields: {ocr_fields}")

    # Initialize database session
    db = SessionLocal()

    try:
        engine = ComprehensiveVerificationEngine(db)

        result = engine.verify_comprehensive(
            document_image_bytes=doc_bytes,
            selfie_image_bytes=selfie_bytes,
            ocr_fields=ocr_fields,
            document_type="aadhaar",
            nationality="INDIAN"
        )

        print(f"\nComprehensive verification result:")
        print(f"  Overall status: {result.overall_status}")
        print(f"  Risk level: {result.risk_level}")
        print(f"  Confidence score: {result.confidence_score}")
        print(f"  Verification summary: {result.verification_summary}")

        print(f"\nDocument conditions ({len(result.document_conditions)}):")
        for cond in result.document_conditions:
            print(f"  - {cond.condition_type}: {cond.status} ({cond.severity}) - {cond.message}")

        print(f"\nFace conditions ({len(result.face_conditions)}):")
        for cond in result.face_conditions:
            print(f"  - {cond.condition_type}: {cond.status} ({cond.severity}) - {cond.message}")

        print(f"\nTampering conditions ({len(result.tampering_conditions)}):")
        for cond in result.tampering_conditions:
            print(f"  - {cond.condition_type}: {cond.status} ({cond.severity}) - {cond.message}")

        print(f"\nIdentity conditions ({len(result.identity_conditions)}):")
        for cond in result.identity_conditions:
            print(f"  - {cond.condition_type}: {cond.status} ({cond.severity}) - {cond.message}")

        print(f"\nOfficer recommendations:")
        for rec in result.officer_recommendations:
            print(f"  - {rec}")

        print(f"\nRequired actions:")
        for action in result.required_actions:
            print(f"  - {action}")

        print(f"\nTechnical details:")
        for key, value in result.technical_details.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"\nComprehensive verification ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """Main debugging function"""
    print("PramaanAI Verification Pipeline Debugging")
    print("=" * 60)

    # Load sample images
    sample_images = load_sample_images()

    if len(sample_images) >= 2:
        img1, img2 = sample_images[0], sample_images[1]
        print(f"Using images: {img1} and {img2}")

        # Debug each component
        debug_face_matching(img1, img2)
        debug_liveness_detection(img2)  # Use second image as "selfie"
        debug_document_forensics(img1)  # Use first image as "document"
        debug_deepfake_detection(img2)  # Use second image for deepfake detection
        debug_comprehensive_verification(img1, img2)

    else:
        print("Not enough sample images found for testing")

    print("\n" + "="*60)
    print("DEBUGGING COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()