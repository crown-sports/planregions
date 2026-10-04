# Contributing

Small fixes can be proposed directly as a pull request. For a larger change, open an issue describing the input problem, expected behavior, approach, and validation. Follow [community conduct](CODE_OF_CONDUCT.md); report security issues privately through [SECURITY](SECURITY.md).

## Development

```bash
git clone https://github.com/chrischen-coder/planregions.git
cd planregions
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,onnx]' onnx
ruff check .
ruff format --check .
pytest
python tools/release.py --check
python -m build
```

Use the `src` layout and Python 3.10+ syntax. Core services accept strategies through protocols; avoid global model loading, hidden downloads, and application-specific dependencies. New adapters must check input type, shape, class mapping, preprocessing, channel order, and actual execution providers. Geometry must keep original pixel coordinates and `planregions/1` contracts. Attribute strategies must not change instance labels.

Keep tests focused on behavior and failure modes: excluded exterior, plateau markers, holes, interior points, footprints, explicit separators, sparse IDs, matching, merge invariants, and export round trips. Use generated arrays and tiny generated model fixtures in temporary test directories. CI covers CPU model contracts; CUDA or semantic accuracy claims require separate evidence.

## Evidence and public boundaries

Accuracy changes need frozen training/validation/test groups, truth definitions, preprocessing and model identity, failure counts, uncertainty, and negative results. Separate the same-wall geometry comparison from a full wall-plus-region pipeline. Ground-truth wall input is an oracle diagnostic. Proximity is not accessibility, and class coverage is not semantic accuracy. Timings must state input sizes, device, warmup/repetitions, model creation, upstream inference, and I/O scope.

Do not commit datasets, real drawings, annotations, sample lists, model weights, per-drawing outputs, credentials, internal addresses, or private Git history. This repository contains no image assets. The release allowlist is a boundary check, not a substitute for archive review.

Contributions are licensed under MIT; submit code you have authority to license and preserve required third-party notices. Update documentation and the changelog for user-visible behavior. Follow [the release procedure](docs/releasing.md) when preparing a version.
