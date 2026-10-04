"""Semantic labels are explicit evidence, never inferred from region shape alone."""

from typing import Protocol

import numpy as np

from .domain import Attribute


class AttributeStrategy(Protocol):
    name: str

    def classify(self, labels: np.ndarray, rgb: np.ndarray | None) -> dict[int, Attribute]: ...


class UnknownAttributes:
    name = "unknown"

    def classify(self, labels: np.ndarray, rgb: np.ndarray | None) -> dict[int, Attribute]:
        return {}


class ClassMapAttributes:
    """Aggregate an aligned semantic class map by majority area with explicit coverage."""

    name = "semantic-class-map"

    def __init__(self, class_map: np.ndarray, names: dict[int, str], min_coverage: float = 0.6):
        if (
            class_map.ndim != 2
            or class_map.size == 0
            or not np.issubdtype(class_map.dtype, np.integer)
            or class_map.min() < 0
        ):
            raise ValueError("class map must be a nonempty 2D nonnegative integer array")
        if not 0 < min_coverage <= 1:
            raise ValueError("min_coverage must be in (0, 1]")
        if not names or any(
            key < 0 or not isinstance(value, str) or not value for key, value in names.items()
        ):
            raise ValueError("class names require nonnegative indices and nonempty labels")
        self.class_map = class_map
        self.names = names
        self.min_coverage = min_coverage

    def classify(self, labels: np.ndarray, rgb: np.ndarray | None) -> dict[int, Attribute]:
        if self.class_map.shape != labels.shape:
            raise ValueError("class map and wall image must share pixel coordinates")
        attributes = {}
        for region in np.unique(labels):
            if region == 0:
                continue
            values, counts = np.unique(self.class_map[labels == region], return_counts=True)
            winner = int(np.argmax(counts))
            category = int(values[winner])
            coverage = float(counts[winner] / counts.sum())
            if category in self.names and coverage >= self.min_coverage:
                attributes[int(region)] = Attribute(self.names[category], coverage, self.name)
        return attributes
