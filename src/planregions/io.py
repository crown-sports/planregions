import json
from pathlib import Path

import numpy as np
from PIL import Image

from .domain import Attribute, RegionResult
from .geometry import proximity_graph, regions_from_labels


def read_result(directory: Path) -> RegionResult:
    metadata = json.loads((directory / "regions.json").read_text(encoding="utf-8"))
    with np.load(directory / "labels.npz", allow_pickle=False) as archive:
        labels = archive["labels"].copy()
    if (
        metadata.get("schema_version") != "planregions/1"
        or labels.ndim != 2
        or not np.issubdtype(labels.dtype, np.integer)
        or labels.min() < 0
    ):
        raise ValueError("invalid region result")
    if metadata.get("image") != {"height": labels.shape[0], "width": labels.shape[1]}:
        raise ValueError("region metadata dimensions do not match labels")
    if metadata.get("coordinates") != {
        "origin": "top_left",
        "x": "right",
        "y": "down",
        "unit": "px",
    }:
        raise ValueError("region coordinate convention is incompatible")
    attributes = {region["id"]: Attribute(**region["attribute"]) for region in metadata["regions"]}
    if set(np.unique(labels)) - {0} != set(attributes):
        raise ValueError("region metadata IDs do not match labels")
    config = metadata.get("metadata", {}).get("config", {})
    regions = regions_from_labels(labels, attributes, config.get("polygon_tolerance", 1.0))
    adjacency = proximity_graph(labels, config.get("adjacency_radius", 6))
    return RegionResult(labels, regions, adjacency, metadata.get("metadata", {}))


def read_mask(path: Path, wall_value: int = 255) -> np.ndarray:
    if wall_value not in {0, 255}:
        raise ValueError("wall_value must be zero or 255")
    with Image.open(path) as source:
        values = np.asarray(source.convert("L"))
    if not np.isin(values, [0, 255]).all():
        raise ValueError("mask must contain only 0 and 255; threshold grayscale data explicitly")
    return (values == wall_value).astype(np.uint8) * 255


def check_wall_contract(metadata: Path, shape: tuple[int, int], wall_value: int) -> None:
    data = json.loads(metadata.read_text(encoding="utf-8"))
    if data.get("schema_version") != "wallgraph/1":
        raise ValueError("unsupported wall schema")
    if data.get("image") != {"height": shape[0], "width": shape[1]}:
        raise ValueError("wall metadata dimensions do not match mask")
    if data.get("coordinates") != {"origin": "top_left", "x": "right", "y": "down", "unit": "px"}:
        raise ValueError("wall coordinate convention is incompatible")
    if data.get("mask", {}).get("wall_value") != wall_value:
        raise ValueError("wall polarity does not match metadata")


def save_result(result: RegionResult, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    # NPZ is the exact integer label map; the color PNG is only a preview.
    np.savez_compressed(destination / "labels.npz", labels=result.labels)
    preview = np.full((*result.labels.shape, 3), 255, np.uint8)
    features = []
    for region in result.regions:
        hue = (region.id * 137) % 255
        preview[result.labels == region.id] = (70 + hue // 3, 100 + hue // 4, 220 - hue // 3)
        coordinates = [
            [list(polygon.exterior), *[list(hole) for hole in polygon.holes]]
            for polygon in region.polygons
        ]
        features.append(
            {
                "type": "Feature",
                "id": region.id,
                "geometry": {"type": "MultiPolygon", "coordinates": coordinates},
                "properties": {
                    "area_px": region.area_px,
                    "attribute": region.attribute.label,
                    "attribute_source": region.attribute.source,
                },
            }
        )
    Image.fromarray(preview).save(destination / "regions.png")
    (destination / "regions.json").write_text(
        json.dumps(result.to_dict(), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    # Pixel-plane GeoJSON-shaped geometry, not georeferenced longitude/latitude.
    (destination / "regions.polygons.json").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "coordinate_system": "image_pixels",
                "features": features,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
