# See which regions changed

[中文](comparison.zh-CN.md) · [Use cases](use-cases.md) · [Research roadmap](research-roadmap.md)

A wall score can change slightly while several rooms merge or disappear. Compare two aligned instance maps to see that effect directly. This is useful when reviewing a model version, a threshold, an explicit separator, or a manual merge. Neither input needs to be ground truth.

## Run a comparison

Install PlanRegions 0.2.0 or newer. Use the exact integer `labels.npz` outputs from two runs on the same drawing:

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json
```

The CLI also reads 2D integer label images. Do not use color preview PNGs. Both maps must refer to the same original pixel grid; equal dimensions alone do not prove alignment. Zero means excluded space, and each positive number identifies an instance within that map. IDs need not match between runs.

```python
from planregions import compare_regions

report = compare_regions(before_labels, after_labels)
for group in report["groups"]:
    if group["kind"] != "unchanged":
        print(group["kind"], group["before_ids"], group["after_ids"])
```

## Read the report

Every observed positive overlap links a before instance to an after instance. Connected groups of these links describe the correspondence:

| Kind | Correspondence |
| --- | --- |
| `unchanged` | One to one, with exactly the same pixel support; renumbering is allowed |
| `reshaped` | One to one, with pixels entering or leaving excluded space; holes may change |
| `split` | One before instance overlaps several after instances |
| `merge` | Several before instances overlap one after instance |
| `reorganized` | Several instances on both sides are connected through overlaps |
| `appeared` | An after instance has no positive overlap with any before instance |
| `disappeared` | A before instance has no positive overlap with any after instance |

`overlaps` contains each observed positive ID pair, its pixel count, and fractions of both instances. `before_regions` records pixels and fractions sent to background; `after_regions` records the reverse flow. `groups` gives IDs and pixel accounting for each correspondence group. `summary.group_counts` counts groups, not rooms. The schema is `planregions-comparison/1`.

The default counts even a one-pixel overlap. Small boundary movement can therefore connect a large correspondence group. There is no implicit tolerance or one-to-one matching. Check overlap fractions before treating a group as a meaningful change. These categories describe instance correspondence; they do not measure door access or prove that geometry is correct. Background combines walls, exterior, filtered regions, and other excluded pixels, so two label maps alone cannot identify the cause of lost pixels.

## Use it in a review gate

Request an explicit exit code for selected changes:

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json \
  --fail-on merge disappeared
```

The report is written first. Exit 1 means a selected change kind occurred; without `--fail-on`, a successful comparison exits 0. Invalid inputs or report-write failures exit 2. `review_gate` records the requested and triggered kinds. A planned merge can legitimately trigger the gate. It requests review; it does not decide accuracy. Input maps are never modified, and an output path pointing or linked to either input is rejected.

## Reproduce the one-pixel example

From a source checkout, run:

```bash
python tools/compare_demo.py --output runs/change-demo
planregions compare --before runs/change-demo/closed.npz \
  --after runs/change-demo/inner-gap.npz --output runs/change-demo/inner.json
planregions compare --before runs/change-demo/closed.npz \
  --after runs/change-demo/outer-gap.npz --output runs/change-demo/outer.json
```

The tool generates arrays in memory and saves local label maps; it ships no dataset or extra image. A 20×30 layout has two enclosed regions and 94 wall pixels. Removing one inner-wall pixel leaves wall IoU at 0.98936 but merges the regions. Removing one outer-wall pixel gives the same wall IoU, while one region disappears through exterior exclusion.

| Generated case | Regions before → after | Region pixels before → after | Report |
| --- | --- | --- | --- |
| Inner gap | 2 → 1 | 322 → 323 | One merge, one new foreground pixel |
| Outer gap | 2 → 1 | 322 → 154 | One disappearance, 168 pixels sent to background |

This is a controlled geometry example, not an accuracy estimate. Its purpose is to show why region structure belongs beside wall overlap in evaluation.

## Checks and practical limits

Acceptance checks include splits, merges, many-to-many correspondence, holes, renumbering, maximum uint64 IDs, read-only and noncontiguous inputs, empty foreground, invalid inputs, and CLI review gates. An independent coordinate-set and graph-traversal oracle agreed on 1,000 fixed-seed random small-array comparisons. Pixel accounting and JSON round trips also passed on three private, previously selected severe failure cases. Those saved old/new maps contained 52/11 total instances; the report found five merge groups, five disappearances, one reorganization, and four reshaped groups. This selected subset does not estimate real-world error frequency, and it adds no new recognition-accuracy claim.

For P pixels, R observed IDs, and E observed pairs, the implementation uses O(P log P) sorting, union-find, and O(P+R+E) working memory. It allocates an explicit P×2 index array, avoiding maximum-ID and all-instance-pair matrices. Large images still need memory proportional to pixels. IDs are emitted as exact Python integers; JavaScript consumers must preserve large integers when decoding JSON.

Use [instance F1/PQ with independent truth](validation.md) to assess correctness. Use this comparison to find where a change deserves inspection. The [research roadmap](research-roadmap.md) describes the next continuity and boundary experiments.
