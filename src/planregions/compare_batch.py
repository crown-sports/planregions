"""Manifest-driven comparison for model or manual-edit regression review."""

import hashlib
import json
import math
from pathlib import Path
from zipfile import BadZipFile

from .compare import compare_regions
from .evaluate import read_instances

CHANGE_KINDS = ("reshaped", "split", "merge", "reorganized", "appeared", "disappeared")


def compare_batch(
    manifest: Path,
    *,
    fail_on: tuple[str, ...] = (),
    max_background_loss_fraction: float | None = None,
    output: Path | None = None,
) -> dict:
    """Compare independent pairs sequentially; retain errors rather than dropping cases.

    Relative map paths resolve beside the manifest. If supplied, output is checked
    against *all* inputs before anything is written by the caller.
    """
    manifest = Path(manifest)
    if isinstance(fail_on, str) or any(kind not in CHANGE_KINDS for kind in fail_on):
        raise ValueError("fail_on contains an unknown change kind")
    if max_background_loss_fraction is not None and (
        isinstance(max_background_loss_fraction, bool)
        or not math.isfinite(max_background_loss_fraction)
        or not 0 <= max_background_loss_fraction <= 1
    ):
        raise ValueError("maximum background loss fraction must be finite and between 0 and 1")
    content = manifest.read_bytes()
    records = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("comparison manifest is empty")
    ids, inputs = set(), [manifest]
    for record in records:
        if not isinstance(record, dict) or any(
            not isinstance(record.get(key), str) or not record[key].strip()
            for key in ("id", "before", "after")
        ):
            raise ValueError("each comparison record needs nonempty id, before and after strings")
        if record["id"] in ids:
            raise ValueError(f"duplicate comparison id: {record['id']}")
        ids.add(record["id"])
        inputs.extend(manifest.parent / record[key] for key in ("before", "after"))
    if output is not None:
        for source in inputs:
            if output.resolve() == source.resolve() or (
                output.exists() and source.exists() and output.samefile(source)
            ):
                raise ValueError("batch output must differ from manifest and every input map")
    cases = []
    selected = sorted(set(fail_on))
    counts = dict.fromkeys(("unchanged", *CHANGE_KINDS), 0)
    for record in records:
        paths = [manifest.parent / record[key] for key in ("before", "after")]
        try:
            comparison = compare_regions(*(read_instances(path) for path in paths))
            summary = comparison["summary"]
            loss = (
                summary["to_background_px"] / summary["before_foreground_px"]
                if (summary["before_foreground_px"])
                else 0.0
            )
            triggered = [kind for kind in selected if summary["group_counts"][kind]]
            if max_background_loss_fraction is not None and loss > max_background_loss_fraction:
                triggered.append("background_loss_fraction")
            for kind, count in summary["group_counts"].items():
                counts[kind] += count
            cases.append(
                {
                    "id": record["id"],
                    "status": "review" if triggered else "passed",
                    "background_loss_fraction": loss,
                    "triggered": triggered,
                    "before_sha256": hashlib.sha256(paths[0].read_bytes()).hexdigest(),
                    "after_sha256": hashlib.sha256(paths[1].read_bytes()).hexdigest(),
                    "comparison": comparison,
                }
            )
        except (ValueError, OSError, KeyError, TypeError, EOFError, BadZipFile) as error:
            cases.append({"id": record["id"], "status": "error", "error": str(error)})
    errors = [case["id"] for case in cases if case["status"] == "error"]
    flagged = [case["id"] for case in cases if case["status"] == "review"]
    return {
        "schema_version": "planregions-batch-comparison/1",
        "manifest_sha256": hashlib.sha256(content).hexdigest(),
        "summary": {
            "case_count": len(cases),
            "compared_count": len(cases) - len(errors),
            "error_case_ids": errors,
            "review_case_ids": flagged,
            "group_counts": counts,
        },
        "review_gate": {
            "fail_on": selected,
            "max_background_loss_fraction": max_background_loss_fraction,
            "exit_code": 2 if errors else 1 if flagged else 0,
        },
        "cases": cases,
        "meaning": "changes between aligned supplied labels; no correctness or accuracy claim",
    }
