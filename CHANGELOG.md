# Changelog

## 0.3.0 — 2026-10-08

- Add a self-contained local HTML change-review report with synchronized label previews, change filters, selection and full-resolution pixel accounting.
- Keep large label IDs exact in browser payloads, bound preview size, and preserve CLI input/output alias protection and review exit codes.
- Add a browser demonstration generated through the production comparison and renderer, checked against the implementation in CI.
- Present concrete integrations and bilingual project introductions; extraction and accuracy metrics remain unchanged.

## 0.2.0 — 2026-10-08

- Add `compare_regions` and the `compare` CLI for many-to-many region correspondence and background pixel flow.
- Report unchanged/reshaped regions, splits, merges, reorganizations, appearances, and disappearances without requiring truth or matching IDs.
- Add explicit review gates, input-file protection, and distinct input-error/review exit codes.
- Include a generated one-pixel-gap demonstration, bilingual use cases, and a continuity/opening research roadmap.
- Explain core technical choices, paper lineage, adaptation scope, and actual reproduction lessons in English and Chinese.
- Clarify that one-to-one assignment uses SciPy's modified Jonker–Volgenant solver; measured matching rules and results remain unchanged.
- Use the current `crown-sports` repository URLs. Existing extraction, merging, and accuracy metrics are unchanged.

## 0.1.1 — 2026-10-04

Initial public experimental release.

- Region instances from explicit wall masks, footprints and separators, with connected-component and optional distance-watershed strategies.
- Polygon holes, exact pixel areas, interior points, spatial proximity, explicit merges, optional CPU semantic adapters, and versioned JSON/NPZ output.
- Exterior exclusion before partitioning, one actual-pixel marker per maximum plateau, safe compaction of sparse/unsigned strategy IDs, and one-pass contingency-based evaluation.
- Frozen paired evaluation records retain the uncertain same-wall difference and negative full-pipeline results; watershed oversegmentation remains documented.
- English/Chinese documentation, provenance and MIT license, community/security policies, citation metadata, issue/PR templates, CI, and reviewed source/package assets.

No datasets, image files, pretrained weights, private credentials, or legacy Git history are distributed. This is a geometry toolkit, not a production-equivalent system replacement.
