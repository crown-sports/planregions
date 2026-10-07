"""Describe changes between aligned region maps without assuming either is truth."""

import numpy as np

_KINDS = (
    "unchanged",
    "reshaped",
    "split",
    "merge",
    "reorganized",
    "appeared",
    "disappeared",
)


class _DisjointSets:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        first, second = self.find(first), self.find(second)
        if first == second:
            return
        if self.rank[first] < self.rank[second]:
            first, second = second, first
        self.parent[second] = first
        if self.rank[first] == self.rank[second]:
            self.rank[first] += 1


def _validate_labels(labels: np.ndarray) -> None:
    if not isinstance(labels, np.ndarray) or labels.ndim != 2 or labels.size == 0:
        raise ValueError("instance maps must be nonempty 2D arrays")
    if not np.issubdtype(labels.dtype, np.integer) or np.any(labels < 0):
        raise ValueError("instance maps must contain nonnegative integer labels")


def compare_regions(before: np.ndarray, after: np.ndarray) -> dict:
    """Return an exact, JSON-serializable comparison on the same pixel grid.

    Positive IDs are independent identifiers in each map; zero is excluded space.
    Every positive pixel overlap creates an edge in a bipartite region graph.
    Connected components of that graph describe splits, merges, and reorganizations;
    isolated positive IDs describe appearances or disappearances. A one-to-one
    component is unchanged only when its pixel supports are identical, regardless
    of the numerical IDs. Background flow is reported separately and never connects
    otherwise unrelated regions. No overlap tolerance or spatial alignment is inferred.

    For P pixels, R observed IDs, and E observed ID pairs, sorting the compressed
    pixel pairs takes O(P log P) time. Union-find takes O(E alpha(R)) time, and
    report ordering takes O(R log R). Working memory is O(P + R + E), including
    an explicit P-by-2 array; no maximum-ID array or R-by-R matrix is allocated.
    Inputs are not modified. Changes are observations, not recognition errors.
    """
    _validate_labels(before)
    _validate_labels(after)
    if before.shape != after.shape:
        raise ValueError("instance maps must share the same 2D shape")

    before_ids, before_inverse, before_counts = np.unique(
        before, return_inverse=True, return_counts=True
    )
    after_ids, after_inverse, after_counts = np.unique(
        after, return_inverse=True, return_counts=True
    )
    # Keep the two compact indices separate: mixed signed/uint64 IDs must never
    # be promoted to floats, and a multiplied pair key could overflow.
    pairs, counts = np.unique(
        np.column_stack((before_inverse.ravel(), after_inverse.ravel())),
        axis=0,
        return_counts=True,
    )
    before_regions = {
        int(region_id): {
            "id": int(region_id),
            "area_px": int(area),
            "to_background_px": 0,
            "to_background_fraction": 0.0,
        }
        for region_id, area in zip(before_ids, before_counts, strict=True)
        if region_id != 0
    }
    after_regions = {
        int(region_id): {
            "id": int(region_id),
            "area_px": int(area),
            "from_background_px": 0,
            "from_background_fraction": 0.0,
        }
        for region_id, area in zip(after_ids, after_counts, strict=True)
        if region_id != 0
    }
    offset = len(before_ids)
    sets = _DisjointSets(offset + len(after_ids))
    overlaps = []
    shared_foreground = 0
    unchanged_background = 0
    for (before_index, after_index), count in zip(pairs, counts, strict=True):
        before_index, after_index, count = int(before_index), int(after_index), int(count)
        before_id, after_id = int(before_ids[before_index]), int(after_ids[after_index])
        if before_id and after_id:
            sets.union(before_index, offset + after_index)
            shared_foreground += count
            overlaps.append(
                {
                    "before_id": before_id,
                    "after_id": after_id,
                    "overlap_px": count,
                    "before_fraction": count / before_regions[before_id]["area_px"],
                    "after_fraction": count / after_regions[after_id]["area_px"],
                }
            )
        elif before_id:
            region = before_regions[before_id]
            region["to_background_px"] = count
            region["to_background_fraction"] = count / region["area_px"]
        elif after_id:
            region = after_regions[after_id]
            region["from_background_px"] = count
            region["from_background_fraction"] = count / region["area_px"]
        else:
            unchanged_background = count

    components = {}
    for side, ids, start in (("before_ids", before_ids, 0), ("after_ids", after_ids, offset)):
        for index, region_id in enumerate(ids):
            if region_id != 0:
                root = sets.find(start + index)
                component = components.setdefault(root, {"before_ids": [], "after_ids": []})
                component[side].append(int(region_id))
    # Before-associated groups come first; completely new groups follow. Sorting
    # affects display order only, never the geometric classification.
    ordered = sorted(
        components.values(),
        key=lambda group: (
            (0, group["before_ids"][0]) if group["before_ids"] else (1, group["after_ids"][0])
        ),
    )
    groups = []
    group_counts = dict.fromkeys(_KINDS, 0)
    for index, component in enumerate(ordered, 1):
        before_group = [before_regions[region_id] for region_id in component["before_ids"]]
        after_group = [after_regions[region_id] for region_id in component["after_ids"]]
        before_area = sum(region["area_px"] for region in before_group)
        after_area = sum(region["area_px"] for region in after_group)
        to_background = sum(region["to_background_px"] for region in before_group)
        from_background = sum(region["from_background_px"] for region in after_group)
        if not before_group:
            kind = "appeared"
        elif not after_group:
            kind = "disappeared"
        elif len(before_group) > 1 and len(after_group) > 1:
            kind = "reorganized"
        elif len(before_group) > 1:
            kind = "merge"
        elif len(after_group) > 1:
            kind = "split"
        else:
            kind = "reshaped" if to_background or from_background else "unchanged"
        group_counts[kind] += 1
        groups.append(
            {
                "id": index,
                "kind": kind,
                **component,
                "before_area_px": before_area,
                "after_area_px": after_area,
                "overlap_px": before_area - to_background,
                "to_background_px": to_background,
                "from_background_px": from_background,
            }
        )
    height, width = before.shape
    before_foreground = sum(region["area_px"] for region in before_regions.values())
    after_foreground = sum(region["area_px"] for region in after_regions.values())
    return {
        "schema_version": "planregions-comparison/1",
        "image": {"width": width, "height": height},
        "coordinates": {"origin": "top_left", "x": "right", "y": "down", "unit": "px"},
        "policy": {
            "background_label": 0,
            "overlap_rule": "positive_pixel_count",
            "label_ids": "independent_identifiers",
            "classification_basis": "positive_overlap_bipartite_components",
            "alignment": "same_pixel_grid_required",
        },
        "summary": {
            "before_region_count": len(before_regions),
            "after_region_count": len(after_regions),
            "group_count": len(groups),
            "group_counts": group_counts,
            "total_pixels": before.size,
            "before_foreground_px": before_foreground,
            "after_foreground_px": after_foreground,
            "shared_foreground_px": shared_foreground,
            "to_background_px": before_foreground - shared_foreground,
            "from_background_px": after_foreground - shared_foreground,
            "unchanged_background_px": unchanged_background,
        },
        "before_regions": list(before_regions.values()),
        "after_regions": list(after_regions.values()),
        "overlaps": overlaps,
        "groups": groups,
    }
