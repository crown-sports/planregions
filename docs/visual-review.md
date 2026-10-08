# Review region changes in your browser

[中文](visual-review.zh-CN.md) · [Interactive generated example](https://crown-sports.github.io/planregions/) · [Comparison contract](comparison.md)

When a model update or a manual edit changes a room, a summary score does not show where to look. PlanRegions 0.3.0 can save a local HTML report alongside the exact JSON comparison. Click a change group or a preview region to inspect the corresponding before/after instances, their overlap, and pixels entering or leaving excluded space. Filter by change type to focus a review.

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json \
  --html-output runs/review/changes.html --fail-on merge disappeared
```

Open `changes.html` directly in a browser. No web server, neural model, browser extension, or CDN is required. The generated report makes no network requests. Both inputs must be aligned integer labels on the same original pixel grid; neither must be ground truth.

The CLI calculates the comparison once. JSON and HTML use that same report, including the explicit review gate. Exit 1 means a chosen change type occurred after both outputs were saved; exit 2 means an input, rendering, or output error. A write failure may leave an output file, so successful completion is required before using the pair. Paths resolving to input files, or outputs resolving to each other, are rejected, including hard links and symbolic links.

## What the preview can establish

The two canvases use consistent change-group colors; background is gray. Selection highlights the group across both maps. The group list and pixel accounting are calculated at full resolution. Positive overlap, including one pixel, defines correspondence; changing a label number alone does not create a change. The comparison does not decide which result is correct or whether regions are connected by a door.

Canvas previews are nearest-neighbor samples, bounded to a maximum side of 1,024 pixels. A small component or a one-pixel gap may disappear in a large-image preview. Use the original label files for pixel-exact inspection. The maps contain integer IDs; the HTML keeps IDs as decimal strings to preserve values larger than JavaScript's safe-integer limit. Numbers in the exact JSON remain Python integers, as described in [the comparison guide](comparison.md).

The HTML contains your label previews and per-region statistics. Keep it with your private results; creating it does not upload or publish it. Share it only as deliberately as you would the input labels. The public online examples use only small generated arrays and do not load any dataset.

## Python API

```python
from pathlib import Path
from planregions import compare_regions, render_comparison_html

report = compare_regions(before_labels, after_labels)
html = render_comparison_html(before_labels, after_labels, report, max_side=1024)
Path("/private/review.html").write_text(html, encoding="utf-8")
```

Pass the report returned from comparing those same inputs. The renderer is separate from the comparison algorithm and does not recompute the diagnostic. It validates the report's basic schema, image shape, and preview mappings; it cannot establish provenance of an independently supplied report.

To regenerate the public geometry examples from a source checkout, run `python tools/build_showcase.py`. CI runs `python tools/build_showcase.py --check` to keep the displayed example tied to the actual implementation.
