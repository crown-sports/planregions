import json
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from PIL import Image

from .io import read_mask
from .pipeline import RegionPipeline


def benchmark(
    pipeline: RegionPipeline,
    manifest: Path,
    *,
    wall_value: int = 255,
    warmup: int = 1,
    repeats: int = 3,
) -> dict:
    if warmup < 0 or repeats < 1:
        raise ValueError("warmup must be nonnegative and repeats positive")
    records = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError("benchmark manifest is empty")
    timings = []
    geometry_timings = []
    counts = []
    shapes = set()
    for record in records:
        if not isinstance(record.get("walls"), str):
            raise ValueError("each benchmark record requires a wall mask path")
        walls = read_mask(manifest.parent / record["walls"], wall_value)
        shapes.add(walls.shape)
        rgb = None
        if record.get("image"):
            with Image.open(manifest.parent / record["image"]) as image:
                rgb = np.asarray(image.convert("RGB"))
        footprint = (
            read_mask(manifest.parent / record["footprint"]) if record.get("footprint") else None
        )
        for _ in range(warmup):
            pipeline.run(walls, rgb=rgb, footprint=footprint)
        for _ in range(repeats):
            result = pipeline.run(walls, rgb=rgb, footprint=footprint)
            timings.append(result.metadata["timings_ms"]["total"])
            geometry_timings.append(result.metadata["timings_ms"]["geometry"])
            counts.append(len(result.regions))
    return {
        "schema_version": "planregions-benchmark/1",
        "input_count": len(records),
        "measured_runs": len(timings),
        "warmup_per_input": warmup,
        "repeats_per_input": repeats,
        "input_shapes_hw": sorted(shapes),
        "pipeline_ms": {
            "median": float(np.median(timings)),
            "p95": float(np.percentile(timings, 95)),
        },
        "geometry_ms": {
            "median": float(np.median(geometry_timings)),
            "p95": float(np.percentile(geometry_timings, 95)),
        },
        "region_count_range": [min(counts), max(counts)],
        "metadata": result.metadata,
        "accuracy": None,
        "accuracy_reason": "no region instance or semantic annotations",
        "timing_scope": "region pipeline; excludes wall inference, model creation and file I/O",
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": version("numpy"),
            "opencv": version("opencv-python-headless"),
        },
    }
