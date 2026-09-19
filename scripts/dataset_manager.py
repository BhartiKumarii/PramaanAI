"""Comprehensive Dataset Management System

This script manages the ID document dataset and creates comprehensive test data
for all verification conditions specified in the requirements:

1. Document Verification (validity, format, duplicates, blacklist)
2. Tampering Detection (all types of modifications)
3. Face Verification (matching, spoofing, multiple identities)
4. Liveness Detection (various attack types)
5. Risk Assessment (Low/Medium/High conditions)
"""
import os
import json
import uuid
import random
import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sqlite3
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import cv2
import numpy as np

# Database setup
DB_PATH = "pramaan.db"

# Dataset paths
DATASET_ROOT = "/home/bharti/ID_DOCUMENT_DATASET"
PROCESSED_DATA_DIR = "data/processed"
SYNTHETIC_DATA_DIR = "data/synthetic"

# Document types mapping
DOCUMENT_TYPES = {
    "National_ID": "aadhaar",
    "Passport": "passport",
    "Visa": "visa",
    "Driving_License": "driving_license",
    "Permit": "permit"
}

# Countries
COUNTRIES = ["India", "Nepal", "Bhutan"]

class DatasetManager:
    """Manages comprehensive dataset integration and test data generation"""

    def __init__(self):
        self.db_path = DB_PATH
        self.dataset_root = Path(DATASET_ROOT)
        self.processed_dir = Path(PROCESSED_DATA_DIR)
        self.synthetic_dir = Path(SYNTHETIC_DATA_DIR)

        # Create directories
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.synthetic_dir.mkdir(parents=True, exist_ok=True)

        # Sample names for synthetic data
        self.indian_names = [
            "Rajesh Kumar Singh", "Priya Sharma", "Amit Patel", "Sneha Gupta",
            "Vikram Singh", "Pooja Agarwal", "Rohit Verma", "Kavya Reddy",
            "Arjun Malhotra", "Divya Joshi", "Sanjay Kumar", "Meera Singh"
        ]

        self.nepali_names = [
            "Ramesh Bahadur Thapa", "Sita Maya Gurung", "Krishna Prasad Sharma",
            "Gita Devi Poudel", "Bharat Singh Rai", "Kamala Kumari Shrestha",
            "Dipak Bahadur KC", "Sabita Ghimire", "Tek Raj Pandey", "Sunita Magar"
        ]

        self.bhutanese_names = [
            "Tenzin Wangchuk", "Pema Lhamo", "Karma Dorji", "Deki Choden",
            "Phurba Tshering", "Sangay Dema", "Jigme Singye", "Tashi Peldon",
            "Ugyen Dorji", "Chimi Lhamo", "Norbu Wangdi", "Dechen Pemo"
        ]

    def setup_database(self):
        """Initialize database with all required tables"""
        print("Setting up database...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables for comprehensive testing

        # Document registry with verification conditions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_registry (
                id TEXT PRIMARY KEY,
                document_number TEXT UNIQUE NOT NULL,
                document_type TEXT NOT NULL,
                nationality TEXT NOT NULL,
                full_name TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                gender TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                expiry_date TEXT,
                issuing_authority TEXT,
                status TEXT DEFAULT 'VALID',  -- VALID, EXPIRED, REVOKED, BLACKLISTED
                blacklist_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Face embeddings for identity verification
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id TEXT PRIMARY KEY,
                document_number TEXT,
                full_name TEXT,
                embedding_json TEXT NOT NULL,
                image_path TEXT,
                nationality TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_number) REFERENCES document_registry(document_number)
            )
        """)

        # Test cases for all verification conditions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_cases (
                id TEXT PRIMARY KEY,
                test_type TEXT NOT NULL,  -- DOCUMENT_VALID, DOCUMENT_EXPIRED, FACE_MATCH, etc.
                document_path TEXT,
                selfie_path TEXT,
                expected_result TEXT NOT NULL,
                risk_level TEXT NOT NULL,  -- LOW, MEDIUM, HIGH
                description TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Known tampering examples
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tampering_examples (
                id TEXT PRIMARY KEY,
                original_path TEXT NOT NULL,
                tampered_path TEXT NOT NULL,
                tampering_type TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        print("Database setup complete!")

    def process_dataset(self):
        """Process the ID document dataset"""
        print("Processing ID document dataset...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        processed_count = 0

        for country in COUNTRIES:
            country_path = self.dataset_root / country
            if not country_path.exists():
                print(f"Country path not found: {country_path}")
                continue

            print(f"\nProcessing {country} documents...")

            for doc_type_folder in country_path.iterdir():
                if not doc_type_folder.is_dir():
                    continue

                doc_type = DOCUMENT_TYPES.get(doc_type_folder.name, doc_type_folder.name.lower())
                print(f"  Processing {doc_type}...")

                # Find all images in this document type folder
                for img_file in doc_type_folder.glob("**/*"):
                    if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                        try:
                            # Generate synthetic document data
                            doc_data = self._generate_document_metadata(country, doc_type)

                            # Insert into registry
                            cursor.execute("""
                                INSERT OR REPLACE INTO document_registry
                                (id, document_number, document_type, nationality, full_name,
                                 date_of_birth, gender, issue_date, expiry_date, issuing_authority, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                str(uuid.uuid4()), doc_data['document_number'], doc_type, country,
                                doc_data['full_name'], doc_data['date_of_birth'], doc_data['gender'],
                                doc_data['issue_date'], doc_data.get('expiry_date'),
                                doc_data['issuing_authority'], doc_data['status']
                            ))

                            # Copy image to processed directory
                            processed_filename = f"{doc_data['document_number']}_{doc_type}.{img_file.suffix}"
                            processed_path = self.processed_dir / processed_filename
                            shutil.copy2(img_file, processed_path)

                            processed_count += 1

                        except Exception as e:
                            print(f"    Error processing {img_file}: {e}")

        conn.commit()
        conn.close()
        print(f"\nProcessed {processed_count} documents!")

    def _generate_document_metadata(self, country: str, doc_type: str) -> Dict:
        """Generate realistic document metadata"""

        # Select appropriate name based on country
        if country == "India":
            name = random.choice(self.indian_names)
        elif country == "Nepal":
            name = random.choice(self.nepali_names)
        else:  # Bhutan
            name = random.choice(self.bhutanese_names)

        # Generate document number based on type
        if doc_type == "aadhaar":
            doc_number = f"{random.randint(1000, 9999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"
        elif doc_type == "passport":
            doc_number = f"{country[0]}{random.randint(1000000, 9999999)}"
        else:
            doc_number = f"{doc_type.upper()}{random.randint(100000, 999999)}"

        # Generate dates
        issue_date = datetime.now() - timedelta(days=random.randint(30, 3650))  # 1 month to 10 years ago

        # Determine status (create some expired/blacklisted for testing)
        status = "VALID"
        expiry_date = None

        if doc_type in ["passport", "visa", "driving_license"]:
            expiry_date = issue_date + timedelta(days=random.randint(365, 3650))  # 1-10 years validity
            if expiry_date < datetime.now():
                status = "EXPIRED"

        # Create some blacklisted documents (5% chance)
        if random.random() < 0.05:
            status = "BLACKLISTED"

        return {
            'document_number': doc_number,
            'full_name': name,
            'date_of_birth': (datetime.now() - timedelta(days=random.randint(6570, 25550))).strftime('%Y-%m-%d'),  # 18-70 years
            'gender': random.choice(['M', 'F']),
            'issue_date': issue_date.strftime('%Y-%m-%d'),
            'expiry_date': expiry_date.strftime('%Y-%m-%d') if expiry_date else None,
            'issuing_authority': self._get_issuing_authority(country, doc_type),
            'status': status
        }

    def _get_issuing_authority(self, country: str, doc_type: str) -> str:
        """Get appropriate issuing authority"""
        authorities = {
            "India": {
                "aadhaar": "UIDAI",
                "passport": "Ministry of External Affairs",
                "visa": "Ministry of Home Affairs",
                "driving_license": "Regional Transport Office",
                "permit": "Ministry of Home Affairs"
            },
            "Nepal": {
                "aadhaar": "Department of National ID",
                "passport": "Department of Passport",
                "visa": "Department of Immigration",
                "driving_license": "Department of Transport",
                "permit": "Immigration Office"
            },
            "Bhutan": {
                "aadhaar": "Civil Registration Authority",
                "passport": "Department of Immigration",
                "visa": "Immigration Services",
                "driving_license": "Road Safety Authority",
                "permit": "Immigration Department"
            }
        }

        return authorities.get(country, {}).get(doc_type, f"{country} Government")

    def generate_test_cases(self):
        """Generate comprehensive test cases for all verification conditions"""
        print("\nGenerating comprehensive test cases...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all processed documents
        cursor.execute("SELECT * FROM document_registry")
        documents = cursor.fetchall()

        test_cases = []

        for doc in documents:
            # Unpack the document row properly
            if len(doc) >= 11:
                doc_id, doc_number, doc_type, nationality, name, dob, gender, issue_date, expiry_date, authority, status = doc[:11]
                created_at = doc[11] if len(doc) > 11 else None
            else:
                print(f"Unexpected document format: {doc}")
                continue

            # 1. Valid document test case
            if status == "VALID":
                test_cases.append({
                    'test_type': 'DOCUMENT_VALID',
                    'expected_result': 'VERIFIED',
                    'risk_level': 'LOW',
                    'description': f'Valid {doc_type} from {nationality}',
                    'metadata': {'document_number': doc_number, 'status': status}
                })

            # 2. Expired document test case
            elif status == "EXPIRED":
                test_cases.append({
                    'test_type': 'DOCUMENT_EXPIRED',
                    'expected_result': 'REVIEW_REQUIRED',
                    'risk_level': 'HIGH',
                    'description': f'Expired {doc_type} - should be flagged',
                    'metadata': {'document_number': doc_number, 'expiry_date': expiry_date}
                })

            # 3. Blacklisted document test case
            elif status == "BLACKLISTED":
                test_cases.append({
                    'test_type': 'DOCUMENT_BLACKLISTED',
                    'expected_result': 'REVIEW_REQUIRED',
                    'risk_level': 'HIGH',
                    'description': f'Blacklisted {doc_type} - high risk',
                    'metadata': {'document_number': doc_number, 'blacklist_status': True}
                })

        # Generate tampering test cases
        self._generate_tampering_test_cases(cursor, test_cases)

        # Generate face verification test cases
        self._generate_face_test_cases(cursor, test_cases)

        # Insert all test cases
        for test_case in test_cases:
            cursor.execute("""
                INSERT INTO test_cases
                (id, test_type, expected_result, risk_level, description, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                test_case['test_type'],
                test_case['expected_result'],
                test_case['risk_level'],
                test_case['description'],
                json.dumps(test_case['metadata'])
            ))

        conn.commit()
        conn.close()
        print(f"Generated {len(test_cases)} comprehensive test cases!")

    def _generate_tampering_test_cases(self, cursor, test_cases: List[Dict]):
        """Generate tampering detection test cases"""

        tampering_types = [
            {'type': 'PHOTO_REPLACEMENT', 'risk': 'HIGH', 'description': 'Photo has been digitally replaced'},
            {'type': 'TEXT_MODIFICATION', 'risk': 'HIGH', 'description': 'Name or DOB has been altered'},
            {'type': 'DATE_ALTERATION', 'risk': 'HIGH', 'description': 'Issue or expiry date modified'},
            {'type': 'FAKE_STAMP', 'risk': 'MEDIUM', 'description': 'Visa stamp appears fake or altered'},
            {'type': 'FONT_INCONSISTENCY', 'risk': 'MEDIUM', 'description': 'Different fonts used in document'},
            {'type': 'COPY_PASTE_MARKS', 'risk': 'MEDIUM', 'description': 'Digital copy-paste artifacts detected'},
            {'type': 'MISSING_HOLOGRAM', 'risk': 'HIGH', 'description': 'Security hologram missing or altered'},
            {'type': 'BLURRED_REGIONS', 'risk': 'MEDIUM', 'description': 'Suspicious blurred areas detected'},
            {'type': 'DIGITAL_EDITING', 'risk': 'HIGH', 'description': 'Signs of digital photo editing'},
            {'type': 'QR_CODE_TAMPERING', 'risk': 'MEDIUM', 'description': 'QR code appears modified'}
        ]

        for tampering in tampering_types:
            test_cases.append({
                'test_type': f"TAMPERING_{tampering['type']}",
                'expected_result': 'REVIEW_REQUIRED',
                'risk_level': tampering['risk'],
                'description': tampering['description'],
                'metadata': {'tampering_type': tampering['type']}
            })

    def _generate_face_test_cases(self, cursor, test_cases: List[Dict]):
        """Generate face verification test cases"""

        face_scenarios = [
            {'type': 'FACE_MATCH_VALID', 'risk': 'LOW', 'result': 'VERIFIED', 'desc': 'Face matches document photo'},
            {'type': 'FACE_MISMATCH', 'risk': 'HIGH', 'result': 'REVIEW_REQUIRED', 'desc': 'Face does not match document'},
            {'type': 'NO_FACE_IN_DOCUMENT', 'risk': 'HIGH', 'result': 'REVIEW_REQUIRED', 'desc': 'No face detected in document'},
            {'type': 'MULTIPLE_FACES', 'risk': 'MEDIUM', 'result': 'REVIEW_REQUIRED', 'desc': 'Multiple faces detected'},
            {'type': 'FACE_PARTIALLY_HIDDEN', 'risk': 'MEDIUM', 'result': 'REVIEW_REQUIRED', 'desc': 'Face partially obscured'},
            {'type': 'POOR_LIGHTING', 'risk': 'LOW', 'result': 'REVIEW_REQUIRED', 'desc': 'Poor lighting affects verification'},
            {'type': 'SPOOF_PHOTO_ON_SCREEN', 'risk': 'HIGH', 'result': 'REVIEW_REQUIRED', 'desc': 'Photo-on-screen spoof attempt'},
            {'type': 'MULTIPLE_IDENTITY_SAME_FACE', 'risk': 'HIGH', 'result': 'REVIEW_REQUIRED', 'desc': 'Same face with different documents'},
            {'type': 'DUPLICATE_DOCUMENT_DIFFERENT_FACE', 'risk': 'HIGH', 'result': 'REVIEW_REQUIRED', 'desc': 'Same document with different faces'}
        ]

        for scenario in face_scenarios:
            test_cases.append({
                'test_type': scenario['type'],
                'expected_result': scenario['result'],
                'risk_level': scenario['risk'],
                'description': scenario['desc'],
                'metadata': {'face_scenario': scenario['type']}
            })

    def create_synthetic_tampering_examples(self):
        """Create synthetic tampering examples for testing"""
        print("\nCreating synthetic tampering examples...")

        # Get some sample documents
        sample_images = list(self.processed_dir.glob("*.jpg")) + list(self.processed_dir.glob("*.png"))

        if not sample_images:
            print("No processed images found. Run process_dataset() first.")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create different types of tampering
        tampering_count = 0

        for i, img_path in enumerate(sample_images[:20]):  # Process first 20 images
            try:
                original_image = Image.open(img_path)

                # 1. Text overlay tampering (simulating altered text)
                tampered_text = self._create_text_tampering(original_image)
                text_path = self.synthetic_dir / f"tampered_text_{i}.jpg"
                tampered_text.save(text_path)

                cursor.execute("""
                    INSERT INTO tampering_examples
                    (id, original_path, tampered_path, tampering_type, description, severity)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    str(img_path),
                    str(text_path),
                    "TEXT_ALTERATION",
                    "Text has been digitally altered",
                    "HIGH"
                ))

                # 2. Brightness/contrast tampering
                tampered_brightness = self._create_brightness_tampering(original_image)
                brightness_path = self.synthetic_dir / f"tampered_brightness_{i}.jpg"
                tampered_brightness.save(brightness_path)

                cursor.execute("""
                    INSERT INTO tampering_examples
                    (id, original_path, tampered_path, tampering_type, description, severity)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    str(img_path),
                    str(brightness_path),
                    "BRIGHTNESS_ALTERATION",
                    "Brightness/contrast has been modified",
                    "MEDIUM"
                ))

                # 3. Blur tampering (simulating document damage)
                tampered_blur = self._create_blur_tampering(original_image)
                blur_path = self.synthetic_dir / f"tampered_blur_{i}.jpg"
                tampered_blur.save(blur_path)

                cursor.execute("""
                    INSERT INTO tampering_examples
                    (id, original_path, tampered_path, tampering_type, description, severity)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    str(img_path),
                    str(blur_path),
                    "SELECTIVE_BLUR",
                    "Selective blur applied to hide information",
                    "MEDIUM"
                ))

                tampering_count += 3

            except Exception as e:
                print(f"Error creating tampering examples for {img_path}: {e}")

        conn.commit()
        conn.close()
        print(f"Created {tampering_count} synthetic tampering examples!")

    def _create_text_tampering(self, image: Image.Image) -> Image.Image:
        """Create text tampering example"""
        tampered = image.copy()
        draw = ImageDraw.Draw(tampered)

        # Add some fake text overlay
        width, height = tampered.size

        # Try to add text in a typical document text area
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 20)
        except:
            font = ImageFont.load_default()

        # Add fake stamp or text
        text = "ALTERED"
        text_color = (255, 0, 0)  # Red
        text_position = (width//4, height//2)

        draw.text(text_position, text, fill=text_color, font=font)

        return tampered

    def _create_brightness_tampering(self, image: Image.Image) -> Image.Image:
        """Create brightness tampering example"""
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(1.5)  # Increase brightness

    def _create_blur_tampering(self, image: Image.Image) -> Image.Image:
        """Create selective blur tampering example"""
        tampered = image.copy()

        # Apply blur to a region (simulating hiding information)
        width, height = tampered.size

        # Convert to CV2 for selective blur
        cv_image = cv2.cvtColor(np.array(tampered), cv2.COLOR_RGB2BGR)

        # Define blur region (center area)
        x1, y1 = width//4, height//4
        x2, y2 = 3*width//4, 3*height//4

        # Apply Gaussian blur to the region
        roi = cv_image[y1:y2, x1:x2]
        blurred_roi = cv2.GaussianBlur(roi, (21, 21), 0)
        cv_image[y1:y2, x1:x2] = blurred_roi

        # Convert back to PIL
        tampered = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))

        return tampered

    def generate_statistics(self):
        """Generate comprehensive dataset statistics"""
        print("\n" + "="*60)
        print("PRAMAAN AI DATASET STATISTICS")
        print("="*60)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Document statistics
        cursor.execute("SELECT COUNT(*) FROM document_registry")
        total_docs = cursor.fetchone()[0]

        cursor.execute("SELECT nationality, COUNT(*) FROM document_registry GROUP BY nationality")
        country_stats = cursor.fetchall()

        cursor.execute("SELECT document_type, COUNT(*) FROM document_registry GROUP BY document_type")
        doc_type_stats = cursor.fetchall()

        cursor.execute("SELECT status, COUNT(*) FROM document_registry GROUP BY status")
        status_stats = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM test_cases")
        total_test_cases = cursor.fetchone()[0]

        cursor.execute("SELECT risk_level, COUNT(*) FROM test_cases GROUP BY risk_level")
        risk_stats = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM tampering_examples")
        tampering_examples = cursor.fetchone()[0]

        print(f"Total Documents: {total_docs}")
        print("\nBy Country:")
        for country, count in country_stats:
            print(f"  {country}: {count}")

        print("\nBy Document Type:")
        for doc_type, count in doc_type_stats:
            print(f"  {doc_type}: {count}")

        print("\nBy Status:")
        for status, count in status_stats:
            print(f"  {status}: {count}")

        print(f"\nTest Cases: {total_test_cases}")
        print("By Risk Level:")
        for risk, count in risk_stats:
            print(f"  {risk}: {count}")

        print(f"\nTampering Examples: {tampering_examples}")

        print("\nVerification Conditions Coverage:")
        cursor.execute("SELECT DISTINCT test_type FROM test_cases")
        test_types = [row[0] for row in cursor.fetchall()]

        for test_type in sorted(test_types):
            print(f"  ✓ {test_type}")

        conn.close()

        print("\n" + "="*60)
        print("DATASET READY FOR COMPREHENSIVE TESTING!")
        print("="*60)

def main():
    """Run complete dataset setup"""
    manager = DatasetManager()

    print("🚀 Starting PramaanAI Dataset Management")
    print("="*50)

    # Step 1: Setup database
    manager.setup_database()

    # Step 2: Process the ID document dataset
    manager.process_dataset()

    # Step 3: Generate comprehensive test cases
    manager.generate_test_cases()

    # Step 4: Create synthetic tampering examples
    manager.create_synthetic_tampering_examples()

    # Step 5: Generate statistics
    manager.generate_statistics()

    print("\n🎉 Dataset management complete!")
    print("Your comprehensive PramaanAI dataset is ready for testing all verification conditions!")

if __name__ == "__main__":
    main()