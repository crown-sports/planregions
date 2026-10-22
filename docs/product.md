# Where PlanRegions fits

**User and decision:** a developer reviewing masks or a model change needs to know whether rooms merge, split or disappear before accepting the output. Start with the [browser example](https://crown-sports.github.io/planregions/), then compare your own aligned integer maps. Room extraction and comparison do not require a neural model.

| Current, checkable value | Evidence | Boundary |
| --- | --- | --- |
| Keep exterior and courtyard/column holes out of region area | [`pipeline.py`](../src/planregions/pipeline.py), [`test_regions.py`](../tests/test_regions.py) | Open exterior boundaries need a supplied footprint; geometry does not establish room use |
| Compare overlap groups without relying on matching instance IDs | [`compare.py`](../src/planregions/compare.py), [`test_compare.py`](../tests/test_compare.py) | Same original grid required; a change does not prove either run is correct |
| Retain failed cases and gate structural/background loss across a manifest | [`compare_batch.py`](../src/planregions/compare_batch.py), [`test_compare_batch.py`](../tests/test_compare_batch.py) | Thresholds are caller policies, not universal quality standards |

Use connected components or [scikit-image watershed](https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_watershed.html) directly for a small segmentation experiment. PlanRegions adds common exterior/area/export contracts and review reports. Use [Shapely](https://github.com/shapely/shapely) for general vector geometry; it is complementary to the pixel-instance bookkeeping here. Neither library is claimed to be slower or less accurate. A general image model can provide masks, but its textual room count does not replace an aligned map that can be compared and audited.

The [validation record](validation.md) and [reproduction notes](reproduction.md) include severe watershed oversegmentation. The browser's one-pixel case is a controlled example, not an end-to-end recognition benchmark. [Run a shared measurement/change/closure example](https://github.com/crown-sports/planportals/blob/main/docs/workflow.md) to inspect the contracts across packages.

**Next priorities:** collect permissioned opening/exterior failure cases and reviewer corrections, then compare structural changes with task-level correctness on held-out drawings. Current value comes from tested bookkeeping and visible failure modes. No proprietary dataset, recognition advantage or proven adoption barrier is established; these are development priorities, not present capabilities.
