#!/usr/bin/env python3
"""
Full System Integration Test for PramaanAI
Tests entire backend-frontend-mobile pipeline
"""

import os
import sys
import base64
import json
import requests
import subprocess
from pathlib import Path

def test_backend_apis():
    """Test all critical backend APIs"""
    print("🔧 Testing Backend APIs...")

    base_url = "http://localhost:8001"

    # Test 1: Health check
    print("  ✓ Testing health endpoint...")
    response = requests.get(f"{base_url}/documents/health")
    if response.status_code == 200:
        health_data = response.json()
        print(f"    Services: {health_data['services']}")
        print(f"    Languages: {health_data['supported_languages']}")
    else:
        print(f"    ❌ Health check failed: {response.status_code}")
        return False

    # Test 2: Authentication
    print("  ✓ Testing authentication...")
    login_data = {"username": "officer1", "password": "BorderShield123"}
    response = requests.post(f"{base_url}/auth/login", json=login_data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"    Token: {token[:20]}...")
    else:
        print(f"    ❌ Auth failed: {response.status_code}")
        return False

    # Test 3: Dashboard API
    print("  ✓ Testing dashboard API...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{base_url}/dashboard/risk-cases?limit=5", headers=headers)
    if response.status_code == 200:
        cases = response.json()
        print(f"    Risk cases: {len(cases)}")
    else:
        print(f"    ❌ Dashboard API failed: {response.status_code}")
        return False

    # Test 4: Comprehensive verification (simplified)
    print("  ✓ Testing verification API...")

    # Use a small test image
    test_image = b"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    verification_data = {
        "document_image": base64.b64encode(b"fake_image_data").decode('utf-8'),
        "selfie_image": base64.b64encode(b"fake_image_data").decode('utf-8'),
        "ocr_fields": {
            "name": "TEST",
            "date_of_birth": "01/01/1990",
            "document_number": "TEST123",
            "nationality": "INDIAN"
        },
        "document_type": "passport",
        "nationality": "INDIAN",
        "language": "en",
        "device_info": {
            "device_id": "TEST_DEVICE",
            "app_version": "1.0.0",
            "os_version": "Android 12",
            "network_status": "ONLINE",
            "timestamp": 1726800000
        }
    }

    try:
        response = requests.post(
            f"{base_url}/documents/comprehensive-verify",
            json=verification_data,
            headers=headers,
            timeout=30
        )
        if response.status_code == 200:
            print(f"    ✓ Verification API working")
            return True
        else:
            print(f"    ❌ Verification failed: {response.status_code}")
            print(f"    Response: {response.text[:200]}...")
            return False
    except Exception as e:
        print(f"    ❌ Verification exception: {str(e)}")
        return False


def test_frontend():
    """Test frontend accessibility"""
    print("🌐 Testing Frontend Dashboard...")

    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            if "PramaanAI" in response.text:
                print("  ✓ Frontend accessible with correct title")
                return True
            else:
                print("  ❌ Frontend accessible but wrong content")
                return False
        else:
            print(f"  ❌ Frontend not accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Frontend test failed: {str(e)}")
        return False


def test_apk():
    """Test Android APK readiness"""
    print("📱 Testing Android APK...")

    apk_path = Path("android/app/build/outputs/apk/debug/app-debug.apk")

    if apk_path.exists():
        size = apk_path.stat().st_size
        print(f"  ✓ APK exists: {apk_path}")
        print(f"  ✓ APK size: {size / 1024 / 1024:.1f} MB")

        if size > 50 * 1024 * 1024:  # At least 50MB
            print("  ✓ APK size looks good")
            return True
        else:
            print("  ❌ APK size too small - might be incomplete")
            return False
    else:
        print("  ❌ APK not found")
        return False


def check_system_ports():
    """Check all system ports"""
    print("🔌 Checking System Ports...")

    # Check if ports are in use
    try:
        result = subprocess.run(['ss', '-tulpn'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout

            # Check backend (8001)
            if ":8001" in lines:
                print("  ✓ Backend API running on port 8001")
            else:
                print("  ❌ Backend API not running on port 8001")
                return False

            # Check frontend (3000)
            if ":3000" in lines:
                print("  ✓ Frontend running on port 3000")
            else:
                print("  ❌ Frontend not running on port 3000")
                return False

            return True
        else:
            print("  ❌ Could not check ports")
            return False
    except Exception as e:
        print(f"  ❌ Port check failed: {str(e)}")
        return False


def main():
    """Run full system test"""
    print("🚀 PramaanAI Full System Integration Test")
    print("=" * 50)

    results = {}

    # Test each component
    results["ports"] = check_system_ports()
    results["backend"] = test_backend_apis()
    results["frontend"] = test_frontend()
    results["apk"] = test_apk()

    # Summary
    print("\n📊 Test Summary:")
    print("-" * 30)
    total_tests = len(results)
    passed_tests = sum(results.values())

    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component.capitalize()}: {'PASS' if status else 'FAIL'}")

    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n🎉 SYSTEM READY FOR DEPLOYMENT!")
        print("\n📱 To install APK on your phone:")
        print("1. Enable Developer Options and USB Debugging")
        print("2. Connect phone via USB")
        print("3. Run: adb install android/app/build/outputs/apk/debug/app-debug.apk")
        print("4. Or copy APK to phone and install manually")

        print("\n🌐 System URLs:")
        print("- Backend API: http://localhost:8001")
        print("- Web Dashboard: http://localhost:3000")
        print("- API Docs: http://localhost:8001/docs")

    else:
        print("\n⚠️  SYSTEM HAS ISSUES - Check failed components above")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)