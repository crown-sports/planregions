import json

import numpy as np
import pytest

from planregions import RegionConfig, RegionPipeline
from planregions.compare import compare_regions


def _two_room_walls():
    walls = np.zeros((20, 30), np.uint8)
    walls[2, 2:28] = walls[17, 2:28] = 255
    walls[2:18, 2] = walls[2:18, 27] = walls[2:18, 15] = 255
    return walls


def _check_conservation(report):
    summary = report["summary"]
    assert summary["before_foreground_px"] == (
        summary["shared_foreground_px"] + summary["to_background_px"]
    )
    assert summary["after_foreground_px"] == (
        summary["shared_foreground_px"] + summary["from_background_px"]
    )
    assert summary["total_pixels"] == sum(
        summary[key]
        for key in (
            "shared_foreground_px",
            "to_background_px",
            "from_background_px",
            "unchanged_background_px",
        )
    )
    for group in report["groups"]:
        assert group["before_area_px"] == group["overlap_px"] + group["to_background_px"]
        assert group["after_area_px"] == group["overlap_px"] + group["from_background_px"]
    assert (
        sum(item["overlap_px"] for item in report["overlaps"]) == (summary["shared_foreground_px"])
    )


def test_id_permutation_is_unchanged_and_inputs_are_not_modified():
    before = np.array([[0, 2, 2, 0], [9, 9, 0, 0]], np.int32)
    after = np.array([[0, 71, 71, 0], [3, 3, 0, 0]], np.uint64)
    originals = before.copy(), after.copy()
    before.flags.writeable = after.flags.writeable = False
    report = compare_regions(before, after)
    assert [group["kind"] for group in report["groups"]] == ["unchanged", "unchanged"]
    assert [(edge["before_id"], edge["after_id"]) for edge in report["overlaps"]] == [
        (2, 71),
        (9, 3),
    ]
    assert all(
        edge["before_fraction"] == edge["after_fraction"] == 1 for edge in report["overlaps"]
    )
    assert report["summary"]["to_background_px"] == 0
    assert report["summary"]["from_background_px"] == 0
    assert np.array_equal(before, originals[0])
    assert np.array_equal(after, originals[1])
    assert json.loads(json.dumps(report, allow_nan=False)) == report
    _check_conservation(report)


def test_one_missing_internal_wall_pixel_reports_room_merge():
    walls = _two_room_walls()
    damaged = walls.copy()
    damaged[10, 15] = 0
    pipeline = RegionPipeline(RegionConfig(min_area=1))
    before, after = pipeline.run(walls), pipeline.run(damaged)
    report = compare_regions(before.labels, after.labels)
    assert np.count_nonzero(walls != damaged) == 1
    assert np.count_nonzero(damaged) / np.count_nonzero(walls) > 0.98
    assert report["summary"]["before_region_count"] == 2
    assert report["summary"]["after_region_count"] == 1
    assert report["summary"]["group_counts"]["merge"] == 1
    assert report["groups"][0]["before_area_px"] == 322
    assert report["groups"][0]["after_area_px"] == 323
    assert report["groups"][0]["from_background_px"] == 1
    _check_conservation(report)


def test_one_missing_exterior_wall_pixel_reports_room_disappearance():
    walls = _two_room_walls()
    damaged = walls.copy()
    damaged[2, 8] = 0
    pipeline = RegionPipeline(RegionConfig(min_area=1))
    report = compare_regions(pipeline.run(walls).labels, pipeline.run(damaged).labels)
    assert report["summary"]["group_counts"]["disappeared"] == 1
    assert report["summary"]["group_counts"]["unchanged"] == 1
    assert report["summary"]["before_foreground_px"] == 322
    assert report["summary"]["after_foreground_px"] == 154
    disappeared = next(group for group in report["groups"] if group["kind"] == "disappeared")
    assert disappeared["to_background_px"] == disappeared["before_area_px"] == 168
    assert disappeared["overlap_px"] == 0
    region = next(
        region for region in report["before_regions"] if region["id"] in disappeared["before_ids"]
    )
    assert region["to_background_fraction"] == 1.0
    _check_conservation(report)


def test_explicit_separator_is_a_split_with_wall_pixel_loss():
    walls = _two_room_walls()
    walls[3:17, 15] = 0
    pipeline = RegionPipeline(RegionConfig(min_area=1))
    before = pipeline.run(walls)
    after = pipeline.run(walls, separators=(((15, 2), (15, 17)),))
    report = compare_regions(before.labels, after.labels)
    assert report["summary"]["group_counts"]["split"] == 1
    assert report["groups"][0]["to_background_px"] == 14
    assert report["groups"][0]["from_background_px"] == 0
    _check_conservation(report)


def test_hole_changes_are_reshaping_not_region_splits():
    before = np.ones((9, 9), np.int32)
    after = before.copy()
    after[3:6, 3:6] = 0
    report = compare_regions(before, after)
    assert report["summary"]["group_counts"]["reshaped"] == 1
    assert report["before_regions"][0]["to_background_px"] == 9
    assert report["before_regions"][0]["to_background_fraction"] == pytest.approx(1 / 9)
    assert report["overlaps"][0]["after_fraction"] == 1.0
    reverse = compare_regions(after, before)
    assert reverse["summary"]["group_counts"]["reshaped"] == 1
    assert reverse["after_regions"][0]["from_background_px"] == 9
    assert reverse["after_regions"][0]["from_background_fraction"] == pytest.approx(1 / 9)
    _check_conservation(report)
    _check_conservation(reverse)


def test_many_to_many_overlap_reports_one_reorganization():
    before = np.array([[1, 1], [2, 2]], np.int32)
    after = np.array([[8, 9], [8, 9]], np.int32)
    report = compare_regions(before, after)
    assert report["summary"]["group_counts"]["reorganized"] == 1
    assert report["summary"]["group_count"] == 1
    assert report["groups"][0]["before_ids"] == [1, 2]
    assert report["groups"][0]["after_ids"] == [8, 9]
    assert len(report["overlaps"]) == 4
    assert all(edge["overlap_px"] == 1 for edge in report["overlaps"])
    _check_conservation(report)


def test_single_pixel_overlap_links_transitive_changes_without_tolerance():
    before = np.array([[1, 1, 2, 3, 3]], np.int32)
    after = np.array([[4, 5, 5, 6, 6]], np.int32)
    report = compare_regions(before, after)
    assert report["summary"]["group_count"] == 2
    changed, unchanged = report["groups"]
    assert changed["kind"] == "reorganized"
    assert changed["before_ids"] == [1, 2]
    assert changed["after_ids"] == [4, 5]
    assert changed["overlap_px"] == 3
    assert unchanged["kind"] == "unchanged"
    assert unchanged["before_ids"] == [3]
    assert unchanged["after_ids"] == [6]
    _check_conservation(report)


def test_background_does_not_link_unrelated_disappearances_and_appearances():
    before = np.array([[1, 2, 0, 0]], np.int32)
    after = np.array([[0, 0, 3, 4]], np.int32)
    report = compare_regions(before, after)
    assert report["summary"]["group_counts"]["appeared"] == 2
    assert report["summary"]["group_counts"]["disappeared"] == 2
    assert report["summary"]["group_count"] == 4
    assert report["overlaps"] == []
    assert all(region["from_background_fraction"] == 1 for region in report["after_regions"])
    _check_conservation(report)


def test_sparse_uint64_ids_keep_exact_identity_across_mixed_dtypes():
    high = 2**64 - 1
    before = np.array([[0, high, high - 1], [17, 0, 17]], np.uint64)
    after = np.array([[0, 3, 3], [2, 0, 2]], np.int64)
    report = compare_regions(before, after)
    assert [region["id"] for region in report["before_regions"]] == [17, high - 1, high]
    assert report["summary"]["group_counts"]["merge"] == 1
    assert report["summary"]["group_counts"]["unchanged"] == 1
    assert json.loads(json.dumps(report))["before_regions"][-1]["id"] == high
    _check_conservation(report)


def test_many_observed_regions_do_not_require_dense_pair_storage():
    # A dense 20,000-by-20,000 contingency table would occupy several GiB.
    before = np.arange(1, 20_001, dtype=np.uint64).reshape(100, 200)
    after = before + np.uint64(2**63)
    report = compare_regions(before, after)
    assert len(report["overlaps"]) == 20_000
    assert report["summary"]["group_counts"]["unchanged"] == 20_000
    _check_conservation(report)


def test_all_background_and_one_sided_foreground_are_valid():
    background = np.zeros((2, 3), np.uint8)
    report = compare_regions(background, background)
    assert report["groups"] == report["overlaps"] == []
    assert report["before_regions"] == report["after_regions"] == []
    assert report["summary"]["unchanged_background_px"] == 6
    assert all(count == 0 for count in report["summary"]["group_counts"].values())
    foreground = np.ones_like(background)
    assert compare_regions(background, foreground)["groups"][0]["kind"] == "appeared"
    assert compare_regions(foreground, background)["groups"][0]["kind"] == "disappeared"
    _check_conservation(report)


@pytest.mark.parametrize(
    "invalid",
    [
        np.empty((0, 2), np.int32),
        np.ones((2,), np.int32),
        np.ones((2, 2, 1), np.int32),
        np.ones((2, 2), np.float64),
        np.ones((2, 2), bool),
        np.full((2, 2), -1, np.int32),
        np.full((2, 2), np.nan),
        np.ones((2, 2), object),
        [[1, 1], [1, 1]],
    ],
)
def test_invalid_inputs_are_rejected_on_both_sides(invalid):
    valid = np.ones((2, 2), np.int32)
    with pytest.raises(ValueError):
        compare_regions(invalid, valid)
    with pytest.raises(ValueError):
        compare_regions(valid, invalid)


def test_mismatched_shapes_are_rejected():
    with pytest.raises(ValueError, match="shape"):
        compare_regions(np.zeros((2, 2), np.int32), np.zeros((2, 3), np.int32))
