"""Build reference feature profiles from the ID_DOCUMENT_DATASET.

Run once:  python -m app.services.document_classifier.reference_builder
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from app.services.document_classifier.feature_extractor import extract_features

DATASET_ROOT = Path("/home/bharti/ID_DOCUMENT_DATASET")
OUTPUT_PATH = Path(__file__).parent / "reference_profiles.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

SCALAR_KEYS = [
    "aspect_ratio",
    "text_density",
    "face_present",
    "face_count",
    "face_area_ratio",
    "h_line_count",
    "blue_ratio",
    "green_ratio",
    "red_ratio",
    "white_ratio",
    "edge_uniformity",
]

HISTOGRAM_KEYS = ["hist_h", "hist_s", "hist_v"]


def collect_image_paths(root: Path) -> dict[str, list[Path]]:
    """Walk the dataset tree and group images by country_doctype key."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for country_dir in sorted(root.iterdir()):
        if not country_dir.is_dir():
            continue
        country = country_dir.name
        for doc_dir in sorted(country_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            doc_type = doc_dir.name
            key = f"{country}_{doc_type}"
            for img_path in doc_dir.rglob("*"):
                if img_path.suffix.lower() in IMAGE_EXTENSIONS and img_path.is_file():
                    groups[key].append(img_path)
    return groups


def build_profiles():
    print(f"[reference_builder] Dataset root: {DATASET_ROOT}")
    groups = collect_image_paths(DATASET_ROOT)
    print(f"[reference_builder] Found {len(groups)} categories:")
    for key, paths in sorted(groups.items()):
        print(f"  {key}: {len(paths)} images")

    profiles: dict[str, dict] = {}

    for key, paths in sorted(groups.items()):
        print(f"\n[reference_builder] Processing {key} ({len(paths)} images)...")
        all_scalars: dict[str, list[float]] = defaultdict(list)
        all_histograms: dict[str, list[list[float]]] = defaultdict(list)
        processed = 0
        skipped = 0

        # Cap processing to avoid spending too long on the 1000-image National_ID set
        sample_paths = paths if len(paths) <= 200 else np.random.default_rng(42).choice(paths, 200, replace=False).tolist()

        for path in sample_paths:
            img = cv2.imread(str(path))
            if img is None:
                skipped += 1
                continue
            try:
                features = extract_features(img)
            except Exception as e:
                print(f"  WARN: failed on {path.name}: {e}")
                skipped += 1
                continue

            for sk in SCALAR_KEYS:
                all_scalars[sk].append(features[sk])
            for hk in HISTOGRAM_KEYS:
                all_histograms[hk].append(features[hk])
            processed += 1

        if processed == 0:
            print(f"  SKIP: no images processed for {key}")
            continue

        print(f"  processed={processed}, skipped={skipped}")

        # Compute mean/std for scalar features
        feature_stats: dict[str, dict] = {}
        for sk in SCALAR_KEYS:
            vals = np.array(all_scalars[sk])
            feature_stats[sk] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }

        # Compute mean/std for histogram bins
        for hk in HISTOGRAM_KEYS:
            arr = np.array(all_histograms[hk])  # shape (N, 16)
            mean_hist = np.mean(arr, axis=0).tolist()
            std_hist = np.std(arr, axis=0).tolist()
            feature_stats[hk] = {
                "mean": mean_hist,
                "std": std_hist,
            }

        profiles[key] = {
            "count": processed,
            "total_in_dataset": len(paths),
            "features": feature_stats,
        }

    # Extract unique document types
    valid_categories = sorted({k.split("_", 1)[1] for k in profiles.keys()})

    output = {
        "profiles": profiles,
        "valid_categories": valid_categories,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(DATASET_ROOT),
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n[reference_builder] Saved profiles to {OUTPUT_PATH}")
    print(f"[reference_builder] {len(profiles)} profiles, {len(valid_categories)} doc types")
    return output


if __name__ == "__main__":
    build_profiles()
