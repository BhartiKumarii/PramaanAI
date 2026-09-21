#!/usr/bin/env python3
"""
Comprehensive test suite for verifying all document types from the dataset.
Tests face verification, document classification, and OCR extraction.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.services.document_classifier.classifier import DocumentClassifier
from app.services.face.embedding import extract_embedding, cosine_similarity
from app.services.visa.nepal_visa_handler import NepalVisaHandler
from app.services.language.multilingual_handler import MultilingualDocumentHandler
from tests.synthetic_documents import generate_face_like_image


class DatasetVerifier:
    """Verify all document types in the dataset."""

    def __init__(self):
        self.classifier = DocumentClassifier()
        self.nepal_visa_handler = NepalVisaHandler()
        self.multilingual_handler = MultilingualDocumentHandler()
        self.results = {
            'classification': [],
            'face_verification': [],
            'nepal_visa': [],
            'multilingual': [],
            'errors': []
        }

    def verify_dataset(self, dataset_path: str):
        """Verify all documents in the dataset."""
        dataset_path = Path(dataset_path)

        print("\n" + "="*80)
        print("PramaanAI COMPREHENSIVE DATASET VERIFICATION")
        print("="*80)

        # Process each country
        for country_dir in sorted(dataset_path.iterdir()):
            if not country_dir.is_dir():
                continue

            country = country_dir.name
            print(f"\n\n{'='*80}")
            print(f"Processing {country.upper()} Documents")
            print(f"{'='*80}")

            self._process_country(country_dir, country)

        # Print summary
        self._print_summary()

    def _process_country(self, country_path: Path, country: str):
        """Process all documents in a country directory."""
        documents = sorted([
            f for f in country_path.glob('*')
            if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']
            and f.stat().st_size > 0  # Skip empty files
        ])

        print(f"\nFound {len(documents)} valid documents\n")

        for idx, doc_path in enumerate(documents, 1):
            print(f"\n[{idx}/{len(documents)}] {doc_path.name}")
            print("-" * 60)

            try:
                doc_bytes = doc_path.read_bytes()

                # 1. Document Classification
                print("  1️⃣  Classification:", end=" ")
                self._test_classification(doc_bytes, country, doc_path.name)

                # 2. Face Detection
                print("  2️⃣  Face Detection:", end=" ")
                self._test_face_detection(doc_bytes, doc_path.name)

                # 3. Nepal Visa Detection
                if country.lower() == 'nepal':
                    print("  3️⃣  Nepal Visa:", end=" ")
                    self._test_nepal_visa(doc_bytes, country, doc_path.name)

                # 4. Multilingual Detection
                print("  4️⃣  Language/Script:", end=" ")
                self._test_multilingual(doc_bytes, country, doc_path.name)

            except Exception as e:
                error_msg = f"{doc_path.name}: {str(e)}"
                print(f"  ❌ ERROR: {error_msg}")
                self.results['errors'].append(error_msg)

    def _test_classification(self, doc_bytes: bytes, country: str, filename: str):
        """Test document classification."""
        try:
            result = self.classifier.classify(doc_bytes)
            status = "✅" if result.is_identity_document else "❌"
            print(f"{status} {result.document_type.upper()} ({result.country})")

            self.results['classification'].append({
                'file': filename,
                'country': country,
                'is_identity': result.is_identity_document,
                'doc_type': result.document_type,
                'confidence': result.confidence,
                'reason': result.reason[:50]
            })
        except Exception as e:
            print(f"❌ {str(e)[:50]}")
            raise

    def _test_face_detection(self, doc_bytes: bytes, filename: str):
        """Test face detection in document."""
        try:
            # Try to extract embedding - this requires face detection
            embedding = extract_embedding(doc_bytes)
            if embedding and len(embedding) > 0:
                print(f"✅ Face embedding extracted ({len(embedding)} dims)")
                self.results['face_verification'].append({
                    'file': filename,
                    'embedding_extracted': True,
                    'embedding_size': len(embedding)
                })
            else:
                print("⚠️  Face detection inconclusive")
                self.results['face_verification'].append({
                    'file': filename,
                    'embedding_extracted': False
                })
        except Exception as e:
            print(f"⚠️  No face/error: {str(e)[:30]}")

    def _test_nepal_visa(self, doc_bytes: bytes, country: str, filename: str):
        """Test Nepal visa specific verification."""
        try:
            result = self.nepal_visa_handler.verify_nepal_visa(doc_bytes)

            format_status = "✅" if result.format_detected.confidence > 0.5 else "⚠️"
            date_status = "✅" if result.date_validation.status in ["VALID", "EXPIRED"] else "⚠️"

            print(f"{format_status} {result.format_detected.format_type} | {date_status} Dates: {result.date_validation.status}")

            self.results['nepal_visa'].append({
                'file': filename,
                'format': result.format_detected.format_type,
                'format_confidence': result.format_detected.confidence,
                'date_status': result.date_validation.status,
                'overall_status': result.overall_status
            })
        except Exception as e:
            print(f"⚠️  {str(e)[:40]}")

    def _test_multilingual(self, doc_bytes: bytes, country: str, filename: str):
        """Test multilingual document processing."""
        try:
            result = self.multilingual_handler.process_multilingual_document(
                doc_bytes,
                document_type='unknown',
                country=country
            )

            script_status = "✅" if result.script_detection.confidence > 0.5 else "⚠️"
            lang_status = "✅" if result.language_detection.confidence > 0.5 else "⚠️"

            print(f"{script_status} {result.script_detection.primary_script.value} | {lang_status} {result.officer_display['primary_language']}")

            self.results['multilingual'].append({
                'file': filename,
                'script': result.script_detection.primary_script.value,
                'script_confidence': result.script_detection.confidence,
                'language': result.language_detection.primary_language.value,
                'language_confidence': result.language_detection.confidence
            })
        except Exception as e:
            print(f"⚠️  {str(e)[:40]}")

    def _print_summary(self):
        """Print verification summary."""
        print("\n\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)

        print(f"\n📊 STATISTICS:")
        print(f"  Classification Results: {len(self.results['classification'])}")
        print(f"  Face Detections: {len(self.results['face_verification'])}")
        print(f"  Nepal Visa Tests: {len(self.results['nepal_visa'])}")
        print(f"  Multilingual Tests: {len(self.results['multilingual'])}")
        print(f"  Errors Encountered: {len(self.results['errors'])}")

        # Classification breakdown
        if self.results['classification']:
            id_docs = sum(1 for r in self.results['classification'] if r['is_identity'])
            print(f"\n📄 DOCUMENTS CLASSIFIED:")
            print(f"  Identity Documents: {id_docs}/{len(self.results['classification'])}")

            doc_types = {}
            for r in self.results['classification']:
                doc_types[r['doc_type']] = doc_types.get(r['doc_type'], 0) + 1
            for doc_type, count in sorted(doc_types.items(), key=lambda x: -x[1]):
                print(f"    - {doc_type.upper()}: {count}")

        # Face detection
        if self.results['face_verification']:
            faces_found = sum(1 for r in self.results['face_verification'] if r['embedding_extracted'])
            print(f"\n👤 FACE DETECTION:")
            print(f"  Faces Extracted: {faces_found}/{len(self.results['face_verification'])}")

        # Nepal visa results
        if self.results['nepal_visa']:
            print(f"\n🇳🇵 NEPAL VISA VERIFICATION:")
            formats = {}
            for r in self.results['nepal_visa']:
                formats[r['format']] = formats.get(r['format'], 0) + 1
            for fmt, count in sorted(formats.items(), key=lambda x: -x[1]):
                print(f"    - {fmt}: {count}")

        # Multilingual results
        if self.results['multilingual']:
            print(f"\n🌍 MULTILINGUAL DETECTION:")
            scripts = {}
            langs = {}
            for r in self.results['multilingual']:
                scripts[r['script']] = scripts.get(r['script'], 0) + 1
                langs[r['language']] = langs.get(r['language'], 0) + 1

            print(f"  Detected Scripts:")
            for script, count in sorted(scripts.items(), key=lambda x: -x[1]):
                print(f"    - {script}: {count}")

            print(f"  Detected Languages:")
            for lang, count in sorted(langs.items(), key=lambda x: -x[1]):
                print(f"    - {lang}: {count}")

        # Errors
        if self.results['errors']:
            print(f"\n⚠️  ERRORS ({len(self.results['errors'])}):")
            for error in self.results['errors'][:5]:
                print(f"    - {error}")
            if len(self.results['errors']) > 5:
                print(f"    ... and {len(self.results['errors']) - 5} more")

        print("\n" + "="*80)
        print(f"✅ VERIFICATION COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")


def test_face_similarity():
    """Test face similarity comparison with synthetic faces."""
    print("\n" + "="*80)
    print("FACE SIMILARITY VERIFICATION")
    print("="*80 + "\n")

    # Generate synthetic faces
    face1_seed1 = generate_face_like_image(1)
    face1_seed1_dup = generate_face_like_image(1)
    face2_seed2 = generate_face_like_image(2)

    # Extract embeddings
    embed1 = extract_embedding(face1_seed1)
    embed1_dup = extract_embedding(face1_seed1_dup)
    embed2 = extract_embedding(face2_seed2)

    # Compare
    sim_same = cosine_similarity(embed1, embed1_dup)
    sim_different = cosine_similarity(embed1, embed2)

    print(f"Same Face (seed 1 vs seed 1):")
    print(f"  Similarity: {sim_same:.4f}")
    print(f"  Result: {'✅ MATCH' if sim_same >= 0.75 else '❌ NO MATCH'}")

    print(f"\nDifferent Faces (seed 1 vs seed 2):")
    print(f"  Similarity: {sim_different:.4f}")
    print(f"  Result: {'❌ NO MATCH' if sim_different < 0.75 else '✅ MATCH (ERROR!)'}")

    print(f"\nThreshold: 0.75")
    print(f"Same-face separation: {sim_same - sim_different:.4f}")
    print("✅ Face verification calibration PASSED" if (sim_same >= 0.75 and sim_different < 0.75) else "❌ FAILED")


if __name__ == "__main__":
    dataset_path = "/home/bharti/ID_DOCUMENT_DATASET"

    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]

    # Test face verification calibration
    test_face_similarity()

    # Verify dataset
    verifier = DatasetVerifier()
    verifier.verify_dataset(dataset_path)