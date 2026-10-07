"""Generate label maps showing how a single wall pixel changes room structure."""

import argparse
import json
from pathlib import Path

import numpy as np

from planregions import RegionConfig, RegionPipeline, compare_regions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    walls = np.zeros((20, 30), np.uint8)
    walls[2, 2:28] = walls[17, 2:28] = 255
    walls[2:18, 2] = walls[2:18, 27] = 255
    walls[2:18, 15] = 255
    pipeline = RegionPipeline(RegionConfig(min_area=1))
    baseline = pipeline.run(walls).labels
    np.savez_compressed(args.output / "closed.npz", labels=baseline)
    examples = []
    for name, pixel in (("inner-gap", (10, 15)), ("outer-gap", (2, 8))):
        changed = walls.copy()
        changed[pixel] = 0
        labels = pipeline.run(changed).labels
        np.savez_compressed(args.output / f"{name}.npz", labels=labels)
        report = compare_regions(baseline, labels)
        wall_iou = float(((walls > 0) & (changed > 0)).sum() / (walls > 0).sum())
        examples.append({"case": name, "wall_iou": wall_iou, "summary": report["summary"]})
    print(
        json.dumps({"scope": "generated geometry demonstration, not accuracy", "cases": examples})
    )


if __name__ == "__main__":
    main()
