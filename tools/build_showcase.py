"""Build public HTML examples from generated geometry, never from dataset files."""

import argparse
from pathlib import Path

import numpy as np

from planregions import RegionConfig, RegionPipeline, compare_regions, render_comparison_html


def build_examples() -> dict[str, str]:
    walls = np.zeros((20, 30), np.uint8)
    walls[2, 2:28] = walls[17, 2:28] = 255
    walls[2:18, 2] = walls[2:18, 27] = 255
    walls[2:18, 15] = 255
    pipeline = RegionPipeline(RegionConfig(min_area=1))
    before = pipeline.run(walls).labels
    examples = {}
    for name, pixel, title, kind in (
        ("inner", (10, 15), "One pixel. Two rooms become one.", "merge"),
        ("outer", (2, 8), "One pixel. One room reaches the outside.", "disappeared"),
    ):
        changed = walls.copy()
        changed[pixel] = 0
        after = pipeline.run(changed).labels
        report = compare_regions(before, after)
        iou = float(((walls > 0) & (changed > 0)).sum() / (walls > 0).sum())
        assert int((walls > 0).sum()) == 94 and int((changed > 0).sum()) == 93
        assert report["summary"]["before_region_count"] == 2
        assert report["summary"]["after_region_count"] == 1
        assert report["summary"]["group_counts"][kind] == 1
        assert round(iou * 100, 2) == 98.94
        report["demo"] = {"scope": "generated_geometry_not_accuracy", "wall_iou": iou}
        examples[f"{name}.html"] = render_comparison_html(before, after, report, title=title)
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed examples match code")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parents[1] / "docs/demo"
    )
    args = parser.parse_args()
    examples = build_examples()
    if args.check:
        for name, html in examples.items():
            if not (args.output / name).is_file() or (args.output / name).read_text() != html:
                parser.error(f"generated example differs: {name}; rerun tools/build_showcase.py")
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, html in examples.items():
            (args.output / name).write_text(html, encoding="utf-8")
    print("Generated geometry examples verified" if args.check else "Generated two HTML examples")


if __name__ == "__main__":
    main()
