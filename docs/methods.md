# Keeping a region's geometry meaningful

[中文](methods.zh-CN.md) · [Reproduction notes](reproduction.md) · [Validation](validation.md)

A room outline may contain columns, courtyards, or obstacles. Those holes should survive merging, and area should still correspond to the actual pixels. PlanRegions starts from an authoritative instance map and derives polygons, interior points, attributes, and proximity from it.

| Core choice | Purpose | Implementation |
| --- | --- | --- |
| Exclude exterior before partitioning | Prevent watershed from manufacturing interior fragments; accept explicit footprints for open boundaries | [pipeline.py](../src/planregions/pipeline.py) |
| One valid marker per maximum plateau | Avoid repeated seeds along a flat rectangular-room ridge; ensure each free component has a marker | [partition.py](../src/planregions/partition.py) |
| Pixel-driven geometry with holes | Keep contour hierarchy, exact pixel areas, centroids, and independently selected interior pixels | [geometry.py](../src/planregions/geometry.py) |
| Explicit merges and attribute strategies | Preserve barriers and holes, support disjoint MultiPolygons, retain unknown semantics on conflicts, and record mappings | [operations.py](../src/planregions/operations.py), [attributes.py](../src/planregions/attributes.py) |
| ID-independent instance evaluation | Compact IDs, count intersections once with background area retained, and solve one-to-one assignment | [metrics.py](../src/planregions/metrics.py) |

These choices need reliable barriers or explicit footprint evidence. Default exterior exclusion can lose interiors connected through gaps. Plateau repair does not remove noise-driven watershed peaks; connected components remains the default.

## Research lineage

| Original work | Used here | Scope |
| --- | --- | --- |
| Suzuki et al., [Topological structural analysis of digitized binary images by border following](https://docs.opencv.org/4.13.0/d0/de3/citelist.html), CVGIP 1985 | OpenCV `findContours` with `RETR_CCOMP` hierarchy | Library algorithm; this project organizes holes, coordinates, and merging. [OpenCV's API](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html) gives the paper connection |
| Soille, Ansoult, [Automated basin delineation from digital elevation models using mathematical morphology](https://doi.org/10.1016/0165-1684(90)90127-K), Signal Processing 1990 | Marker-controlled watershed background | [scikit-image](https://scikit-image.org/docs/stable/api/skimage.segmentation.html#skimage.segmentation.watershed) attributes some queue ideas to it. We use the library with distance maps, plateau markers, and exterior exclusion, without reproducing terrain experiments |
| Crouse, [On implementing 2D rectangular assignment algorithms](https://doi.org/10.1109/TAES.2016.140952), IEEE TAES 2016 | SciPy `linear_sum_assignment` | [The solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html) is a modified Jonker–Volgenant variant; this project does not implement the classic Hungarian algorithm |
| Kirillov et al., [Panoptic Segmentation](https://arxiv.org/abs/1801.00868), CVPR 2019 | PQ's matched-IoU numerator and FP/FN penalty | Class-agnostic geometry, inclusive `IoU >= 0.5`, image macro/instance micro aggregation. It differs from the paper's semantic-class, strict `IoU > 0.5` full protocol |
| Kalervo et al., [CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image Analysis](https://arxiv.org/abs/1904.01920), 2019 | Official SVG Space and structural Wall annotations | Private geometry evaluation; no full multi-task model or leaderboard reproduction, and no business semantic truth |

Connected components and Euclidean distance transforms use SciPy. Wall recognition belongs upstream. This package does not train a region network or infer room use from shape.

## Assignment and metric scope

With `K = min(predicted instances, truth instances)`, reward is `1[IoU >= t]*(K+1) + IoU`. Qualified-match count dominates; total IoU across all assigned pairs breaks ties. Only qualified pairs enter F1/PQ. Intersections with background contribute to instance area; 0 is not a room. This explains the current implementation without changing measured results.

Paper methods, library implementations, and dataset conventions are separate parts of the result. Explicit relationships help readers decide what to replace and which scores to compare. Existing experiments support interface and geometry invariants; they do not establish improved full-pipeline accuracy or semantic correctness.
