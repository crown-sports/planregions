# Validation snapshot — 2026-10-04

This is a frozen engineering comparison of region geometry. The repository is released as an experimental library; the measurements do not establish production-equivalent full-pipeline quality or semantic recognition accuracy.

## Data and controls

Human annotations came from [CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k) and the [official CC BY-NC 4.0 archive](https://zenodo.org/records/2613548). Images, annotations, sample lists, models, and per-drawing outputs remain private.

Selection seed 20261003 was fixed before inference. Official validation/test splits supplied 15/30 balanced drawings; test contained ten each from colorful, high_quality, and high_quality_architectural. Floor-plan groups and identical image bytes did not overlap between splits; near duplicates were not exhaustively excluded. Legacy model training exposure is unknown, including possible exposure to official test drawings.

Ground-truth instances rasterized each SVG Space, excluded Outdoor/Background, and cleared structural Wall pixels. There were 322 test instances. Structural Wall label 2 includes annotated door/window opening structures and differs from a perfectly closed opaque barrier. These region labels do not provide the legacy application's business semantic truth.

The wall threshold 0.5 and closing radius 2 were selected only on validation. After the validation-driven geometry fixes, validation end-to-end macro PQ was 0.61747 with connected components and 0.36000 with watershed; connected components was frozen before test. The region stage used minimum area 64, no closing, no truth footprint, and no truth separator lines. The optional watershed comparison used peak distance 20 without test tuning.

## Matching and accuracy

Predictions and truth use original image coordinates. SciPy's modified Jonker–Volgenant solver first maximizes matches with `IoU >= 0.5`, then total IoU across all assigned pairs, including subthreshold pairs. Only qualified pairs enter the metrics. Matching is class-agnostic. Instance F1 is `TP / (TP + 0.5 FP + 0.5 FN)`; PQ replaces the numerator with summed qualified IoU. This differs from strict `IoU > 0.5` or class-aware benchmarks. Macro averages images equally; micro aggregates instance counts and qualified IoU. See [methods](methods.md) for the objective and research lineage.

All 30 test cases completed; no failures were dropped. The legacy region API retained its attribute model and geometry adjustments, while new default attributes were unknown. The same-wall row controls upstream wall input to distinguish geometry from the full pipeline.

| Input and region method | Macro PQ | Macro F1 | Micro PQ | Predicted instances |
| --- | ---: | ---: | ---: | ---: |
| Legacy wall + legacy region API | 0.68034 | 0.75300 | 0.69466 | 330 |
| Same legacy wall + new connected components | 0.69868 | 0.75786 | 0.72019 | 296 |
| New selected wall + new connected components | 0.56580 | 0.61474 | 0.55180 | 181 |
| New selected wall + optional watershed | 0.29763 | 0.36960 | 0.22636 | 1273 |
| Truth wall + new connected components | 0.79272 | 0.83008 | 0.82173 | 259 |
| Truth wall + optional watershed | 0.79583 | 0.83897 | 0.79025 | 387 |

Truth-wall rows use human input and are diagnostic, not fully automatic recognition results. Even truth walls do not resolve all open spaces or annotation conventions.

Paired source-stratified bootstrap used 10,000 repetitions, seed 20261003, percentile 95% intervals:

- Same legacy wall plus new geometry minus legacy region API: **+1.83 percentage points**, interval **[−0.69, +4.35]**, 24 improvements and six regressions. The interval crosses zero; stable improvement or noninferiority is not established.
- New full wall-plus-region pipeline minus legacy: **−11.45 points**, interval **[−20.25, −3.40]**, 15 improvements and 15 regressions.

Legacy full-pipeline TP/FP/FN was 250/80/72; new full-pipeline counts were 151/30/171. New-wall recall fell from 0.95247 to 0.88687 despite improved wall IoU over the final legacy mask. Thin-wall gaps can merge rooms or connect them to exterior, after which default outside exclusion removes interior space. Private case review supports this mechanism; not every error received a manual cause label. Watershed greatly oversegmented predicted masks and remains optional.

## Repairs and engineering validation

Version 0.1.1 excludes border-connected free space before partitioning, places one valid-pixel marker per maximum plateau, safely compacts sparse/unsigned strategy IDs, and uses a single pixel contingency pass for the unchanged matching rule. Repairs used validation failures and constructed counterexamples before the frozen test run. Plateau repair does not eliminate noise-driven distance peaks.

Twenty region tests passed locally; both extracted packages passed 33 local tests and 32 server tests with one CPU-only wall check skipped. One hundred generated layouts passed geometry/protocol invariants, and five generated layouts completed JSON/NPZ round trips. These checks are not recognition accuracy measurements. Attribute injection left geometry unchanged on all 45 validation/test drawings; no semantic accuracy is reported without business semantic truth.

The common accuracy runtime used Linux, Python 3.12.14, NumPy 1.26.4, OpenCV 4.11.0.86, SciPy 1.14.1, scikit-image 0.24.0, and ORT GPU 1.26.0. Region geometry and attributes executed on CPU.

An earlier four-drawing run used one warmup and three calls per drawing, excluding upstream walls, I/O, model construction, and warmup. Region-only median/P95 was 41.76/232.51 ms; with an external CPU semantic model it was 741.66/1383.22 ms. Those 12 measurements used a different dependency environment and lacked a paired legacy timing control. They do not establish production tail latency, software speedup, or end-to-end P95.

See [the detailed Chinese record](results.md) for historical timing and model-interface details. Further work needs opening/footprint evidence, finer-wall recall, independent business geometry and semantic truth, and a newly frozen holdout after future tuning.

## 0.2.0 change-diagnosis checks — 2026-10-08

Extraction and the above accuracy calculations are unchanged. The new `compare_regions` API and CLI diagnose correspondence between two aligned instance maps. Fifty local tests passed, including background flow, splits/merges, many-to-many correspondence, ID renumbering, maximum uint64 IDs, 20,000 independent regions, input-file link protection, and distinct review/input-error exits. An independent coordinate-set/DFS oracle agreed on 1,000 random small-array cases, seed 20261008.

Three private saved cases, previously chosen for severe end-to-end regressions, completed comparison, pixel-accounting checks, and JSON round trips. Together their old/new maps had 52/11 instances, with five merge groups, five disappearances, one reorganization, and four reshaped groups. These are observations on a selected subset, not new accuracy scores or estimates of error frequency.

Single comparison calls on those 3.61–6.95-million-pixel maps took 3.24–6.42 seconds locally, excluding file I/O. The macOS arm64 process used Python 3.12.12 and NumPy 2.5.3; its cumulative peak RSS was about 656 MiB including imports and sequential map loading. This was an engineering smoke check with no repeated latency benchmark. Sorting the explicit pixel-pair array still costs memory proportional to image size. See [comparison details and the generated one-pixel example](comparison.md); the [research roadmap](research-roadmap.md) separates validated diagnostics from proposed continuity training.

## 0.3.0 visual-review checks — 2026-10-08

The extraction and comparison algorithms, frozen recognition measurements, and 0.2.0 comparison observations above are unchanged. Seventy-eight PlanRegions tests and thirteen WallGraph tests passed locally. New checks cover exact uint64 ID strings, bounded nearest-neighbor previews, compressed and raw preview encoding, HTML/script escaping, report validation, output link protection, and writing the paired JSON/HTML outputs before a review-gate exit.

The two published browser examples are generated from a 20 × 30 array with 94 wall pixels. Removing one inner-wall pixel merges two regions; removing one outer-wall pixel connects one region to excluded space. Both have 93/94 wall IoU (98.94%) and two-to-one region counts. These constructed examples explain a failure mechanism; they are not model accuracy or prevalence estimates. CI regenerates both through the production renderer and checks byte equality. No dataset files, labels, model weights, or private reports are included. See [visual-review usage and limits](visual-review.md).
