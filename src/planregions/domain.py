from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

Ring = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Polygon:
    exterior: Ring
    holes: tuple[Ring, ...] = ()


@dataclass(frozen=True)
class Attribute:
    label: str | None = None
    confidence: float | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class Region:
    id: int
    polygons: tuple[Polygon, ...]
    centroid: tuple[float, float]
    interior_point: tuple[int, int]
    area_px: int
    bbox: tuple[int, int, int, int]
    attribute: Attribute


@dataclass(frozen=True)
class Adjacency:
    first: int
    second: int
    kind: str = "spatial_proximity"


@dataclass
class RegionResult:
    labels: NDArray[np.int32]
    regions: tuple[Region, ...]
    adjacency: tuple[Adjacency, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        height, width = self.labels.shape
        return {
            "schema_version": "planregions/1",
            "image": {"width": width, "height": height},
            "coordinates": {"origin": "top_left", "x": "right", "y": "down", "unit": "px"},
            "labels": {"excluded_value": 0, "region_ids_start_at": 1},
            "regions": [asdict(region) for region in self.regions],
            "adjacency": [asdict(edge) for edge in self.adjacency],
            "metadata": self.metadata,
        }
