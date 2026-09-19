#!/usr/bin/env python3
"""
Test the fixed verification pipeline with the real passport image
to verify all components are working correctly.
"""

import os
import sys
import base64
import json
import requests
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_comprehensive_verification_api():
    """Test the comprehensive verification API with real passport image"""

    passport_path = "/tmp/ID_DOCUMENT_DATASET/India/Passport/Indianpassportbiopage2025.jpg"

    if not os.path.exists(passport_path):
        print("Passport image not found! Please extract the dataset first.")
        return

    print("Testing Fixed Comprehensive Verification API")
    print("=" * 60)

    # Read and encode images
    with open(passport_path, 'rb') as f:
        passport_bytes = f.read()

    # Use same image as both document and selfie for testing
    document_b64 = base64.b64encode(passport_bytes).decode('utf-8')
    selfie_b64 = base64.b64encode(passport_bytes).decode('utf-8')

    # Mock OCR fields from passport
    ocr_fields = {
        "name": "PREETHAL",
        "date_of_birth": "12/07/1984",
        "document_number": "SP003369",
        "nationality": "INDIAN",
        "gender": "F",
        "issue_date": "10/07/2015",
        "expiry_date": "09/07/2025"
    }

    # Mock device info
    device_info = {
        "device_id": "TEST_DEVICE_001",
        "app_version": "1.0.0",
        "os_version": "Android 12",
        "network_status": "ONLINE",
        "timestamp": 1726800000
    }

    # Prepare request
    request_data = {
        "document_image": document_b64,
        "selfie_image": selfie_b64,
        "ocr_fields": ocr_fields,
        "document_type": "passport",
        "nationality": "INDIAN",
        "language": "hi",  # Test Hindi localization
        "device_info": device_info
    }

    print(f"Testing with passport image: {passport_path}")
    print(f"Image size: {len(passport_bytes)} bytes")
    print(f"Document type: {request_data['document_type']}")
    print(f"Language: {request_data['language']}")
    print(f"OCR fields: {ocr_fields}")

    try:
        # First, get authentication token
        print("\nStep 1: Authentication")
        print("-" * 30)

        login_data = {
            "username": "officer1",
            "password": "BorderShield123"
        }

        response = requests.post("http://localhost:8001/auth/login", json=login_data)
        if response.status_code != 200:
            print(f"Login failed: {response.status_code} - {response.text}")
            return

        token = response.json().get("access_token")
        print(f"Login successful, token received: {token[:20]}...")

        # Call comprehensive verification API
        print("\nStep 2: Comprehensive Verification")
        print("-" * 30)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            "http://localhost:8001/documents/comprehensive-verify",
            json=request_data,
            headers=headers,
            timeout=60  # Allow time for processing
        )

        print(f"API Response Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            print(f"\n✅ COMPREHENSIVE VERIFICATION SUCCESSFUL!")
            print(f"Overall Status: {result['overall_status']}")
            print(f"Risk Level: {result['risk_level']}")
            print(f"Confidence Score: {result['confidence_score']:.3f}")
            print(f"Verification Summary: {result['verification_summary']}")

            print(f"\nDocument Conditions ({len(result['document_conditions'])}):")
            for cond in result['document_conditions']:
                status_icon = "✅" if cond['status'] == "PASS" else "❌" if cond['status'] == "FAIL" else "⚠️"
                print(f"  {status_icon} {cond['condition_type']}: {cond['status']} ({cond['severity']}) - {cond['message']}")

            print(f"\nFace Conditions ({len(result['face_conditions'])}):")
            for cond in result['face_conditions']:
                status_icon = "✅" if cond['status'] == "PASS" else "❌" if cond['status'] == "FAIL" else "⚠️"
                print(f"  {status_icon} {cond['condition_type']}: {cond['status']} ({cond['severity']}) - {cond['message']}")

                # Special handling for face match details
                if 'similarity' in cond['details']:
                    print(f"    → Similarity: {cond['details']['similarity']:.4f}")
                if 'confidence' in cond['details']:
                    print(f"    → Confidence: {cond['details']['confidence']:.4f}")

            print(f"\nTampering Conditions ({len(result['tampering_conditions'])}):")
            for i, cond in enumerate(result['tampering_conditions'][:5]):  # Show first 5
                status_icon = "✅" if cond['status'] == "PASS" else "❌" if cond['status'] == "FAIL" else "⚠️"
                print(f"  {status_icon} {cond['condition_type']}: {cond['status']} ({cond['severity']}) - {cond['message']}")

            print(f"\nIdentity Conditions ({len(result['identity_conditions'])}):")
            for cond in result['identity_conditions']:
                status_icon = "✅" if cond['status'] == "PASS" else "❌" if cond['status'] == "FAIL" else "⚠️"
                print(f"  {status_icon} {cond['condition_type']}: {cond['status']} ({cond['severity']}) - {cond['message']}")

            print(f"\n🎯 Officer Recommendations ({len(result['officer_recommendations'])}):")
            for rec in result['officer_recommendations']:
                print(f"  • {rec}")

            print(f"\n📋 Required Actions ({len(result['required_actions'])}):")
            for action in result['required_actions']:
                print(f"  • {action}")

            # Test dashboard integration
            print("\nStep 3: Dashboard Integration Check")
            print("-" * 30)

            if result['risk_level'] in ["MEDIUM", "HIGH"]:
                print(f"✅ Risk case should be sent to dashboard (Risk Level: {result['risk_level']})")

                # Check dashboard API
                dashboard_response = requests.get(
                    "http://localhost:8001/dashboard/risk-cases?limit=5",
                    headers=headers
                )

                if dashboard_response.status_code == 200:
                    risk_cases = dashboard_response.json()
                    print(f"✅ Dashboard API working - found {len(risk_cases)} risk cases")
                    if risk_cases:
                        latest_case = risk_cases[0]
                        print(f"   Latest case: {latest_case.get('case_id', 'Unknown')} - {latest_case.get('risk_level', 'Unknown')}")
                else:
                    print(f"❌ Dashboard API failed: {dashboard_response.status_code}")
            else:
                print(f"ℹ️ Low risk case - not sent to dashboard (Risk Level: {result['risk_level']})")

        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Main test function"""
    test_comprehensive_verification_api()


if __name__ == "__main__":
    main()