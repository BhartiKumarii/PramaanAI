"""Copy-move forgery detection using DCT-based block matching.

Detects duplicated regions within a document image — a common forgery
technique where part of the document is copied and pasted over another
area (e.g., duplicating a stamp, covering text, replicating a signature).

Algorithm:
1. Convert to grayscale, divide into overlapping blocks
2. Compute DCT of each block and quantize coefficients
3. Sort blocks lexicographically by quantized DCT
4. Adjacent entries in sorted order with identical/near-identical DCT
   that are spatially distant in the image = copy-move candidates
5. Filter by minimum spatial distance to avoid self-matches

Pure numpy + OpenCV — no ML models.
"""
import io
from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image


@dataclass
class CopyMoveFinding:
    finding_type: str
    severity: str
    confidence: float
    description: str
    location: Dict  # source region
    evidence: Dict


def detect_copy_move(
    image_bytes: bytes,
    block_size: int = 16,
    stride: int = 8,
    min_distance: int = 40,
    match_threshold: float = 4.0,
    min_matches: int = 5,
) -> List[CopyMoveFinding]:
    """Detect copy-move forgery in a document image.

    Returns findings for pairs of regions that appear to be duplicates.
    """
    findings: List[CopyMoveFinding] = []

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)

        # Work on a downscaled version for performance
        max_dim = 800
        h, w = arr.shape[:2]
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            arr = cv2.resize(arr, (new_w, new_h), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
        h, w = gray.shape

        if h < block_size * 2 or w < block_size * 2:
            return findings

        # Extract overlapping blocks and their DCT features
        blocks_info = []  # (quantized_dct_flat, row, col)

        for row in range(0, h - block_size + 1, stride):
            for col in range(0, w - block_size + 1, stride):
                block = gray[row:row + block_size, col:col + block_size]
                dct_block = cv2.dct(block)

                # Keep top-left 8x8 DCT coefficients (most energy)
                truncated = dct_block[:8, :8]

                # Quantize to reduce noise sensitivity
                quantized = np.round(truncated / match_threshold).astype(np.int16)
                blocks_info.append((quantized.flatten(), row, col))

        if len(blocks_info) < 10:
            return findings

        # Sort by quantized DCT for efficient matching
        features = np.array([b[0] for b in blocks_info])
        positions = np.array([(b[1], b[2]) for b in blocks_info])

        # Lexicographic sort
        sort_indices = np.lexsort(features.T[::-1])
        sorted_features = features[sort_indices]
        sorted_positions = positions[sort_indices]

        # Find adjacent matches in sorted order
        match_pairs = []
        for i in range(len(sorted_features) - 1):
            if np.array_equal(sorted_features[i], sorted_features[i + 1]):
                r1, c1 = sorted_positions[i]
                r2, c2 = sorted_positions[i + 1]
                dist = np.sqrt((r1 - r2) ** 2 + (c1 - c2) ** 2)

                if dist > min_distance:
                    match_pairs.append((r1, c1, r2, c2, dist))

        if len(match_pairs) < min_matches:
            return findings

        # Cluster matches by displacement vector
        clusters = _cluster_by_displacement(match_pairs, block_size)

        for cluster in clusters:
            if len(cluster) < min_matches:
                continue

            # Compute bounding box of source and target regions
            src_rows = [p[0] for p in cluster]
            src_cols = [p[1] for p in cluster]
            dst_rows = [p[2] for p in cluster]
            dst_cols = [p[3] for p in cluster]

            # Scale back to original coordinates
            inv_scale = 1.0 / scale if scale != 1.0 else 1.0

            src_bbox = {
                "x0": int(min(src_cols) * inv_scale),
                "y0": int(min(src_rows) * inv_scale),
                "x1": int((max(src_cols) + block_size) * inv_scale),
                "y1": int((max(src_rows) + block_size) * inv_scale),
            }
            dst_bbox = {
                "x0": int(min(dst_cols) * inv_scale),
                "y0": int(min(dst_rows) * inv_scale),
                "x1": int((max(dst_cols) + block_size) * inv_scale),
                "y1": int((max(dst_rows) + block_size) * inv_scale),
            }

            match_count = len(cluster)
            confidence = min(1.0, match_count / 30.0)
            severity = "HIGH" if match_count > 20 else "MEDIUM" if match_count > 10 else "LOW"

            findings.append(CopyMoveFinding(
                finding_type="copy_move_detected",
                severity=severity,
                confidence=confidence,
                description=f"Duplicated region detected — {match_count} matching blocks between two areas of the document, suggesting copy-paste manipulation",
                location=src_bbox,
                evidence={
                    "source_region": src_bbox,
                    "destination_region": dst_bbox,
                    "matching_blocks": match_count,
                    "average_distance": round(float(np.mean([p[4] for p in cluster])) * (1.0 / scale if scale != 1.0 else 1.0), 1),
                }
            ))

    except Exception:
        pass

    return findings


def _cluster_by_displacement(
    matches: List[Tuple[int, int, int, int, float]],
    block_size: int,
) -> List[List[Tuple[int, int, int, int, float]]]:
    """Cluster match pairs by similar displacement vectors.

    Real copy-move forgeries produce many matches with the same
    displacement; random coincidences have scattered displacements.
    """
    if not matches:
        return []

    # Compute displacement vectors
    displacements = [(m[2] - m[0], m[3] - m[1]) for m in matches]

    # Simple grid-based clustering
    tolerance = block_size * 2
    clusters: List[List[Tuple[int, int, int, int, float]]] = []

    used = set()
    for i, (dy, dx) in enumerate(displacements):
        if i in used:
            continue

        cluster = [matches[i]]
        used.add(i)

        for j in range(i + 1, len(displacements)):
            if j in used:
                continue
            dy2, dx2 = displacements[j]
            if abs(dy - dy2) <= tolerance and abs(dx - dx2) <= tolerance:
                cluster.append(matches[j])
                used.add(j)

        clusters.append(cluster)

    return clusters
