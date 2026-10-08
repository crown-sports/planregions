"""A local, self-contained review page for an existing region comparison."""

import base64
import html
import json

import numpy as np

_KINDS = ("unchanged", "reshaped", "split", "merge", "reorganized", "appeared", "disappeared")
_SUMMARY_FIELDS = (
    "before_region_count",
    "after_region_count",
    "group_count",
    "total_pixels",
    "before_foreground_px",
    "after_foreground_px",
    "shared_foreground_px",
    "to_background_px",
    "from_background_px",
    "unchanged_background_px",
)
_GROUP_FIELDS = (
    "before_area_px",
    "after_area_px",
    "overlap_px",
    "to_background_px",
    "from_background_px",
)


def _integer(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _view_report(report: dict, shape: tuple[int, int]) -> tuple[dict, dict, dict]:
    if not isinstance(report, dict) or report.get("schema_version") != "planregions-comparison/1":
        raise ValueError("expected a planregions-comparison/1 report")
    try:
        image = report["image"]
        if (
            _integer(image["height"], "image.height", 1),
            _integer(image["width"], "image.width", 1),
        ) != shape:
            raise ValueError("comparison report shape must match both maps")
        summary = {
            key: _integer(report["summary"][key], f"summary.{key}") for key in _SUMMARY_FIELDS
        }
        if summary["total_pixels"] != shape[0] * shape[1]:
            raise ValueError("comparison report pixel count must match both maps")
        summary["group_counts"] = {
            kind: _integer(report["summary"]["group_counts"][kind], f"group_counts.{kind}")
            for kind in _KINDS
        }
        groups = []
        maps = ({}, {})
        group_ids = set()
        for source in report["groups"]:
            group_id = _integer(source["id"], "group.id", 1)
            if group_id in group_ids or source["kind"] not in _KINDS:
                raise ValueError("comparison groups require unique IDs and recognized kinds")
            group_ids.add(group_id)
            group = {"id": group_id, "kind": source["kind"]}
            for side, lookup in zip(("before_ids", "after_ids"), maps, strict=True):
                group[side] = []
                for value in source[side]:
                    region_id = _integer(value, side, 1)
                    if region_id in lookup:
                        raise ValueError(
                            "each positive region ID must belong to one group per side"
                        )
                    lookup[region_id] = group_id
                    # Browser Number cannot represent all uint64 identifiers exactly.
                    group[side].append(str(region_id))
            group.update({key: _integer(source[key], f"group.{key}") for key in _GROUP_FIELDS})
            if not group["before_ids"] and not group["after_ids"]:
                raise ValueError("comparison groups must contain at least one positive region ID")
            groups.append(group)
        if len(groups) != summary["group_count"]:
            raise ValueError("comparison group count does not match the report")
        if any(
            sum(group["kind"] == kind for group in groups) != summary["group_counts"][kind]
            for kind in _KINDS
        ):
            raise ValueError("comparison change counts do not match the groups")
        if (len(maps[0]), len(maps[1])) != (
            summary["before_region_count"],
            summary["after_region_count"],
        ):
            raise ValueError("comparison region counts do not match the groups")
        return {"summary": summary, "groups": groups}, maps[0], maps[1]
    except (KeyError, TypeError) as error:
        raise ValueError("comparison report is missing required fields") from error


def _preview(labels: np.ndarray, shape: tuple[int, int], group_lookup: dict) -> dict:
    height, width = shape
    # Integer, center-aligned nearest-neighbor coordinates preserve the original
    # label dtype. Never resize uint64 labels through floating-point image APIs.
    rows = ((2 * np.arange(height, dtype=np.int64) + 1) * labels.shape[0]) // (2 * height)
    columns = ((2 * np.arange(width, dtype=np.int64) + 1) * labels.shape[1]) // (2 * width)
    sampled = labels[np.ix_(rows, columns)]
    ids, inverse = np.unique(sampled, return_inverse=True)
    lookup = []
    for value in ids:
        region_id = int(value)
        if region_id and region_id not in group_lookup:
            raise ValueError("preview contains a region ID absent from the comparison report")
        lookup.append({"id": str(region_id), "group": group_lookup.get(region_id)})
    values = inverse.ravel().astype("<u4")
    starts = np.r_[0, np.flatnonzero(values[1:] != values[:-1]) + 1]
    lengths = np.diff(np.r_[starts, values.size]).astype("<u4")
    runs = np.column_stack((lengths, values[starts])).astype("<u4")
    # Long uniform regions compress well. A checkerboard uses bounded raw preview
    # indices instead of allowing an RLE sequence to be twice as large.
    encoding = "rle-u32le" if runs.nbytes < values.nbytes else "raw-u32le"
    packed = runs if encoding == "rle-u32le" else values
    return {
        "width": width,
        "height": height,
        "encoding": encoding,
        "data": base64.b64encode(packed.tobytes()).decode("ascii"),
        "lookup": lookup,
    }


def render_comparison_html(
    before: np.ndarray,
    after: np.ndarray,
    report: dict,
    *,
    max_side: int = 1024,
    title: str = "Region change review",
) -> str:
    """Render a comparison without recomputing it or modifying inputs/report.

    ``report`` must come from ``compare_regions(before, after)`` on these same
    aligned maps. Basic schema, shape, group counts and sampled ID membership are
    checked; this renderer does not revalidate every full-resolution overlap.
    Both previews use integer nearest-neighbor sampling and at most 1024 pixels
    on either side. All displayed counts come from the full-resolution report.
    The returned HTML embeds label previews and region IDs, so treat it as a
    private result when working with private inputs. It performs no network calls.
    """
    max_side = _integer(max_side, "max_side", 1)
    if max_side > 1024:
        raise ValueError("max_side must be at most 1024")
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    for labels in (before, after):
        if (
            not isinstance(labels, np.ndarray)
            or labels.ndim != 2
            or not labels.size
            or not np.issubdtype(labels.dtype, np.integer)
            or np.any(labels < 0)
        ):
            raise ValueError("preview maps must be nonempty 2D nonnegative integer arrays")
    if before.shape != after.shape:
        raise ValueError("preview maps must share the same shape")
    view, before_lookup, after_lookup = _view_report(report, before.shape)
    height, width = before.shape
    longest = max(height, width)
    scale = min(longest, max_side)
    preview_shape = (max(1, height * scale // longest), max(1, width * scale // longest))
    view.update(
        {
            "title": title,
            "image": {"height": height, "width": width},
            "before": _preview(before, preview_shape, before_lookup),
            "after": _preview(after, preview_shape, after_lookup),
        }
    )
    if "review_gate" in report:
        try:
            gate = report["review_gate"]
            if any(kind not in _KINDS for key in ("fail_on", "triggered") for kind in gate[key]):
                raise ValueError("review gate contains an unrecognized change kind")
            view["review_gate"] = {key: list(gate[key]) for key in ("fail_on", "triggered")}
        except (KeyError, TypeError) as error:
            raise ValueError("review gate is missing required fields") from error
    payload = json.dumps(view, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    # A JSON script element is still parsed as HTML raw text. Escape its closing
    # tag characters rather than assuming application/json makes it safe.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    beginning, _, remainder = _PAGE.partition("__PAGE_TITLE__")
    middle, _, ending = remainder.partition("__COMPARISON_DATA__")
    return beginning + html.escape(title, quote=True) + middle + payload + ending


_PAGE = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta
      http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'unsafe-inline';
        style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    />
    <title>__PAGE_TITLE__</title>
    <style>
      :root {
        color-scheme: light;
        --ink: #192638;
        --muted: #596579;
        --line: #dde4ed;
        --accent: #5b42cb;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        font:
          15px/1.5 system-ui,
          sans-serif;
        color: var(--ink);
        background: #f3f5f9;
      }
      header {
        background: #192638;
        color: white;
        padding: 28px 5vw;
      }
      header p {
        margin: 5px 0;
        color: #cdd8e9;
      }
      .eyebrow {
        font-size: 12px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #c9bfff;
      }
      h1 {
        margin: 8px 0;
        font-size: clamp(25px, 4vw, 38px);
        line-height: 1.2;
      }
      main {
        max-width: 1400px;
        margin: auto;
        padding: 24px;
      }
      .notice {
        border-left: 4px solid #df9d24;
        background: #fff6df;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 20px;
      }
      .stats {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 20px;
      }
      .stat,
      .panel {
        background: white;
        border: 1px solid var(--line);
        border-radius: 12px;
      }
      .stat {
        padding: 16px;
      }
      .stat span {
        display: block;
        color: var(--muted);
        font-size: 12px;
      }
      .stat strong {
        display: block;
        font-size: 25px;
        margin: 3px 0;
      }
      .stat small {
        color: var(--muted);
      }
      .toolbar {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        margin: 14px 0;
      }
      button,
      select {
        font: inherit;
        border: 1px solid #bbc5d4;
        border-radius: 7px;
        background: white;
        color: var(--ink);
        padding: 7px 10px;
      }
      button {
        cursor: pointer;
      }
      button:hover {
        border-color: var(--accent);
      }
      button:disabled {
        opacity: 0.45;
        cursor: default;
      }
      .views {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      .panel {
        padding: 16px;
        min-width: 0;
      }
      .panel h2 {
        font-size: 17px;
        margin: 0 0 10px;
      }
      .stage {
        position: relative;
        background: #e4e8ee;
        border-radius: 7px;
        overflow: hidden;
        line-height: 0;
      }
      .stage canvas {
        display: block;
        width: 100%;
        height: auto;
        image-rendering: pixelated;
        cursor: crosshair;
      }
      .hair {
        position: absolute;
        pointer-events: none;
        display: none;
        background: rgba(255, 255, 255, 0.9);
        box-shadow: 0 0 0 1px rgba(25, 38, 56, 0.35);
      }
      .hair-x {
        height: 1px;
        width: 100%;
        left: 0;
      }
      .hair-y {
        width: 1px;
        height: 100%;
        top: 0;
      }
      .caption {
        font-size: 12px;
        color: var(--muted);
        margin: 8px 0 0;
      }
      .hover {
        min-height: 26px;
        margin: 10px 0;
        color: var(--muted);
      }
      .details {
        margin-top: 16px;
      }
      .details h2 {
        margin-bottom: 5px;
      }
      .details p {
        margin: 5px 0;
      }
      .detail-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 12px;
      }
      .detail-grid div {
        background: #f3f5f9;
        padding: 10px;
        border-radius: 6px;
      }
      .detail-grid span {
        display: block;
        color: var(--muted);
        font-size: 12px;
      }
      .detail-grid strong {
        font-size: 16px;
      }
      .table-panel {
        margin-top: 16px;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th {
        text-align: left;
        color: var(--muted);
        font-weight: 500;
        border-bottom: 1px solid var(--line);
        padding: 9px;
      }
      td {
        padding: 9px;
        border-bottom: 1px solid #edf0f5;
        vertical-align: top;
      }
      tr.group-row {
        cursor: pointer;
      }
      tr.group-row:hover {
        background: #f7f5ff;
      }
      tr.selected {
        background: #eee9ff;
      }
      .tag {
        display: inline-block;
        border-radius: 20px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
        background: #e9edf5;
        white-space: nowrap;
      }
      .tag.merge,
      .tag.disappeared {
        background: #fff0d7;
        color: #835411;
      }
      .tag.split,
      .tag.appeared {
        background: #e1f5ed;
        color: #19634b;
      }
      .tag.reorganized {
        background: #f3e2f1;
        color: #804175;
      }
      .ids {
        max-width: 240px;
        overflow-wrap: anywhere;
        font-variant-numeric: tabular-nums;
      }
      .page-info {
        margin-left: auto;
        color: var(--muted);
        font-size: 12px;
      }
      .definitions {
        margin-top: 16px;
      }
      .definitions dl {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 7px 14px;
        font-size: 13px;
      }
      .definitions dt {
        font-weight: 600;
      }
      .definitions dd {
        margin: 0;
        color: var(--muted);
      }
      footer {
        margin: 24px 0 5px;
        font-size: 12px;
        color: var(--muted);
      }
      .error {
        padding: 16px;
        color: #8b2828;
        background: #ffeded;
      }
      @media (max-width: 700px) {
        main {
          padding: 14px;
        }
        .stats {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .views {
          grid-template-columns: 1fr;
        }
        .detail-grid {
          grid-template-columns: 1fr 1fr;
        }
        .definitions dl {
          grid-template-columns: 1fr;
          gap: 3px;
        }
        .definitions dd {
          margin-bottom: 7px;
        }
      }
    </style>
  </head>
  <body>
    <header>
      <div class="eyebrow">PlanRegions · Local review</div>
      <h1 id="heading"></h1>
      <p>Trace where regions merge, split or disappear — and inspect the pixel flow.</p>
    </header>
    <main>
      <div class="notice">
        <strong>Preview ≠ full-resolution evidence.</strong> Previews use nearest-neighbor
        sampling, with at most 1024 pixels on either side. Tiny regions and one-pixel gaps may
        be invisible. Every count below comes from the full-resolution comparison. Changes are
        observations, not proof of a recognition error; the maps must already share the same
        pixel grid.
      </div>
      <div class="stats" id="stats"></div>
      <div class="toolbar">
        <label for="kind-filter">Show groups</label
        ><select id="kind-filter">
          <option value="all">All change kinds</option></select
        ><button id="clear-selection">Clear selection</button
        ><span class="page-info" id="map-size"></span>
      </div>
      <div class="views">
        <section class="panel">
          <h2>Before</h2>
          <div class="stage" id="before-stage">
            <canvas id="before-canvas" aria-label="Before region labels"></canvas>
            <div class="hair hair-x"></div>
            <div class="hair hair-y"></div>
          </div>
          <p class="caption">
            Background is gray. Click a region to select its correspondence group.
          </p>
        </section>
        <section class="panel">
          <h2>After</h2>
          <div class="stage" id="after-stage">
            <canvas id="after-canvas" aria-label="After region labels"></canvas>
            <div class="hair hair-x"></div>
            <div class="hair hair-y"></div>
          </div>
          <p class="caption">
            Matching groups share a color; numeric IDs are independent between maps.
          </p>
        </section>
      </div>
      <p class="hover" id="hover">Hover over either map to inspect sampled region IDs.</p>
      <section class="panel details" id="details" aria-live="polite">
        <h2>Inspect a correspondence group</h2>
        <p>Select a table row or click either map. All group counts are full resolution.</p>
      </section>
      <section class="panel table-panel">
        <h2>Correspondence groups</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Group</th>
                <th>Kind</th>
                <th>Before IDs</th>
                <th>After IDs</th>
                <th>Before / after area</th>
                <th>Shared overlap</th>
                <th>To / from background</th>
              </tr>
            </thead>
            <tbody id="groups-body"></tbody>
          </table>
        </div>
        <div class="toolbar">
          <button id="previous-page">Previous</button><button id="next-page">Next</button
          ><span class="page-info" id="page-info"></span>
        </div>
      </section>
      <section class="panel definitions">
        <h2>What the change kinds mean</h2>
        <dl id="definitions"></dl>
        <p class="caption">
          Any positive pixel overlap creates a correspondence edge. Background never joins
          groups. Coverage is shared foreground divided by the corresponding foreground area; it
          is not an accuracy score.
        </p>
      </section>
      <footer>
        Generated locally by PlanRegions. This page has no external assets or network requests.
        It embeds label previews, IDs and statistics; keep it private when the inputs are
        private.
      </footer>
      <noscript
        ><p class="error">
          Enable JavaScript to draw the embedded label previews and browse groups. The report
          requires no internet connection.
        </p></noscript
      >
    </main>
    <script id="comparison-data" type="application/json">
      __COMPARISON_DATA__
    </script>
    <script>
      (() => {
        "use strict";
        const data = JSON.parse(document.getElementById("comparison-data").textContent);
        const kinds = {
          unchanged:
            "One-to-one correspondence with identical pixel support, even if IDs changed.",
          reshaped: "One-to-one correspondence with pixels moving to or from background.",
          split: "One before region overlaps multiple after regions.",
          merge: "Multiple before regions overlap one after region.",
          reorganized:
            "Multiple before and after regions share one connected correspondence component.",
          appeared: "An after region has no positive overlap with a before region.",
          disappeared: "A before region has no positive overlap with an after region.",
        };
        const byId = new Map(data.groups.map((group) => [group.id, group]));
        const state = { kind: "all", selected: null, page: 0 };
        const pageSize = 50;
        const element = (id) => document.getElementById(id);
        const number = (value) => new Intl.NumberFormat("en").format(value);
        const percent = (shared, area) =>
          area ? ((100 * shared) / area).toFixed(2) + "%" : "—";
        const text = (tag, value, className) => {
          const node = document.createElement(tag);
          node.textContent = value;
          if (className) node.className = className;
          return node;
        };
        const values = {};
        const views = {};
        function decode(preview) {
          const binary = atob(preview.data);
          const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
          const packed = new DataView(bytes.buffer);
          const pixels = new Uint32Array(preview.width * preview.height);
          if (preview.encoding === "raw-u32le") {
            if (bytes.length !== pixels.length * 4) throw Error("Invalid preview length");
            for (let index = 0; index < pixels.length; index++)
              pixels[index] = packed.getUint32(index * 4, true);
          } else if (preview.encoding === "rle-u32le") {
            if (bytes.length % 8) throw Error("Invalid RLE preview length");
            let position = 0;
            for (let offset = 0; offset < bytes.length; offset += 8) {
              const length = packed.getUint32(offset, true),
                value = packed.getUint32(offset + 4, true);
              if (!length || position + length > pixels.length)
                throw Error("Invalid RLE preview run");
              pixels.fill(value, position, position + length);
              position += length;
            }
            if (position !== pixels.length) throw Error("Incomplete RLE preview");
          } else throw Error("Unknown preview encoding");
          if (pixels.some((index) => index >= preview.lookup.length))
            throw Error("Unknown preview label index");
          return pixels;
        }
        function palette(groupId) {
          const hue = (groupId * 0.61803398875) % 1;
          const sector = hue * 6,
            fraction = sector % 1,
            p = 0.32,
            q = 0.82 - fraction * 0.5,
            t = 0.32 + fraction * 0.5;
          const colors = [
            [0.82, t, p],
            [q, 0.82, p],
            [p, 0.82, t],
            [p, q, 0.82],
            [t, p, 0.82],
            [0.82, p, q],
          ];
          return colors[Math.floor(sector)].map((value) => Math.round(value * 255));
        }
        function draw() {
          for (const side of ["before", "after"]) {
            const preview = data[side],
              view = views[side];
            const colors = preview.lookup.map((label) => {
              if (label.id === "0") return [225, 230, 237];
              const group = byId.get(label.group);
              if (
                (state.kind !== "all" && group.kind !== state.kind) ||
                (state.selected !== null && group.id !== state.selected)
              )
                return [236, 237, 242];
              return palette(group.id);
            });
            const bitmap = view.context.createImageData(preview.width, preview.height);
            for (let index = 0; index < values[side].length; index++) {
              const color = colors[values[side][index]],
                offset = index * 4;
              bitmap.data[offset] = color[0];
              bitmap.data[offset + 1] = color[1];
              bitmap.data[offset + 2] = color[2];
              bitmap.data[offset + 3] = 255;
            }
            view.context.putImageData(bitmap, 0, 0);
          }
        }
        function showDetails() {
          const panel = element("details");
          panel.replaceChildren();
          const group = byId.get(state.selected);
          if (!group) {
            panel.append(
              text("h2", "Inspect a correspondence group"),
              text(
                "p",
                "Select a table row or click either map. All group counts are full resolution.",
              ),
            );
            return;
          }
          panel.append(
            text("h2", "Group " + group.id + " · " + group.kind),
            text("p", kinds[group.kind]),
            text("p", "Before IDs: " + (group.before_ids.join(", ") || "none"), "ids"),
            text("p", "After IDs: " + (group.after_ids.join(", ") || "none"), "ids"),
          );
          const grid = document.createElement("div");
          grid.className = "detail-grid";
          const metrics = [
            [
              "Before / after area",
              number(group.before_area_px) + " / " + number(group.after_area_px) + " px",
            ],
            ["Shared positive overlap", number(group.overlap_px) + " px"],
            [
              "Before / after coverage",
              percent(group.overlap_px, group.before_area_px) +
                " / " +
                percent(group.overlap_px, group.after_area_px),
            ],
            ["To background", number(group.to_background_px) + " px"],
            ["From background", number(group.from_background_px) + " px"],
            [
              "Correspondence",
              group.before_ids.length + " → " + group.after_ids.length + " regions",
            ],
          ];
          for (const [label, value] of metrics) {
            const item = document.createElement("div");
            item.append(text("span", label), text("strong", value));
            grid.append(item);
          }
          panel.append(grid);
        }
        function table() {
          const filtered = data.groups.filter(
            (group) => state.kind === "all" || group.kind === state.kind,
          );
          const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
          state.page = Math.min(state.page, pages - 1);
          const body = element("groups-body");
          body.replaceChildren();
          for (const group of filtered.slice(
            state.page * pageSize,
            (state.page + 1) * pageSize,
          )) {
            const row = document.createElement("tr");
            row.className = "group-row" + (group.id === state.selected ? " selected" : "");
            row.tabIndex = 0;
            row.setAttribute("aria-label", "Select group " + group.id + ", " + group.kind);
            row.append(text("td", group.id));
            const kind = document.createElement("td");
            kind.append(text("span", group.kind, "tag " + group.kind));
            row.append(kind);
            for (const ids of [group.before_ids, group.after_ids]) {
              const shown =
                ids.slice(0, 8).join(", ") +
                (ids.length > 8 ? " … (" + ids.length + " IDs)" : "");
              row.append(text("td", shown || "—", "ids"));
            }
            row.append(
              text(
                "td",
                number(group.before_area_px) + " / " + number(group.after_area_px) + " px",
              ),
              text("td", number(group.overlap_px) + " px"),
              text(
                "td",
                number(group.to_background_px) +
                  " / " +
                  number(group.from_background_px) +
                  " px",
              ),
            );
            row.addEventListener("click", () => select(group.id));
            row.addEventListener("keydown", (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                select(group.id);
              }
            });
            body.append(row);
          }
          if (!filtered.length) {
            const row = document.createElement("tr"),
              cell = text("td", "No groups of this kind.");
            cell.colSpan = 7;
            row.append(cell);
            body.append(row);
          }
          element("previous-page").disabled = state.page === 0;
          element("next-page").disabled = state.page === pages - 1;
          element("page-info").textContent =
            number(filtered.length) + " groups · page " + (state.page + 1) + " / " + pages;
        }
        function select(groupId) {
          state.selected = groupId;
          const group = byId.get(groupId);
          if (group && state.kind !== "all" && state.kind !== group.kind) {
            state.kind = "all";
            element("kind-filter").value = "all";
            state.page = 0;
          }
          draw();
          showDetails();
          table();
        }
        function pointer(event, side) {
          const bounds = views[side].canvas.getBoundingClientRect(),
            preview = data[side];
          return {
            x: Math.max(
              0,
              Math.min(
                preview.width - 1,
                Math.floor(((event.clientX - bounds.left) * preview.width) / bounds.width),
              ),
            ),
            y: Math.max(
              0,
              Math.min(
                preview.height - 1,
                Math.floor(((event.clientY - bounds.top) * preview.height) / bounds.height),
              ),
            ),
          };
        }
        function hover(event, side) {
          const point = pointer(event, side),
            labels = {};
          for (const name of ["before", "after"]) {
            const preview = data[name];
            labels[name] = preview.lookup[values[name][point.y * preview.width + point.x]];
            const stage = element(name + "-stage"),
              horizontal = stage.querySelector(".hair-x"),
              vertical = stage.querySelector(".hair-y");
            horizontal.style.top = ((point.y + 0.5) * 100) / preview.height + "%";
            vertical.style.left = ((point.x + 0.5) * 100) / preview.width + "%";
            horizontal.style.display = "block";
            vertical.style.display = "block";
          }
          const sourceX = Math.floor(
              ((2 * point.x + 1) * data.image.width) / (2 * data[side].width),
            ),
            sourceY = Math.floor(
              ((2 * point.y + 1) * data.image.height) / (2 * data[side].height),
            );
          element("hover").textContent =
            "Sampled source pixel (x=" +
            sourceX +
            ", y=" +
            sourceY +
            "): before ID " +
            labels.before.id +
            " · after ID " +
            labels.after.id +
            ". Gray ID 0 means background.";
          return labels[side];
        }
        try {
          element("heading").textContent = data.title;
          const summary = data.summary;
          const metrics = [
            [
              "Regions",
              number(summary.before_region_count) + " → " + number(summary.after_region_count),
              "before → after",
            ],
            [
              "Shared foreground",
              number(summary.shared_foreground_px) + " px",
              percent(summary.shared_foreground_px, summary.before_foreground_px) +
                " before / " +
                percent(summary.shared_foreground_px, summary.after_foreground_px) +
                " after coverage",
            ],
            [
              "To background",
              number(summary.to_background_px) + " px",
              "positive before → zero after",
            ],
            [
              "From background",
              number(summary.from_background_px) + " px",
              "zero before → positive after",
            ],
          ];
          for (const [label, value, note] of metrics) {
            const card = document.createElement("div");
            card.className = "stat";
            card.append(text("span", label), text("strong", value), text("small", note));
            element("stats").append(card);
          }
          element("map-size").textContent =
            data.image.width +
            " × " +
            data.image.height +
            " original · " +
            data.before.width +
            " × " +
            data.before.height +
            " preview";
          for (const [kind, description] of Object.entries(kinds)) {
            const option = text("option", kind + " (" + summary.group_counts[kind] + ")");
            option.value = kind;
            element("kind-filter").append(option);
            element("definitions").append(text("dt", kind), text("dd", description));
          }
          if (data.review_gate) {
            const gate = data.review_gate.triggered.length
              ? "Review gate triggered: " + data.review_gate.triggered.join(", ")
              : "Review gate: no selected change kinds triggered.";
            element("definitions").append(text("dt", "Review gate"), text("dd", gate));
          }
          for (const side of ["before", "after"]) {
            values[side] = decode(data[side]);
            const canvas = element(side + "-canvas");
            canvas.width = data[side].width;
            canvas.height = data[side].height;
            views[side] = { canvas, context: canvas.getContext("2d") };
            canvas.addEventListener("mousemove", (event) => hover(event, side));
            canvas.addEventListener("click", (event) => select(hover(event, side).group));
            canvas.addEventListener("mouseleave", () => {
              for (const hair of document.querySelectorAll(".hair"))
                hair.style.display = "none";
            });
          }
          element("kind-filter").addEventListener("change", (event) => {
            state.kind = event.target.value;
            state.selected = null;
            state.page = 0;
            draw();
            showDetails();
            table();
          });
          element("clear-selection").addEventListener("click", () => select(null));
          element("previous-page").addEventListener("click", () => {
            state.page--;
            table();
          });
          element("next-page").addEventListener("click", () => {
            state.page++;
            table();
          });
          draw();
          table();
        } catch (error) {
          const warning = text(
            "p",
            "Unable to display this comparison: " + error.message,
            "error",
          );
          document.querySelector("main").prepend(warning);
        }
      })();
    </script>
  </body>
</html>
"""
