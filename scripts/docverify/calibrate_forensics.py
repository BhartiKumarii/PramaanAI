"""Calibrate region-forensics thresholds on presumed-genuine real captures.

Deterministic split of data/dataset_1 (labels.json, excluding screenshots,
duplicates, concept designs and portraits): images whose sha256 starts with
an even hex digit calibrate; odd ones are held out. For each region family
and method, the "high" threshold is set just above the calibration set's
97th percentile (and "low" just below the 3rd), never tighter than the
built-in defaults. The held-out half then reports how often a presumed-
genuine capture would still be flagged (a false-positive estimate).

Caveat, reported with the numbers: the images are presumed genuine (not
independently verified) and the set is small.

    .venv/bin/python -m scripts.docverify.calibrate_forensics
"""
from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from app.services.docverify import forensics  # noqa: E402
from app.services.docverify.pipeline import verify_images  # noqa: E402

DATASET = ROOT / "data/dataset_1"
OUT = ROOT / "app/services/docverify/forensics_thresholds.json"


def usable() -> list[dict]:
    labels = json.loads((DATASET / "labels.json").read_text())
    return [r for r in labels["records"] if not r["exclude"] and r.get("presumed_genuine_capture")]


def region_measures(path: Path) -> list[dict]:
    out = verify_images([path.read_bytes()])
    return out.documents[0].tampering["region_measures"], out.documents[0].tampering["tampering_detected"]


def main() -> None:
    records = usable()
    calib = [r for r in records if int(r["sha256"][0], 16) % 2 == 0]
    hold = [r for r in records if int(r["sha256"][0], 16) % 2 == 1]
    samples: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in calib:
        measures, _ = region_measures(DATASET / "Dataset" / r["file"])
        for m in measures:
            fam = forensics.region_family(m["region_label"])
            for method, value in m["measures"].items():
                if value is not None:
                    samples[fam][method].append(value)
    families: dict[str, dict[str, dict[str, float]]] = {}
    for fam, methods in samples.items():
        families[fam] = {}
        for method, values in methods.items():
            base = forensics.THRESHOLDS[method]
            arr = np.asarray(values)
            high = max(base["high"], float(np.percentile(arr, 97)) * 1.1)
            low = min(base["low"], float(np.percentile(arr, 3)) * 0.9) if base["low"] else 0.0
            families[fam][method] = {"high": round(high, 3), "low": round(low, 3), "n": len(values)}
    OUT.write_text(json.dumps({
        "generated_by": "scripts/docverify/calibrate_forensics.py",
        "calibration_images": len(calib), "holdout_images": len(hold),
        "method": "per-family P97*1.1 (high) / P3*0.9 (low), never tighter than built-in defaults",
        "families": families}, indent=2) + "\n")
    forensics.calibrated_thresholds.cache_clear()

    flagged = []
    for r in hold:
        _, detected = region_measures(DATASET / "Dataset" / r["file"])
        if detected:
            flagged.append(r["file"])
    fpr = len(flagged) / len(hold) if hold else 0.0
    print(json.dumps({"calibration_images": len(calib), "holdout_images": len(hold),
                      "holdout_flagged": len(flagged), "holdout_false_positive_rate": round(fpr, 3),
                      "flagged_files": flagged}, indent=2))


if __name__ == "__main__":
    main()
