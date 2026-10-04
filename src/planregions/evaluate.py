import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .io import read_mask
from .metrics import region_metrics
from .pipeline import RegionPipeline


def read_instances(path: Path) -> np.ndarray:
    if path.suffix == ".npz":
        with np.load(path, allow_pickle=False) as data:
            return data["labels"].copy()
    with Image.open(path) as image:
        values = np.asarray(image)
    if values.ndim != 2:
        raise ValueError("instance annotation must contain integer region IDs in a 2D image")
    return values


def evaluate(pipeline: RegionPipeline, manifest: Path, wall_value: int = 255) -> dict:
    records = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError("manifest is empty")
    summaries = []
    timings = []
    for record in records:
        if not all(
            isinstance(record.get(key), str) and record[key]
            for key in ("walls", "instances", "group")
        ):
            raise ValueError("records require walls, instances and group strings")
        walls = read_mask(manifest.parent / record["walls"], wall_value)
        footprint = (
            read_mask(manifest.parent / record["footprint"]) if record.get("footprint") else None
        )
        result = pipeline.run(walls, footprint=footprint)
        scores = region_metrics(
            result.labels, read_instances(manifest.parent / record["instances"])
        )
        summaries.append(scores)
        timings.append(result.metadata["timings_ms"]["total"])
    tp, fp, fn = (sum(row[key] for row in summaries) for key in ("tp", "fp", "fn"))
    denominator = tp + 0.5 * fp + 0.5 * fn
    return {
        "schema_version": "planregions-evaluation/1",
        "sample_count": len(records),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "instance_f1": tp / denominator if denominator else 1.0,
        "macro_panoptic_quality": float(np.mean([row["panoptic_quality"] for row in summaries])),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "iou_threshold": 0.5,
        "semantic_accuracy": None,
        "metric_scope": "geometry on supplied wall masks; not semantic or end-to-end wall accuracy",
        "latency_ms": {
            "median": float(np.median(timings)),
            "p95": float(np.percentile(timings, 95)),
        },
        "config": result.metadata["config"],
        "partition": result.metadata["partition"],
    }
