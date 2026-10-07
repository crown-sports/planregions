import json
import sys

import numpy as np
import pytest

from planregions.cli import main


def test_compare_cli_writes_report_before_review_gate_exit(tmp_path, monkeypatch, capsys):
    before = np.array([[0, 1, 1, 0, 2, 2]], np.uint64)
    after = np.array([[0, 7, 7, 7, 7, 7]], np.uint64)
    np.savez_compressed(tmp_path / "before.npz", labels=before)
    np.savez_compressed(tmp_path / "after.npz", labels=after)
    output = tmp_path / "review" / "changes.json"
    arguments = [
        "planregions",
        "compare",
        "--before",
        str(tmp_path / "before.npz"),
        "--after",
        str(tmp_path / "after.npz"),
        "--output",
        str(output),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    main()
    report = json.loads(output.read_text())
    assert report["summary"]["group_counts"]["merge"] == 1
    assert report["review_gate"] == {"fail_on": [], "triggered": []}
    assert json.loads(capsys.readouterr().out)["summary"] == report["summary"]
    monkeypatch.setattr(sys, "argv", [*arguments, "--fail-on", "merge", "disappeared"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert json.loads(output.read_text())["review_gate"]["triggered"] == ["merge"]
    with np.load(tmp_path / "before.npz", allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive["labels"], before)


def test_compare_cli_accepts_renumbering_and_protects_input(tmp_path, monkeypatch):
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    np.savez_compressed(first, labels=np.array([[1, 0, 2]], np.uint64))
    np.savez_compressed(second, labels=np.array([[2**63, 0, 2**64 - 1]], np.uint64))
    arguments = [
        "planregions",
        "compare",
        "--before",
        str(first),
        "--after",
        str(second),
        "--output",
        str(tmp_path / "same.json"),
        "--fail-on",
        "merge",
        "disappeared",
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    main()
    original = first.read_bytes()
    arguments[arguments.index("--output") + 1] = str(first)
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert first.read_bytes() == original


@pytest.mark.parametrize("link_kind", ["hard", "symbolic"])
def test_compare_cli_rejects_output_linked_to_input(tmp_path, monkeypatch, link_kind):
    source = tmp_path / "labels.npz"
    np.savez_compressed(source, labels=np.array([[0, 1]], np.int32))
    alias = tmp_path / "alias.json"
    if link_kind == "hard":
        alias.hardlink_to(source)
    else:
        alias.symlink_to(source)
    original = source.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "planregions",
            "compare",
            "--before",
            str(source),
            "--after",
            str(source),
            "--output",
            str(alias),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert source.read_bytes() == original


@pytest.mark.parametrize("problem", ["shape", "float", "negative", "missing_labels", "corrupt"])
def test_compare_cli_input_errors_exit_two_without_a_report(tmp_path, monkeypatch, problem):
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    np.savez_compressed(first, labels=np.array([[0, 1]], np.int32))
    values = {
        "shape": np.array([[0]], np.int32),
        "float": np.array([[0, 1]], np.float32),
        "negative": np.array([[0, -1]], np.int32),
    }
    if problem in values:
        np.savez_compressed(second, labels=values[problem])
    elif problem == "missing_labels":
        np.savez_compressed(second, other=np.array([[0, 1]], np.int32))
    else:
        second.write_bytes(b"PK\x03\x04invalid archive")
    output = tmp_path / "changes.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "planregions",
            "compare",
            "--before",
            str(first),
            "--after",
            str(second),
            "--output",
            str(output),
            "--fail-on",
            "merge",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()
