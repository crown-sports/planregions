import argparse
import json
from pathlib import Path
from zipfile import BadZipFile

import cv2
import numpy as np
from PIL import Image

from .attributes import ClassMapAttributes
from .benchmark import benchmark
from .compare import compare_regions
from .comparison_view import render_comparison_html
from .config import RegionConfig
from .evaluate import evaluate, read_instances
from .io import check_wall_contract, read_mask, read_result, save_result
from .onnx_attributes import OnnxAttributes
from .operations import merge_regions
from .partition import WatershedPartition
from .pipeline import RegionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract regions from an aligned wall mask")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("detect", "demo", "evaluate", "benchmark"):
        command = commands.add_parser(name)
        if name == "detect":
            command.add_argument("--walls", type=Path, required=True)
            command.add_argument("--wall-metadata", type=Path)
            command.add_argument("--image", type=Path)
            command.add_argument("--footprint", type=Path)
            command.add_argument("--separators", type=Path)
        if name in {"detect", "benchmark"}:
            command.add_argument("--attribute-model", type=Path)
            command.add_argument("--class-map", type=Path)
            command.add_argument("--class-names", type=Path)
            command.add_argument("--attribute-color", choices=("rgb", "bgr"), default="rgb")
            command.add_argument("--min-coverage", type=float, default=0.6)
        if name in {"evaluate", "benchmark"}:
            command.add_argument("--manifest", type=Path, required=True)
        if name == "benchmark":
            command.add_argument("--warmup", type=int, default=1)
            command.add_argument("--repeats", type=int, default=3)
        command.add_argument("--wall-value", type=int, choices=(0, 255), default=255)
        command.add_argument("--close-radius", type=int, default=0)
        command.add_argument("--min-area", type=int, default=64)
        command.add_argument("--watershed", action="store_true")
        command.add_argument("--peak-distance", type=int, default=20)
        command.add_argument("--output", type=Path, required=True)
    merge = commands.add_parser("merge")
    merge.add_argument("--input", type=Path, required=True)
    merge.add_argument("--groups", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare", help="Trace changes between aligned instance maps")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument(
        "--html-output", type=Path, help="Optional self-contained local visual review report"
    )
    compare.add_argument(
        "--fail-on",
        nargs="+",
        choices=("reshaped", "split", "merge", "reorganized", "appeared", "disappeared"),
        default=[],
        help="Write the report, then exit 1 if any chosen change kind occurs",
    )
    args = parser.parse_args()
    if args.command == "compare":
        try:
            inputs = (args.before, args.after)
            outputs = [args.output] + ([args.html_output] if args.html_output else [])
            for index, output in enumerate(outputs):
                for other in (*inputs, *outputs[:index]):
                    if output.resolve() == other.resolve() or (
                        output.exists() and other.exists() and output.samefile(other)
                    ):
                        parser.error(
                            "comparison outputs must differ from input maps and each other"
                        )
                if output.is_dir():
                    parser.error("comparison output must be a file, not a directory")
            before = read_instances(args.before)
            after = read_instances(args.after)
        except (ValueError, OSError, KeyError, TypeError, EOFError, BadZipFile) as error:
            parser.error(f"cannot read comparison inputs: {error}")
        try:
            report = compare_regions(before, after)
        except ValueError as error:
            parser.error(str(error))
        selected = sorted(set(args.fail_on))
        triggered = [kind for kind in selected if report["summary"]["group_counts"][kind]]
        report["review_gate"] = {"fail_on": selected, "triggered": triggered}
        try:
            html = render_comparison_html(before, after, report) if args.html_output else None
            for output in outputs:
                output.parent.mkdir(parents=True, exist_ok=True)
            if html is not None:
                args.html_output.write_text(html, encoding="utf-8")
            args.output.write_text(
                json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
        except (OSError, ValueError) as error:
            parser.error(f"cannot write comparison report: {error}")
        print(json.dumps({"summary": report["summary"], "review_gate": report["review_gate"]}))
        if triggered:
            raise SystemExit(1)
        return
    if args.command == "merge":
        groups = json.loads(args.groups.read_text(encoding="utf-8"))
        result = merge_regions(read_result(args.input), groups)
        save_result(result, args.output)
        print(json.dumps({"region_count": len(result.regions)}))
        return
    partition = WatershedPartition(args.peak_distance) if args.watershed else None
    config = RegionConfig(min_area=args.min_area, close_radius=args.close_radius)
    if args.command == "evaluate":
        report = evaluate(RegionPipeline(config, partition), args.manifest, args.wall_value)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
        return
    if args.command == "demo":
        walls = np.zeros((256, 384), np.uint8)
        cv2.rectangle(walls, (24, 24), (360, 232), 255, 9)
        cv2.line(walls, (192, 24), (192, 232), 255, 9)
        cv2.line(walls, (192, 128), (360, 128), 255, 9)
        result = RegionPipeline(config, partition).run(walls)
        save_result(result, args.output)
        print(json.dumps({"region_count": len(result.regions), "metadata": result.metadata}))
        return
    if args.attribute_model and args.class_map:
        parser.error("select one attribute source")
    if (args.attribute_model or args.class_map) and not args.class_names:
        parser.error("attribute inference requires --class-names")
    attributes = None
    if args.class_names:
        names = {
            int(key): value
            for key, value in json.loads(args.class_names.read_text(encoding="utf-8")).items()
        }
        if args.attribute_model:
            attributes = OnnxAttributes(
                args.attribute_model,
                names,
                color=args.attribute_color,
                min_coverage=args.min_coverage,
            )
        elif args.class_map:
            with Image.open(args.class_map) as source:
                class_map = np.asarray(source)
            attributes = ClassMapAttributes(class_map, names, args.min_coverage)
    pipeline = RegionPipeline(config, partition, attributes)
    if args.command == "benchmark":
        report = benchmark(
            pipeline,
            args.manifest,
            wall_value=args.wall_value,
            warmup=args.warmup,
            repeats=args.repeats,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(report))
        return
    walls = read_mask(args.walls, args.wall_value)
    if args.wall_metadata:
        check_wall_contract(args.wall_metadata, walls.shape, args.wall_value)
    rgb = None
    if args.image:
        with Image.open(args.image) as image:
            rgb = np.asarray(image.convert("RGB"))
    footprint = read_mask(args.footprint) if args.footprint else None
    separators = ()
    if args.separators:
        data = json.loads(args.separators.read_text(encoding="utf-8"))
        separators = tuple((tuple(first), tuple(second)) for first, second in data)
    result = pipeline.run(walls, rgb=rgb, footprint=footprint, separators=separators)
    save_result(result, args.output)
    print(json.dumps({"region_count": len(result.regions), "metadata": result.metadata}))


if __name__ == "__main__":
    main()
