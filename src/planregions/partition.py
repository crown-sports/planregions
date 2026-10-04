from typing import Protocol

import numpy as np
from scipy import ndimage
from skimage.morphology import local_maxima
from skimage.segmentation import watershed


class PartitionStrategy(Protocol):
    name: str

    def partition(self, free: np.ndarray) -> np.ndarray:
        """Label every free pixel; zero means excluded."""


class ConnectedPartition:
    name = "connected-components"

    def __init__(self, connectivity: int = 4) -> None:
        self.structure = ndimage.generate_binary_structure(2, 1 if connectivity == 4 else 2)

    def partition(self, free: np.ndarray) -> np.ndarray:
        labels, _ = ndimage.label(free, self.structure)
        return labels.astype(np.int32)


class WatershedPartition:
    """Optional geometric splitting for open spaces; may over-segment."""

    name = "distance-watershed"

    def __init__(self, min_peak_distance: int = 20, connectivity: int = 4) -> None:
        if min_peak_distance < 1:
            raise ValueError("min_peak_distance must be positive")
        self.min_peak_distance = min_peak_distance
        self.structure = ndimage.generate_binary_structure(2, 1 if connectivity == 4 else 2)

    def partition(self, free: np.ndarray) -> np.ndarray:
        distance = ndimage.distance_transform_edt(np.pad(free, 1))[1:-1, 1:-1]
        maxima = local_maxima(distance, connectivity=1 if self.structure.sum() == 5 else 2)
        plateaus, count = ndimage.label(maxima & free, self.structure)
        candidates = []
        for index, bounds in enumerate(ndimage.find_objects(plateaus), 1):
            if bounds is None:
                continue
            coordinates = np.argwhere(plateaus[bounds] == index)
            center = coordinates.mean(axis=0)
            representative = coordinates[np.argmin(((coordinates - center) ** 2).sum(axis=1))]
            y, x = representative + [bounds[0].start, bounds[1].start]
            candidates.append((float(distance[y, x]), int(y), int(x)))
        # A flat maximum is one seed, even when its ridge is wider than the
        # requested spacing. Suppress nearby *distinct* maxima deterministically.
        coordinates = []
        for _, y, x in sorted(candidates, key=lambda item: (-item[0], item[1], item[2])):
            if all(
                (y - py) ** 2 + (x - px) ** 2 >= self.min_peak_distance**2 for py, px in coordinates
            ):
                coordinates.append((y, x))
        markers = np.zeros(free.shape, np.int32)
        for index, (y, x) in enumerate(coordinates, 1):
            markers[y, x] = index
        components, count = ndimage.label(free, self.structure)
        # Every connected component must receive a marker, including narrow spaces.
        for component in range(1, count + 1):
            mask = components == component
            if not markers[mask].any():
                flat = np.argmax(np.where(mask, distance, -1))
                markers.flat[flat] = int(markers.max()) + 1
        return watershed(-distance, markers, mask=free, connectivity=self.structure).astype(
            np.int32
        )
