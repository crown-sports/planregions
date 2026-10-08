import base64
import copy
import json
from html.parser import HTMLParser

import numpy as np
import pytest

from planregions.compare import compare_regions
from planregions.comparison_view import render_comparison_html


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.payload = ""
        self.in_payload = False
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.in_payload = tag == "script" and dict(attrs).get("id") == "comparison-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_payload = False

    def handle_data(self, data):
        if self.in_payload:
            self.payload += data


def _payload(page):
    parser = _PageParser()
    parser.feed(page)
    return json.loads(parser.payload)


def _decode(preview):
    packed = np.frombuffer(base64.b64decode(preview["data"]), dtype="<u4")
    if preview["encoding"] == "rle-u32le":
        runs = packed.reshape(-1, 2)
        packed = np.repeat(runs[:, 1], runs[:, 0])
    return np.asarray([preview["lookup"][int(value)]["id"] for value in packed]).reshape(
        preview["height"], preview["width"]
    )


def test_view_preserves_large_ids_and_independent_renumbering():
    before = np.array([[0, 2**63 + 7, 2**63 + 7, 2**64 - 1]], np.uint64)
    after = np.array([[0, 41, 41, 42]], np.int64)
    report = compare_regions(before, after)
    payload = _payload(render_comparison_html(before, after, report))
    assert payload["summary"]["group_counts"]["unchanged"] == 2
    assert payload["groups"][0]["before_ids"] == [str(2**63 + 7)]
    assert payload["groups"][1]["before_ids"] == [str(2**64 - 1)]
    assert _decode(payload["before"]).tolist() == [[str(int(value)) for value in before[0]]]
    assert _decode(payload["after"]).tolist() == [["0", "41", "41", "42"]]
    assert payload["before"]["lookup"][1]["group"] == payload["after"]["lookup"][1]["group"]


def test_view_uses_nn_sampling_but_retains_full_resolution_missing_region():
    before = np.zeros((2049, 17), np.uint64)
    before[0, 0] = 2**64 - 1
    before[1024:, 5:13] = 19
    after = before.copy()
    after[0, 0] = 0
    report = compare_regions(before, after)
    payload = _payload(render_comparison_html(before, after, report))
    assert (payload["before"]["height"], payload["before"]["width"]) == (1024, 8)
    assert max(payload["before"]["height"], payload["before"]["width"]) <= 1024
    # The deliberately tiny disappearing region is absent from this preview,
    # while the exact report still contains the full-resolution event and count.
    assert str(2**64 - 1) not in _decode(payload["before"])
    assert payload["summary"]["group_counts"]["disappeared"] == 1
    assert payload["summary"]["to_background_px"] == 1
    assert any(group["before_ids"] == [str(2**64 - 1)] for group in payload["groups"])
    source_rows = [int((row + 0.5) * 2049 / 1024) for row in range(1024)]
    source_columns = [int((column + 0.5) * 17 / 8) for column in range(8)]
    expected = before[np.ix_(source_rows, source_columns)].astype(str)
    np.testing.assert_array_equal(_decode(payload["before"]), expected)


def test_view_background_only_is_usable_and_has_no_invented_groups():
    before = np.zeros((3, 7), np.int32)
    report = compare_regions(before, before)
    payload = _payload(render_comparison_html(before, before, report))
    assert payload["groups"] == []
    assert payload["before"]["lookup"] == [{"id": "0", "group": None}]
    assert payload["summary"]["unchanged_background_px"] == 21
    assert payload["before"]["encoding"] == "rle-u32le"
    np.testing.assert_array_equal(_decode(payload["before"]), np.full((3, 7), "0"))


def test_view_bounds_checkerboard_encoding_instead_of_expanding_rle():
    before = np.tile(np.array([1, 2], np.uint64), (256, 192))
    after = before.copy()
    payload = _payload(render_comparison_html(before, after, compare_regions(before, after)))
    assert payload["before"]["encoding"] == "raw-u32le"
    assert len(base64.b64decode(payload["before"]["data"])) == before.size * 4
    # The preview is compact binary, never a JSON list of full pixel labels.
    assert isinstance(payload["before"]["data"], str)
    assert "pixels" not in payload["before"]
    np.testing.assert_array_equal(_decode(payload["before"]), before.astype(str))


def test_view_many_to_many_and_gate_do_not_modify_report_or_maps():
    before = np.array([[1, 1, 2, 2], [1, 1, 2, 2]], np.uint64)
    after = np.array([[10, 10, 10, 10], [20, 20, 20, 20]], np.uint64)
    before.flags.writeable = False
    after.flags.writeable = False
    report = compare_regions(before, after)
    report["review_gate"] = {"fail_on": ["reorganized"], "triggered": ["reorganized"]}
    original = copy.deepcopy(report)
    payload = _payload(render_comparison_html(before, after, report, max_side=3))
    assert payload["groups"][0]["kind"] == "reorganized"
    assert payload["groups"][0]["before_ids"] == ["1", "2"]
    assert payload["groups"][0]["after_ids"] == ["10", "20"]
    assert payload["review_gate"] == report["review_gate"]
    assert report == original
    np.testing.assert_array_equal(before, [[1, 1, 2, 2], [1, 1, 2, 2]])
    np.testing.assert_array_equal(after, [[10, 10, 10, 10], [20, 20, 20, 20]])


def test_view_escapes_title_json_and_has_no_external_assets():
    before = np.array([[0, 1]], np.int32)
    title = '</script><script src="https://example.invalid/x.js">&\u2028__COMPARISON_DATA__'
    page = render_comparison_html(before, before, compare_regions(before, before), title=title)
    parser = _PageParser()
    parser.feed(page)
    payload = json.loads(parser.payload)
    assert payload["title"] == title
    assert "</script>" not in parser.payload
    assert "\\u003c/script\\u003e" in parser.payload
    assert "\\u2028" in parser.payload
    assert len([tag for tag, _ in parser.tags if tag == "script"]) == 2
    assert all("src" not in attrs and "href" not in attrs for _, attrs in parser.tags)
    assert "default-src &#x27;none&#x27;" not in page
    assert "default-src 'none'" in page
    assert "innerHTML" not in page
    assert "fetch(" not in page


@pytest.mark.parametrize("max_side", [0, -1, 1025, True, 1.5, "32"])
def test_view_rejects_invalid_preview_limit(max_side):
    before = np.array([[0, 1]], np.int32)
    with pytest.raises(ValueError, match="max_side"):
        render_comparison_html(before, before, compare_regions(before, before), max_side=max_side)


@pytest.mark.parametrize("problem", ["schema", "shape", "missing_id", "duplicate_id", "counts"])
def test_view_rejects_report_inconsistent_with_preview(problem):
    before = np.array([[0, 1, 2]], np.int32)
    report = compare_regions(before, before)
    if problem == "schema":
        report["schema_version"] = "unexpected/1"
    elif problem == "shape":
        report["image"]["width"] = 1
    elif problem == "missing_id":
        # This preserves the count while replacing a sampled ID with a nonexistent one.
        report["groups"][0]["before_ids"] = [99]
    elif problem == "duplicate_id":
        report["groups"][1]["before_ids"] = [1]
    else:
        report["summary"]["group_counts"]["unchanged"] = 1
    with pytest.raises(ValueError):
        render_comparison_html(before, before, report)


@pytest.mark.parametrize(
    "invalid", [np.array([[0.0, 1.0]]), np.array([[0, -1]]), np.zeros((0, 2), int)]
)
def test_view_rejects_invalid_maps(invalid):
    before = np.array([[0, 1]], np.int32)
    with pytest.raises(ValueError):
        render_comparison_html(invalid, before, compare_regions(before, before))
