from dataclasses import replace

import cv2
import numpy as np
import pytest

from planregions import RegionConfig, RegionPipeline
from planregions.attributes import ClassMapAttributes
from planregions.domain import Attribute
from planregions.io import read_result, save_result
from planregions.metrics import region_metrics
from planregions.operations import merge_regions
from planregions.partition import WatershedPartition


def demo_walls():
    walls = np.zeros((100, 180), np.uint8)
    cv2.rectangle(walls, (10, 10), (170, 90), 255, 3)
    cv2.line(walls, (90, 10), (90, 90), 255, 3)
    cv2.line(walls, (90, 50), (170, 50), 255, 3)
    return walls


def test_three_regions_exclude_outside_and_keep_exact_pixel_area():
    walls = demo_walls()
    result = RegionPipeline().run(walls)
    assert len(result.regions) == 3
    assert result.labels[0, 0] == 0
    assert not result.labels[walls > 0].any()
    assert sum(region.area_px for region in result.regions) == (result.labels > 0).sum()
    assert all(region.attribute.label is None for region in result.regions)
    for region in result.regions:
        x, y = region.interior_point
        assert result.labels[y, x] == region.id
        left, top, right, bottom = region.bbox
        for polygon in region.polygons:
            assert all(left <= x < right and top <= y < bottom for x, y in polygon.exterior)


def test_courtyard_hole_is_not_filled_and_anchor_is_inside():
    walls = np.zeros((100, 100), np.uint8)
    cv2.rectangle(walls, (10, 10), (90, 90), 255, 3)
    cv2.circle(walls, (50, 50), 12, 255, -1)
    result = RegionPipeline().run(walls)
    assert len(result.regions) == 1
    region = result.regions[0]
    assert len(region.polygons[0].holes) == 1
    assert result.labels[round(region.centroid[1]), round(region.centroid[0])] == 0
    assert result.labels[region.interior_point[1], region.interior_point[0]] == region.id
    assert region.polygons[0].exterior[0] == region.polygons[0].exterior[-1]


def test_open_exterior_requires_footprint_instead_of_guessing_boundary():
    walls = np.zeros((100, 100), np.uint8)
    cv2.rectangle(walls, (10, 10), (90, 90), 255, 3)
    walls[5:15, 45:55] = 0
    assert not RegionPipeline().run(walls).regions
    footprint = np.zeros_like(walls)
    footprint[10:91, 10:91] = 255
    result = RegionPipeline().run(walls, footprint=footprint)
    assert len(result.regions) == 1
    assert not result.labels[footprint == 0].any()


def test_explicit_separator_splits_open_interior():
    walls = np.zeros((100, 180), np.uint8)
    cv2.rectangle(walls, (10, 10), (170, 90), 255, 3)
    assert len(RegionPipeline().run(walls).regions) == 1
    result = RegionPipeline().run(walls, separators=(((90, 10), (90, 90)),))
    assert len(result.regions) == 2
    assert not result.labels[10:91, 90].any()
    with pytest.raises(ValueError):
        RegionPipeline().run(walls, separators=(((-1, 10), (90, 90)),))


def test_distance_watershed_labels_all_pixels_in_narrow_connected_space():
    footprint = np.zeros((100, 180), np.uint8)
    cv2.circle(footprint, (45, 50), 30, 255, -1)
    cv2.circle(footprint, (135, 50), 30, 255, -1)
    footprint[45:56, 45:136] = 255
    result = RegionPipeline(partition=WatershedPartition(20)).run(
        np.zeros_like(footprint),
        footprint=footprint,
    )
    assert len(result.regions) >= 2
    assert np.all((result.labels > 0) == (footprint > 0))


def test_explicit_class_map_uses_coverage_and_leaves_other_labels_unknown():
    walls = demo_walls()
    original = RegionPipeline().run(walls)
    class_map = np.ones_like(walls)
    class_map[original.labels == 1] = 2
    attributes = ClassMapAttributes(class_map, {2: "restricted"}, 0.6)
    result = RegionPipeline(attributes=attributes).run(walls)
    assert result.regions[0].attribute.label == "restricted"
    assert result.regions[0].attribute.confidence == 1
    assert all(region.attribute.label is None for region in result.regions[1:])
    with pytest.raises(ValueError):
        ClassMapAttributes(class_map[:10], {2: "restricted"}).classify(result.labels, None)


def test_proximity_is_never_labeled_as_door_access():
    result = RegionPipeline().run(demo_walls())
    assert len(result.adjacency) == 3
    assert all(edge.kind == "spatial_proximity" for edge in result.adjacency)


def test_merging_preserves_excluded_pixels_and_disconnected_polygons(tmp_path):
    result = RegionPipeline().run(demo_walls())
    merged = merge_regions(result, [[1, 2]])
    assert len(merged.regions) == 2
    assert np.array_equal(result.labels == 0, merged.labels == 0)
    assert len(merged.regions[0].polygons) == 2
    assert merged.regions[0].area_px == result.regions[0].area_px + result.regions[1].area_px
    save_result(merged, tmp_path)
    restored = read_result(tmp_path)
    assert np.array_equal(restored.labels, merged.labels)
    with pytest.raises(ValueError):
        merge_regions(result, [[1, 2], [2, 3]])


def test_instance_metric_ignores_id_order_and_penalizes_merges():
    labels = RegionPipeline().run(demo_walls()).labels
    permuted = np.where(labels > 0, 7 - labels, 0).astype(np.int32)
    assert region_metrics(permuted, labels)["panoptic_quality"] == 1
    collapsed = (labels > 0).astype(np.int32)
    assert region_metrics(collapsed, labels)["instance_f1"] < 1
    empty = np.zeros_like(labels)
    assert region_metrics(empty, empty)["panoptic_quality"] == 1
    assert region_metrics(empty, labels)["instance_f1"] == 0


def test_instance_metric_handles_sparse_ids_and_background_area():
    predicted = np.array([[0, 1, 1, 2, 2], [0, 1, 0, 2, 0]], dtype=np.uint64)
    target = np.array([[0, 2**40, 2**40, 2**40, 0], [0, 2**40, 0, 2**50, 2**50]], dtype=np.uint64)
    scores = region_metrics(predicted, target)
    assert (scores["tp"], scores["fp"], scores["fn"]) == (1, 1, 1)
    assert scores["matched_mean_iou"] == pytest.approx(0.75)
    assert scores["instance_f1"] == pytest.approx(0.5)
    assert scores["panoptic_quality"] == pytest.approx(0.375)
    assert scores["foreground_iou"] == pytest.approx(5 / 7)


@pytest.mark.parametrize("sparse", [False, True])
def test_partition_ids_can_be_unsigned_or_sparse(sparse):
    from planregions.partition import ConnectedPartition

    class CustomPartition:
        name = "custom-unsigned-ids"

        def partition(self, free):
            labels = ConnectedPartition().partition(free).astype(np.uint64)
            if sparse:
                labels = np.where(labels > 0, labels + 2**40, 0).astype(np.uint64)
            return labels

    walls = demo_walls()
    expected = RegionPipeline().run(walls)
    actual = RegionPipeline(partition=CustomPartition()).run(walls)
    assert np.array_equal(actual.labels, expected.labels)
    assert [region.area_px for region in actual.regions] == [
        region.area_px for region in expected.regions
    ]


def test_watershed_uses_one_marker_for_a_rectangular_room_plateau():
    walls = np.zeros((160, 260), np.uint8)
    cv2.rectangle(walls, (20, 20), (240, 140), 255, 5)
    result = RegionPipeline(partition=WatershedPartition(20)).run(walls)
    assert len(result.regions) == 1
    assert result.labels[80, 130] == 1


def test_watershed_does_not_turn_exterior_connected_spaces_into_rooms():
    walls = np.zeros((160, 260), np.uint8)
    cv2.rectangle(walls, (20, 20), (240, 140), 255, 5)
    walls[15:26, 110:135] = 0
    result = RegionPipeline(partition=WatershedPartition(20)).run(walls)
    assert not result.regions
    assert result.metadata["excluded_border_components"] == 1
    footprint = np.zeros_like(walls)
    footprint[24:137, 24:237] = 255
    assert RegionPipeline(partition=WatershedPartition(20)).run(walls, footprint=footprint).regions


def test_merge_coverage_is_area_weighted_and_conflicts_remain_unknown():
    result = RegionPipeline().run(demo_walls())
    first, second, third = result.regions
    result.regions = (
        replace(first, attribute=Attribute("office", 0.8, "semantic-class-map")),
        replace(second, attribute=Attribute("office", 0.6, "semantic-class-map")),
        third,
    )
    merged = merge_regions(result, [[1, 2]])
    expected = (first.area_px * 0.8 + second.area_px * 0.6) / (first.area_px + second.area_px)
    assert merged.regions[0].attribute.confidence == pytest.approx(expected)
    assert merged.metadata["operations"][-1]["name"] == "manual_merge"
    conflicted = merge_regions(result, [[1, 3]])
    assert conflicted.regions[0].attribute.label is None


def test_invalid_mask_and_configuration_are_rejected():
    with pytest.raises(ValueError):
        RegionConfig(min_area=0)
    with pytest.raises(ValueError):
        RegionPipeline().run(np.full((20, 20), 127, np.uint8))
    with pytest.raises(ValueError):
        RegionPipeline().run(demo_walls(), footprint=np.zeros((10, 10), np.uint8))
    assert not RegionPipeline().run(np.full((20, 20), 255, np.uint8)).regions
