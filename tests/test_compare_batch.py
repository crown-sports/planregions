import json
import subprocess
import sys

import numpy as np
import pytest

from planregions.compare_batch import compare_batch


def manifest(tmp_path):
    before = np.array([[1, 1, 0, 2, 2], [1, 1, 0, 2, 2]], dtype=np.int32)
    merged = np.array([[7, 7, 7, 7, 7], [7, 7, 7, 7, 7]], dtype=np.int32)
    lost = before.copy()
    lost[lost == 2] = 0
    for name, array in (
        ("before", before),
        ("same", before * 4),
        ("merged", merged),
        ("lost", lost),
    ):
        np.savez(tmp_path / f"{name}.npz", labels=array)
    path = tmp_path / "pairs.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"id": name, "before": "before.npz", "after": f"{name}.npz"})
            for name in ("same", "merged", "lost")
        )
    )
    return path


def test_batch_preserves_each_case_and_gates_structural_changes(tmp_path):
    path = manifest(tmp_path)
    report = compare_batch(path, fail_on=("merge",), max_background_loss_fraction=0.4)
    assert report["summary"]["compared_count"] == 3
    assert report["summary"]["review_case_ids"] == ["merged", "lost"]
    assert report["cases"][0]["status"] == "passed"
    assert report["cases"][2]["background_loss_fraction"] == 0.5
    assert report["review_gate"]["exit_code"] == 1
    assert len(report["cases"][0]["before_sha256"]) == 64
    assert compare_batch(path, max_background_loss_fraction=0.5)["review_gate"]["exit_code"] == 0


def test_failed_case_cannot_disappear_or_make_gate_pass(tmp_path):
    path = manifest(tmp_path)
    (tmp_path / "same.npz").unlink()
    report = compare_batch(path, fail_on=("merge",))
    assert report["summary"]["error_case_ids"] == ["same"]
    assert report["summary"]["compared_count"] == 2
    assert report["review_gate"]["exit_code"] == 2
    assert report["summary"]["review_case_ids"] == ["merged"]


def test_manifest_validation_and_alias_protection(tmp_path):
    path = manifest(tmp_path)
    for value in (-1, float("nan"), 1.1):
        with pytest.raises(ValueError, match="fraction"):
            compare_batch(path, max_background_loss_fraction=value)
    with pytest.raises(ValueError, match="differ"):
        compare_batch(path, output=tmp_path / "lost.npz")
    duplicate = path.read_text().splitlines()[0]
    path.write_text(duplicate + "\n" + duplicate)
    with pytest.raises(ValueError, match="duplicate"):
        compare_batch(path)


def test_cli_outputs_report_before_failure_and_keeps_inputs(tmp_path):
    path = manifest(tmp_path)
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        "-m",
        "planregions.cli",
        "compare-batch",
        "--manifest",
        str(path),
        "--output",
        str(output),
        "--fail-on",
        "merge",
    ]
    assert subprocess.run(command, capture_output=True).returncode == 1
    assert json.loads(output.read_text())["summary"]["review_case_ids"] == ["merged"]
    (tmp_path / "same.npz").unlink()
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert json.loads(output.read_text())["summary"]["error_case_ids"] == ["same"]
    before = path.read_bytes()
    command[command.index(str(output))] = str(path)
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert path.read_bytes() == before
