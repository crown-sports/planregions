# PlanRegions

Find rooms that merged, split or disappeared between two floor-plan results.

[中文](README.zh-CN.md) · [Interactive demo](https://crown-sports.github.io/planregions/) · [v0.4.0](https://github.com/crown-sports/planregions/releases/tag/v0.4.0)

![Five colored regions before a wall gap, four after; the two upper regions merge](examples/workflow.png)

Generated example: removing the red-boxed wall section joins living and kitchen, changing **5 regions to 4**. [Run this example](https://github.com/crown-sports/planportals/blob/main/docs/workflow.md).

## Try it

Python 3.10+. No model is needed for region geometry or comparison.

```bash
python -m pip install "git+https://github.com/crown-sports/planregions.git@v0.4.0"
planregions demo --output runs/demo
```

Keep original inputs in a separate folder. Reusing an output folder replaces its generated result files.

This smaller standalone demo creates three regions. Open `runs/demo/regions.png`; use `labels.npz` for exact instance IDs and `regions.json` for pixel areas, polygons and interior points.

To process your own wall mask:

```bash
planregions detect --walls /private/walls.png --output runs/regions
```

255 means wall and 0 means background; use `--wall-value 0` for black walls. Add `--wall-metadata /private/walls.json` to check a WallGraph export's size and coordinate contract.

## Compare two runs

Use integer label maps on the same original pixel grid:

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json \
  --html-output runs/review/changes.html
```

Open `changes.html` locally. Click a region or change group to inspect both maps and the affected pixel counts. The report finds merges, splits, disappearances and background changes; renumbering alone is unchanged. It makes no network requests.

Add `--fail-on merge disappeared` to save the report and exit **1** when those changes occur. Invalid input exits **2**. For several drawings, `compare-batch` writes per-case reports and a shared summary; see the [comparison guide](docs/comparison.md).

## What the regions mean

The default pipeline removes border-connected exterior and partitions the remaining free pixels. It retains holes such as columns and courtyards. An outer-wall gap can make an interior disappear into the exterior; supply a footprint or explicit separators when the drawing needs them. Watershed is optional and can oversegment.

Areas count labeled pixels. Simplified polygons may have different areas; coordinates are image pixels, not geographic coordinates. Names in the figure are supplied annotations. Without semantic input, room types stay unknown. Without a scale, areas stay in pixels.

A change report shows what changed, not which result is correct. In the private evaluation, same-wall PQ improvement was inconclusive and the new full pipeline regressed. [Results](docs/results.md) · [Validation](docs/validation.md).

## More

[Local review guide](docs/visual-review.md) · [Geometry and input options](docs/use-cases.md) · [Implementation notes](docs/product.md) · [Methods](docs/methods.md) · [Architecture](docs/architecture.md)

[Contributing](CONTRIBUTING.md) · [Release checks](docs/releasing.md) · [Security](SECURITY.md)

MIT for code and the generated figure. No real drawings, annotations or weights are distributed. [Provenance](NOTICE.md).
