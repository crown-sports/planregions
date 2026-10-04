import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

from .domain import Adjacency, Attribute, Polygon, Region


def regions_from_labels(
    labels: np.ndarray, attributes: dict[int, Attribute], tolerance: float
) -> tuple[Region, ...]:
    regions = []
    for region_id in np.unique(labels):
        if region_id == 0:
            continue
        ys, xs = np.nonzero(labels == region_id)
        left, top = int(xs.min()), int(ys.min())
        right, bottom = int(xs.max()) + 1, int(ys.max()) + 1
        mask = labels[top:bottom, left:right] == region_id
        distance = distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]
        interior_y, interior_x = np.unravel_index(np.argmax(distance), mask.shape)
        regions.append(
            Region(
                int(region_id),
                polygons(mask, tolerance, (left, top)),
                (float(xs.mean()), float(ys.mean())),
                (int(interior_x) + left, int(interior_y) + top),
                len(xs),
                (left, top, right, bottom),
                attributes.get(int(region_id), Attribute()),
            )
        )
    return tuple(regions)


def polygons(
    mask: np.ndarray, tolerance: float, offset: tuple[int, int] = (0, 0)
) -> tuple[Polygon, ...]:
    # Contour hierarchy keeps inner obstacles as holes, instead of filling them.
    contours, hierarchy = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if hierarchy is None:
        return ()

    def ring(contour):
        simplified = cv2.approxPolyDP(contour, tolerance, True).reshape(-1, 2)
        if len(simplified) < 3:
            simplified = contour.reshape(-1, 2)
        if len(simplified) < 3:
            # A one-pixel-wide region still has area: encode its pixel-cell bounds.
            x, y, w, h = cv2.boundingRect(contour)
            simplified = np.array(
                [[x, y], [x + w - 0.5, y], [x + w - 0.5, y + h - 0.5], [x, y + h - 0.5]]
            )
        result = tuple((float(x + offset[0]), float(y + offset[1])) for x, y in simplified)
        return result + (result[0],)

    result = []
    for index, contour in enumerate(contours):
        if hierarchy[0, index, 3] != -1:
            continue
        holes = []
        child = hierarchy[0, index, 2]
        while child != -1:
            holes.append(ring(contours[child]))
            child = hierarchy[0, child, 0]
        result.append(Polygon(ring(contour), tuple(holes)))
    return tuple(result)


def proximity_graph(labels: np.ndarray, radius: int) -> tuple[Adjacency, ...]:
    """Euclidean proximity, not an assertion that a doorway connects two rooms."""
    if radius == 0 or not labels.any():
        return ()
    distance, indices = distance_transform_edt(labels == 0, return_indices=True)
    nearest = labels[indices[0], indices[1]]
    expanded = np.where(distance <= radius, nearest, 0)
    pairs = set()
    for first, second in ((expanded[:-1, :], expanded[1:, :]), (expanded[:, :-1], expanded[:, 1:])):
        boundary = (first != second) & (first > 0) & (second > 0)
        for a, b in np.unique(np.stack([first[boundary], second[boundary]], axis=1), axis=0):
            pairs.add((min(int(a), int(b)), max(int(a), int(b))))
    return tuple(Adjacency(first, second) for first, second in sorted(pairs))
