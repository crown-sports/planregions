from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RegionConfig:
    min_area: int = 64
    close_radius: int = 0
    polygon_tolerance: float = 1.0
    adjacency_radius: int = 6
    connectivity: int = 4
    separator_thickness: int = 1

    def __post_init__(self) -> None:
        if self.min_area < 1 or self.close_radius < 0 or self.adjacency_radius < 0:
            raise ValueError("min_area must be positive and radii nonnegative")
        if not isfinite(self.polygon_tolerance) or self.polygon_tolerance < 0:
            raise ValueError("polygon_tolerance must be nonnegative and finite")
        if self.connectivity not in {4, 8}:
            raise ValueError("connectivity must be four or eight")
        if self.separator_thickness < 1:
            raise ValueError("separator_thickness must be positive")
