import json
import sys

import numpy as np
import pytest

from planregions import cli


def _arguments(tmp_path):
    before = tmp_path / "before.npz"
    after = tmp_path / "after.npz"
    np.savez_compressed(before, labels=np.array([[1, 1, 0, 2, 2]], np.uint64))
    np.savez_compressed(after, labels=np.array([[2**64 - 1] * 5], np.uint64))
    return [
        "planregions",
        "compare",
        "--before",
        str(before),
        "--after",
        str(after),
        "--output",
        str(tmp_path / "changes.json"),
        "--html-output",
        str(tmp_path / "changes.html"),
    ]


def test_visual_compare_uses_one_report_and_writes_both_before_gate(tmp_path, monkeypatch):
    arguments = _arguments(tmp_path)
    monkeypatch.setattr(sys, "argv", [*arguments, "--fail-on", "merge"])
    compare = cli.compare_regions
    calls = []

    def counted(before, after):
        result = compare(before, after)
        calls.append(result)
        return result

    monkeypatch.setattr(cli, "compare_regions", counted)
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert len(calls) == 1
    report = json.loads((tmp_path / "changes.json").read_text())
    assert report == calls[0]
    assert report["review_gate"]["triggered"] == ["merge"]
    html = (tmp_path / "changes.html").read_text()
    assert "18446744073709551615" in html
    assert "merge" in html and "<!doctype html>" in html.lower()


@pytest.mark.parametrize("alias", ["path", "hard", "symbolic"])
@pytest.mark.parametrize("target", ["input", "json"])
def test_visual_output_aliases_rejected_before_writes(tmp_path, monkeypatch, alias, target):
    arguments = _arguments(tmp_path)
    destination = tmp_path / ("before.npz" if target == "input" else "changes.json")
    if target == "json":
        destination.write_bytes(b"existing review")
    original = destination.read_bytes()
    html = destination
    if alias != "path":
        html = tmp_path / "alias.html"
        if alias == "hard":
            html.hardlink_to(destination)
        else:
            html.symlink_to(destination)
    arguments[arguments.index("--html-output") + 1] = str(html)
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert destination.read_bytes() == original
    if target == "input":
        assert not (tmp_path / "changes.json").exists()


def test_html_directory_error_keeps_existing_json(tmp_path, monkeypatch):
    arguments = _arguments(tmp_path)
    (tmp_path / "changes.html").mkdir()
    output = tmp_path / "changes.json"
    output.write_bytes(b"existing review")
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert output.read_bytes() == b"existing review"
