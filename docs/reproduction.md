# Lessons from running region extraction

[中文](reproduction.zh-CN.md) · [Methods and papers](methods.md) · [Validation](validation.md)

One incomplete wall can connect two rooms or an interior to the outside. The practical work therefore centered on barriers, partitioning, and instance evaluation. These notes record real paired experiments and validation-driven repairs while adapting established methods to drawings.

## Separate upstream walls from geometry

We compared region methods on the same legacy walls, then measured the new full pipeline; truth-wall input remained a diagnostic. [CubiCasa5K](https://arxiv.org/abs/1904.01920) SVG annotations yielded 322 instances in 30 test drawings, after settings were frozen on 15 validation drawings.

Same-wall macro PQ was 0.69868 for new connected components versus legacy 0.68034. Its 95% difference interval, [−0.69, +4.35] percentage points, crosses zero. New full-pipeline PQ was 0.56580 with a negative difference interval. Geometry has no established stable gain, while upstream gaps can amplify into merges and missing rooms.

## Exterior exclusion must precede partitioning

Running watershed before removing border-connected space can cut that space into fragments that no longer touch the image edge, creating false interior candidates. The repair excludes exterior first and has a constructed regression test.

Consistency does not supply missing boundary evidence. A real opening can still cause the whole interior to be excluded. Explicit footprints or separators are appropriate inputs; automatic closing remains off because it can erase real openings.

## A plateau is one marker candidate

A rectangular room can have a flat ridge in its distance map. Spacing-based peak selection can seed it repeatedly. The repair labels each maximum plateau, selects an actual member pixel, and ensures unseeded free components receive a marker.

The constructed long-room check passed. Predicted wall noise still made multiple peaks: watershed produced 1,273 instances against 322 truth instances and macro PQ 0.29763; connected components reached 0.56580. A correct repair does not establish that a strategy suits real inputs. Watershed remains optional.

## Keep the pixel map authoritative

Pixel counts retain the effect of holes and excluded space. Simplified polygons can have different area, and centroids can fall into holes, so an interior pixel is stored separately. Merging rebuilds geometry without removing barriers; semantic conflicts remain unknown.

Twenty region tests, generated layouts, and JSON/NPZ round trips check these behaviors. Attribute injection left geometry unchanged on all 45 validation/test drawings. Business semantic truth was absent, so no semantic accuracy is reported.

## Align metrics before interpreting speed

IDs should not affect scores. Compact IDs and a contingency count retain background contributions to area. The actual assignment solver is SciPy's Jonker–Volgenant variant. PQ follows the matched-IoU/FP/FN structure of [Panoptic Segmentation](https://arxiv.org/abs/1801.00868), with explicit class-agnostic and inclusive-threshold differences from the paper protocol.

One generated 512×512, 64-instance case had identical metrics under old/new counting, taking 392.26/8.06 ms in single calls. This checks optimization consistency; it is not repeated performance evidence or a production speed ratio.

## Reuse the approach

Fix polarity, coordinates, truth instances, and open-space conventions first. Establish a connected-component baseline, then separately validate footprints, separators, and watershed. Same-wall comparisons isolate geometry; full-pipeline tests answer application usefulness. Future tuning needs a fresh holdout.

Public code and commands work with users' authorized inputs. Frozen selections, reference models, and per-drawing outputs are private, so the package cannot reconstruct the exact paired table. Only WallGraph's single generated demo image is public; PlanRegions generates its demo in memory.
