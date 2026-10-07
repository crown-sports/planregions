# What PlanRegions helps you build

[中文](use-cases.zh-CN.md) · [Quick start](../README.md#install-and-run) · [Methods](methods.md) · [Measured results](validation.md)

PlanRegions is useful when you have an aligned wall mask and need region instances that remain traceable to pixels. It keeps excluded space, holes, areas, and later merges consistent, so an application can build on the result without treating every outline as a filled room.

## Choose it for a concrete task

| Your task | Input | Useful output | What you still provide |
| --- | --- | --- | --- |
| Prepare selectable regions for a drawing interface | A binary wall mask; an optional building footprint or separators | Instance IDs, polygon holes, bounding boxes, and points inside regions | The interface and human review |
| Summarize space in the image plane | A region instance map | Exact labeled-pixel counts and polygons for display | A trustworthy scale before conversion to physical area |
| Group regions after a review decision | Saved results and explicit groups of IDs | Recomputed geometry, preserved excluded pixels, and recorded ID mappings | The decision about which regions belong together |
| Attach room-use evidence | An aligned class map or compatible external ONNX model | Attributes whose coverage is reported separately from geometry | Class meanings, a model or annotations, and semantic validation |
| Compare partitioning methods | Wall masks and independent instance truth | Instance F1/PQ with one-to-one matching | A frozen test protocol and interpretation of failures |
| Review a model upgrade or manual edit | Two instance maps on the same original pixel grid | Merge/split/disappearance groups and background pixel flow | A review decision; independent truth when measuring correctness |

For an annotation interface, an `interior_point` gives a valid region pixel where a marker can be placed. A centroid can fall into a courtyard or outside a concave region. Polygon holes support the visual outline; `labels.npz` remains the authoritative map for pixel membership and area. These are useful building blocks for an interface, not a bundled editor.

## Start alone, then connect wall inference

After [installation](../README.md#install-and-run), no neural model is required for:

```bash
planregions demo --output runs/demo
```

The generated layout produces three regions. For a wall result from [WallGraph](https://github.com/crown-sports/wallgraph), install both packages and run:

```bash
wallgraph demo --output runs/walls
planregions detect --walls runs/walls/walls.png \
  --wall-metadata runs/walls/walls.json --output runs/regions
```

The handoff checks dimensions, coordinates, and wall polarity. PlanRegions writes `regions.json`, `labels.npz`, `regions.polygons.json`, and a `regions.png` preview. WallGraph is optional; any correctly aligned binary wall mask can be used. The demo verifies the workflow on a simple generated layout, not recognition accuracy.

## Where its value ends today

A gap can connect two rooms, or connect the interior to the image border and exclude it as exterior. A supplied footprint bounds the working area; it does not recover every missing internal wall. Add separators only when you have evidence for them. Optional watershed can split one space into many: it oversegmented real predicted walls in the published experiment.

Default region types are unknown. Proximity edges describe geometric closeness, not doors or traversability. Polygon coordinates are image pixels, not geographic coordinates; physical area and routing require additional information. Merging groups instance IDs while retaining walls and excluded pixels—it does not erase a partition wall.

The [validation report](validation.md) shows similar mean results with the same wall input but no established stable improvement. The new end-to-end wall-plus-region pipeline regressed. Keep wall quality and partition quality separate when deciding whether this tool fits your application.

## A 30-second introduction

> PlanRegions turns a binary wall mask into region instances you can inspect and use: pixel labels, outlines with holes, exact pixel areas, and interior points. It supports explicit boundaries, region merging, and optional semantic evidence without requiring a neural model for geometry. Use it on its own or after WallGraph. The project is experimental; its value is making the geometry and its assumptions clear enough to integrate, test, and improve.

Version 0.2.0 also [compares two runs](comparison.md) to find region merges, splits, and disappearances. This connects model changes to specific spaces and gives automated review a concrete trigger.

Read [methods and papers](methods.md) for the technical choices and [reproduction notes](reproduction.md) for the problems that shaped them.
