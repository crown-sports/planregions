import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "release", Path(__file__).parents[1] / "tools/release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_release_contains_no_images_models_data_or_outputs():
    files = release.public_files()
    assert all(
        path.suffix not in {".png", ".jpg", ".onnx", ".pt", ".jsonl", ".npz"} for path in files
    )
