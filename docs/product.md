# Region geometry notes

[README](../README.md) · [中文](../README.zh-CN.md)

The default pipeline treats wall pixels as barriers, removes free space connected to the image border and labels the remaining components. A hole in an outer wall can therefore remove a whole interior. Use an explicit footprint or separator when the drawing requires one; the pipeline does not guess that every opening is a door. [Pipeline](../src/planregions/pipeline.py) · [Partitioning](../src/planregions/partition.py).

The label map is the source for area, polygons and merging. Area counts pixels; simplified polygon area can differ. Holes remain excluded. An explicit instance merge groups regions without demolishing the wall between them. [Geometry and merge tests](../tests/test_regions.py).

Comparison uses pixel overlaps between two maps, not matching ID numbers. It records groups that split, merge, appear or disappear, plus flow to and from background. A changed number alone is not a room change. [Comparison](../src/planregions/compare.py) · [Tests](../tests/test_compare.py).

The README figure comes from the [shared generated example](https://github.com/crown-sports/planportals/blob/main/docs/workflow.md). It colors actual labels before and after removing part of a separator, with stable colors for overlapping groups. Room names are supplied annotations. The [local HTML report](visual-review.md) lets you inspect your own changes.

Geometry does not establish room use or which prediction is correct. Attributes remain unknown without semantic input. Watershed can oversegment; the [validation record](validation.md) explains why connected components remain the default and where the full evaluated pipeline regressed.
