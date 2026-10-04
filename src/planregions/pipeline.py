from dataclasses import asdict
from time import perf_counter

import cv2
import numpy as np
from scipy import ndimage

from .attributes import AttributeStrategy, UnknownAttributes
from .config import RegionConfig
from .domain import RegionResult
from .geometry import proximity_graph, regions_from_labels
from .partition import ConnectedPartition, PartitionStrategy


class RegionPipeline:
    def __init__(
        self,
        config: RegionConfig | None = None,
        partition: PartitionStrategy | None = None,
        attributes: AttributeStrategy | None = None,
    ) -> None:
        self.config = config or RegionConfig()
        self.partition = partition or ConnectedPartition(self.config.connectivity)
        self.attributes = attributes or UnknownAttributes()

    def run(
        self,
        walls: np.ndarray,
        *,
        rgb: np.ndarray | None = None,
        footprint: np.ndarray | None = None,
        separators: tuple[tuple[tuple[int, int], tuple[int, int]], ...] = (),
    ) -> RegionResult:
        if walls.ndim != 2 or min(walls.shape) < 1 or not np.isin(walls, [0, 1, 255]).all():
            raise ValueError("walls must be a nonempty 2D binary mask, with positive wall pixels")
        if rgb is not None and (rgb.shape != (*walls.shape, 3) or rgb.dtype != np.uint8):
            raise ValueError("original image must be aligned uint8 RGB")
        if footprint is not None and (
            footprint.shape != walls.shape or not np.isin(footprint, [0, 1, 255]).all()
        ):
            raise ValueError("footprint must be an aligned binary mask")
        start = perf_counter()
        barriers = (walls > 0).astype(np.uint8)
        if self.config.close_radius:
            size = 2 * self.config.close_radius + 1
            barriers = cv2.morphologyEx(barriers, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
        height, width = walls.shape
        for first, second in separators:
            if any(
                len(point) != 2
                or any(not isinstance(value, (int, np.integer)) for value in point)
                or not (0 <= point[0] < width and 0 <= point[1] < height)
                for point in (first, second)
            ):
                raise ValueError("separator endpoints must be integer pixels inside the image")
            cv2.line(barriers, first, second, 1, self.config.separator_thickness)
        free = barriers == 0
        exterior_components = 0
        if footprint is not None:
            free &= footprint > 0
        else:
            # Exclude the exterior before a strategy can split it into basins
            # that no longer touch the image border.
            components, _ = ndimage.label(
                free,
                ndimage.generate_binary_structure(2, 1 if self.config.connectivity == 4 else 2),
            )
            outside = np.unique(
                np.concatenate([components[0], components[-1], components[:, 0], components[:, -1]])
            )
            outside = outside[outside != 0]
            exterior_components = len(outside)
            free &= ~np.isin(components, outside)
        prepared = perf_counter()
        labels = self.partition.partition(free)
        if (
            labels.shape != free.shape
            or not np.issubdtype(labels.dtype, np.integer)
            or labels.min() < 0
            or np.any(labels[~free] != 0)
            or np.any(labels[free] == 0)
        ):
            raise ValueError("partition strategy must label all free pixels and no barriers")
        # Strategy IDs are identifiers, not array sizes. Compact very sparse IDs
        # before bincount and safely accept unsigned integer outputs as well.
        if int(labels.max()) > labels.size:
            ids, inverse = np.unique(labels, return_inverse=True)
            labels = inverse.reshape(free.shape)
            if ids[0] != 0:
                labels = labels + 1
        labels = labels.astype(np.intp, copy=False)
        excluded = set()
        if footprint is None:
            excluded = set(
                np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
            )
        counts = np.bincount(labels.ravel())
        lookup = np.zeros(len(counts), np.int32)
        next_id = 1
        for old_id in range(1, len(counts)):
            if old_id not in excluded and counts[old_id] >= self.config.min_area:
                lookup[old_id] = next_id
                next_id += 1
        labels = lookup[labels]
        partitioned = perf_counter()
        attributes = self.attributes.classify(labels, rgb)
        classified = perf_counter()
        regions = regions_from_labels(labels, attributes, self.config.polygon_tolerance)
        adjacency = proximity_graph(labels, self.config.adjacency_radius)
        end = perf_counter()
        metadata = {
            "partition": self.partition.name,
            "attributes": self.attributes.name,
            "attribute_model_sha256": getattr(self.attributes, "model_sha256", None),
            "attribute_providers": getattr(self.attributes, "providers", []),
            "attribute_color": getattr(self.attributes, "color", None),
            "config": asdict(self.config),
            "explicit_footprint": footprint is not None,
            "separator_count": len(separators),
            "excluded_border_components": exterior_components,
            "area_kind": "count_of_labeled_pixels",
            "attribute_confidence_kind": "class_area_fraction",
            "timings_ms": {
                "preparation": (prepared - start) * 1000,
                "partition": (partitioned - prepared) * 1000,
                "attributes": (classified - partitioned) * 1000,
                "geometry": (end - classified) * 1000,
                "total": (end - start) * 1000,
            },
        }
        return RegionResult(labels, tuple(regions), adjacency, metadata)
