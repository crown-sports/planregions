# PlanRegions

[中文](README.zh-CN.md) · [Core methods and papers](docs/methods.md) · [Reproduction notes](docs/reproduction.md) · [Validation](docs/validation.md) · [Releases](https://github.com/chrischen-coder/planregions/releases)

A room outline may contain columns, courtyards, and obstacles. PlanRegions turns an aligned wall mask into region instances that retain those holes, with exact pixel areas, interior points, and explicit merge operations. Run it independently or use the documented output of [WallGraph](https://github.com/chrischen-coder/wallgraph).

**Status: experimental geometry toolkit.** Geometry runs without a neural model. Region types remain unknown unless you provide semantic evidence. No real drawings, annotation datasets, or trained models are included; the demo generates a simple layout in memory.

## Problem and approach

Wall pixels do not directly answer how many regions exist or whether columns and courtyards belong to usable space. Filling outlines may fill obstacles. Door openings can connect rooms; a gap in an outer wall can connect an entire interior to the outside. A region's shape alone cannot establish its semantic use.

PlanRegions separates barrier construction, partitioning, attribute assignment, and export. It excludes border-connected exterior before partitioning, retains polygon holes, and accepts explicit footprints or separator lines where the application supplies that evidence. Connected components are the default. Distance watershed is optional and can oversegment noisy predicted walls.

Partition and attribute strategies are separate, so adding semantics does not silently redraw the regions. The instance map remains the common source for area, polygons, and merges. Configuration records which barriers and partition method were used.

## Core technical choices

| Choice | What it makes usable |
| --- | --- |
| Exterior exclusion before partitioning | Consistent outside handling, with explicit footprints for open boundaries |
| One valid marker per maximum plateau | Fewer artificial seeds on flat room ridges; watershed remains optional because real predicted walls oversegment |
| Pixel-driven polygons and explicit merging | Retained holes and barriers, recomputed geometry, and recorded ID mappings |
| ID-independent instance evaluation | Compact IDs, background-aware intersection counts, and one-to-one assignment |

The [method references](docs/methods.md) connect contour hierarchy to Suzuki's border-following work, watershed to the library's documented lineage, assignment to SciPy's Jonker–Volgenant variant, and PQ to [Panoptic Segmentation](https://arxiv.org/abs/1801.00868). They explain the differences from the original protocols. [Reproduction notes](docs/reproduction.md) describe exterior leakage, plateau seeds, same-wall controls, and the severe watershed oversegmentation seen in real tests. The contribution is the independent implementation and explicit geometry contracts.

## Install and run

Requires Python 3.10 or newer. Releases are on GitHub; no PyPI package is currently published.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install "git+https://github.com/chrischen-coder/planregions.git@v0.1.1"
planregions demo --output runs/demo
```

Alternatively, install the wheel from [v0.1.1](https://github.com/chrischen-coder/planregions/releases/tag/v0.1.1). See [release instructions](docs/releasing.md) for SHA-256 verification. The demo produces three regions. The repository contains no image files; its in-memory geometry matches WallGraph's single generated demo drawing.

For your own binary mask:

```bash
planregions detect --walls /private/walls.png --output runs/regions
```

Wall is 255 and background is 0. Set `--wall-value 0` explicitly for black-wall/white-background masks. Grayscale masks are rejected; threshold them deliberately before use. All inputs use original image pixel coordinates.

With both packages installed:

```bash
wallgraph demo --output runs/walls
planregions detect --walls runs/walls/walls.png \
  --wall-metadata runs/walls/walls.json --output runs/regions
```

`--wall-metadata` validates `wallgraph/1`, dimensions, coordinates, and wall polarity. WallGraph is optional and is not an installation dependency.

## Output and geometry contracts

| File | Meaning |
| --- | --- |
| `regions.json` | `planregions/1` instances, polygons, attributes, proximity edges, configuration, timings, and merge operations |
| `labels.npz` | Exact int32 instance IDs; 0 is wall, exterior, or filtered space |
| `regions.polygons.json` | FeatureCollection-shaped polygons in the image pixel plane |
| `regions.png` | Color preview, not the authoritative instance map |

Coordinates have an upper-left origin, x right, y down. Areas count instance pixels; simplified contour area can differ. `centroid` is the pixel centroid and may lie outside a concave or holed region. `interior_point` is a region pixel selected using distance to the boundary. Bounding boxes use an inclusive upper-left and exclusive lower-right corner. There is no inferred physical scale or geographic coordinate system.

Proximity edges always have `kind: spatial_proximity`. They express geometric closeness, not evidence of a door or a traversable connection.

```python
from pathlib import Path
from planregions import RegionConfig, RegionPipeline
from planregions.io import read_mask
from planregions.operations import merge_regions

walls = read_mask(Path("/private/walls.png"))
result = RegionPipeline(RegionConfig(min_area=64)).run(walls)
# Group existing instances if IDs 1 and 2 are present.
merged = merge_regions(result, [[1, 2]])
```

Merging preserves wall/excluded pixels and holes, supports disjoint MultiPolygons, recomputes geometry, and records the operation. It groups instances rather than removing barriers. Conflicting semantic labels become unknown; matching labels' coverage is weighted by pixel area.

## Open boundaries and optional semantics

Use `--footprint /private/footprint.png` for an application-supplied building footprint, with 255 inside. Without one, a room connected to the image boundary is excluded and can be lost. Separator JSON is an array of original-coordinate endpoint pairs, for example `[[[90, 10], [90, 90]]]`; pass it through `--separators`. Closing is disabled by default. Optional splitting uses `--watershed --peak-distance 20` and needs independent validation.

An aligned class map or an external CPU ONNX adapter can assign attributes. Explicit class-name mapping and minimum majority coverage are required; the default does not infer room names from shape.

```bash
python -m pip install "planregions[onnx] @ git+https://github.com/chrischen-coder/planregions.git@v0.1.1"
planregions detect --walls /private/walls.png --image /private/plan.png \
  --attribute-model /private/attributes.onnx --class-names /private/class-names.json \
  --attribute-color rgb --min-coverage 0.6 --output runs/attributes
planregions merge --input runs/regions --groups /private/merge-groups.json \
  --output runs/merged
```

The ONNX adapter uses a persistent CPU session, float32 NCHW three-channel input scaled to 0–1, direct nearest-neighbor resize, and multiclass segmentation scores. Select RGB/BGR explicitly and ensure preprocessing matches training. The original RGB image must align with the wall mask. `attribute.confidence` is majority class coverage inside an instance, not a model probability or measured semantic accuracy. Unmapped or insufficiently covered classes remain unknown.

## What the experiments show

A frozen test sample of 30 annotated drawings contained 322 ground-truth region instances. Instance matching used class-agnostic IoU ≥ 0.5 in original coordinates.

| Input and region method | Macro PQ | Macro instance F1 |
| --- | ---: | ---: |
| Legacy wall + legacy region API | 0.68034 | 0.75300 |
| Same legacy wall + new connected components | 0.69868 | 0.75786 |
| New selected wall + new connected components | 0.56580 | 0.61474 |
| New selected wall + optional watershed | 0.29763 | 0.36960 |

With the same wall input, the mean PQ difference was +1.83 percentage points, with 95% interval [−0.69, +4.35]; this does not establish stable improvement or noninferiority. The new full pipeline regressed by 11.45 points. Watershed produced 1,273 predicted instances against 322 ground truth. Geometry with ground-truth wall input is a diagnostic, not automatic recognition accuracy. No business semantic ground truth was available. See [validation](docs/validation.md) for controls, matching definitions, uncertainty, and failure mechanisms.

## Evaluate, contribute, and cite

Keep datasets outside the repository. Evaluation JSONL contains `walls`, `instances`, `group`, and optional `footprint`; paths resolve relative to the manifest. Instance truth is a 2D integer PNG or NPZ with a `labels` array: 0 excluded, positive integers instance IDs.

```bash
planregions evaluate --manifest /private/test.jsonl --output /private/reports/regions.json
planregions benchmark --manifest /private/benchmark.jsonl --warmup 1 --repeats 3 \
  --output /private/reports/latency.json
```

Evaluation reports instance F1/PQ, not semantic accuracy. Benchmark records have `walls` and optional `image`/`footprint`; timings exclude file I/O and upstream wall inference.

See [CONTRIBUTING](CONTRIBUTING.md), [community conduct](CODE_OF_CONDUCT.md), [security reporting](SECURITY.md), and [release procedure](docs/releasing.md). CI checks Python 3.10/3.12, geometry and model contracts, formatting, buildability, and the public-file allowlist. `CITATION.cff` provides a software citation; there is no accompanying research publication.

MIT applies to the new repository code. External models, datasets, and dependencies retain their licenses. Read [NOTICE](NOTICE.md) for provenance and boundaries.
