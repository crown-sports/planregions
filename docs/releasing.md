# Release procedure

PlanRegions is currently distributed through GitHub experimental prereleases, not PyPI. A release contains:

- An allowlisted source ZIP with implementation, tests, documentation, and repository policies.
- A Python source distribution (`.tar.gz`) for building locally.
- A Python wheel (`.whl`) for installation; pip installs dependencies separately.
- `SHA256SUMS` for the three archives.

No image files, real datasets, annotations, sample lists, trained models, per-drawing results, private credentials, or legacy Git history are published. GitHub also generates source archives for each tag.

## Prepare a version

Work in a clean standalone checkout. Update the package version in `pyproject.toml` and `src/planregions/__init__.py`, `CHANGELOG.md`, `CITATION.cff`, versioned installation links, and validation scope. Fixes that change results require fresh frozen evaluation before claiming accuracy improvement.

```bash
python -m pip install -e '.[dev,onnx]' onnx
ruff check .
ruff format --check .
pytest
python tools/release.py --check
python -m build
python tools/release.py --output dist/planregions-source.zip
```

Review every archive member and relevant text; validate citation and workflow YAML. Install the wheel in a fresh environment and run the demo without the parent application or a semantic model. For extraction from a private parent repository, export only the reviewed allowlist into a new Git repository; never publish the parent checkout or history.

Generate checksums with `sha256sum` on Linux or `shasum -a 256` on macOS. Users can verify with `sha256sum -c SHA256SUMS` or `shasum -a 256 -c SHA256SUMS` from the download directory before installing the wheel.

## Publish and verify

Tag the exact commit whose Python 3.10/3.12 CI passed. Create a draft experimental prerelease and attach only the three reviewed archives and checksum file. Check names, sizes, and SHA-256 digests, then publish the draft. Download the assets again and verify their hashes. Confirm the repository and release are public, the tag points to the validated commit, and the standalone install works.

CI uses read-only repository permissions and actions pinned by full commit SHA. Keep release permissions out of routine pull-request jobs. See [GitHub community guidance](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories), [release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository), and [Actions security](https://docs.github.com/en/actions/reference/security/secure-use).
