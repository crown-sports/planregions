from collections.abc import Sequence
from time import perf_counter

import numpy as np

from .domain import Attribute, RegionResult
from .geometry import proximity_graph, regions_from_labels


def merge_regions(result: RegionResult, groups: Sequence[Sequence[int]]) -> RegionResult:
    """Group instances without modifying excluded wall pixels or inventing semantic labels."""
    started = perf_counter()
    available = {region.id for region in result.regions}
    representatives = {region: region for region in available}
    grouped = set()
    for group in groups:
        if len(group) < 2 or len(set(group)) != len(group) or not set(group) <= available:
            raise ValueError("each merge group requires at least two distinct existing region IDs")
        if grouped & set(group):
            raise ValueError("merge groups must not overlap")
        grouped.update(group)
        for region_id in group:
            representatives[region_id] = min(group)
    canonical = {old: new for new, old in enumerate(sorted(set(representatives.values())), 1)}
    mapping = {old: canonical[representative] for old, representative in representatives.items()}
    labels = np.zeros_like(result.labels)
    old_attributes = {region.id: region.attribute for region in result.regions}
    old_areas = {region.id: region.area_px for region in result.regions}
    for old, new in mapping.items():
        labels[result.labels == old] = new
    attributes = {}
    for new in sorted(set(mapping.values())):
        source_ids = [old for old in mapping if mapping[old] == new]
        sources = [old_attributes[old] for old in source_ids]
        if len(sources) == 1:
            attributes[new] = sources[0]
        elif len({attribute.label for attribute in sources}) == 1 and sources[0].label is not None:
            confidence = (
                sum(old_attributes[old].confidence * old_areas[old] for old in source_ids)
                / sum(old_areas[old] for old in source_ids)
                if all(attribute.confidence is not None for attribute in sources)
                else None
            )
            attributes[new] = Attribute(sources[0].label, confidence, "manual-merge")
        else:
            attributes[new] = Attribute()
    config = result.metadata.get("config", {})
    regions = regions_from_labels(labels, attributes, config.get("polygon_tolerance", 1.0))
    graph = proximity_graph(labels, config.get("adjacency_radius", 6))
    operation = {
        "name": "manual_merge",
        "mapping": mapping,
        "timing_ms": (perf_counter() - started) * 1000,
    }
    metadata = {
        **result.metadata,
        "operations": [*result.metadata.get("operations", []), operation],
    }
    return RegionResult(labels, regions, graph, metadata)
