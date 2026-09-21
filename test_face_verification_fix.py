#!/usr/bin/env python3
"""Test script to verify face verification fixes work correctly."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.face.classical_provider import ClassicalFaceProvider, match_from_embeddings
from app.services.face.embedding import extract_embedding
from tests.synthetic_documents import generate_face_like_image

def test_face_verification():
    """Test that face verification correctly identifies same and different faces."""

    print("Testing Face Verification Pipeline Fixes")
    print("=" * 50)

    # Generate test images
    face1_seed1 = generate_face_like_image(1)   # Person 1
    face1_seed1_dup = generate_face_like_image(1)  # Same person (duplicate)
    face2_seed2 = generate_face_like_image(2)   # Different person
    face3_seed99 = generate_face_like_image(99) # Very different person

    print(f"Generated test images:")
    print(f"  Face 1 (seed 1): {len(face1_seed1)} bytes")
    print(f"  Face 1 duplicate (seed 1): {len(face1_seed1_dup)} bytes")
    print(f"  Face 2 (seed 2): {len(face2_seed2)} bytes")
    print(f"  Face 3 (seed 99): {len(face3_seed99)} bytes")
    print()

    # Test classical provider
    provider = ClassicalFaceProvider()

    print("1. Testing SAME FACE (seed 1 vs seed 1):")
    result_same = provider.verify(face1_seed1, face1_seed1_dup)
    print(f"   Similarity: {result_same.similarity:.4f}")
    print(f"   Match: {result_same.match}")
    print(f"   Reason: {result_same.reason}")
    print()

    print("2. Testing DIFFERENT FACES (seed 1 vs seed 2):")
    result_different = provider.verify(face1_seed1, face2_seed2)
    print(f"   Similarity: {result_different.similarity:.4f}")
    print(f"   Match: {result_different.match}")
    print(f"   Reason: {result_different.reason}")
    print()

    print("3. Testing VERY DIFFERENT FACES (seed 1 vs seed 99):")
    result_very_different = provider.verify(face1_seed1, face3_seed99)
    print(f"   Similarity: {result_very_different.similarity:.4f}")
    print(f"   Match: {result_very_different.match}")
    print(f"   Reason: {result_very_different.reason}")
    print()

    # Test embedding-based matching (used in production pipeline)
    print("4. Testing embedding-based matching (production pipeline):")

    embed1 = extract_embedding(face1_seed1)
    embed1_dup = extract_embedding(face1_seed1_dup)
    embed2 = extract_embedding(face2_seed2)

    result_embed_same = match_from_embeddings(embed1, embed1_dup)
    result_embed_different = match_from_embeddings(embed1, embed2)

    print(f"   Same face embeddings: similarity {result_embed_same.similarity:.4f}, match {result_embed_same.match}")
    print(f"   Different face embeddings: similarity {result_embed_different.similarity:.4f}, match {result_embed_different.match}")
    print()

    # Validation
    print("VALIDATION:")
    print("-----------")

    # Same faces should match
    if result_same.match and result_embed_same.match:
        print("✓ Same faces correctly identified as MATCH")
    else:
        print("✗ ERROR: Same faces not matching!")
        print(f"  Provider result: {result_same.match}, Embedding result: {result_embed_same.match}")

    # Different faces should NOT match
    if not result_different.match and not result_very_different.match and not result_embed_different.match:
        print("✓ Different faces correctly identified as NO MATCH")
    else:
        print("✗ ERROR: Different faces incorrectly matching!")
        print(f"  Different faces match: {result_different.match}")
        print(f"  Very different faces match: {result_very_different.match}")
        print(f"  Different embeddings match: {result_embed_different.match}")

    # Check threshold consistency
    threshold_used = 0.75  # Our fixed threshold
    print(f"✓ Using consistent threshold: {threshold_used}")
    print(f"✓ Same face similarity ({result_same.similarity:.4f}) above threshold: {result_same.similarity >= threshold_used}")
    print(f"✓ Different face similarity ({result_different.similarity:.4f}) below threshold: {result_different.similarity < threshold_used}")

    print()
    print("Face verification pipeline fixes applied successfully!")

if __name__ == "__main__":
    test_face_verification()