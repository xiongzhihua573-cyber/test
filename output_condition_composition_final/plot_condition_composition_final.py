#!/usr/bin/env python3
"""Final four-panel annual 100% stacked bars from saved verified data.

Run: python plot_condition_composition_final.py
  or: python plot_condition_composition_final.py --data path/to/condition_composition_by_year.csv --config path/to/scenario_selection.json --output path/to/export

Uses existing statistics and archived annual action counts only. No fitting,
optimization, state replay, schedule adjustment, or scientific-data mutation.
Default inputs: adjacent input_data/ when packaged, otherwise the existing
sibling output_condition_composition/ directory. All 15 annual bars are drawn;
six selected year labels keep the figure readable at an 18 cm print width.
PDF contains vector bars and embedded Type 3 vector glyph outlines. The actual
PDF is rendered by MuPDF and checked against the PNG for Chinese label ink.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import tempfile
from typing import Any

# Cloud workspaces may have a read-only user home. Respect user overrides and
# otherwise keep only disposable font/render caches under the system temp dir.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "condition_composition_mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "condition_composition_cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch
from matplotlib.text import Text
from matplotlib.ticker import FixedLocator, FuncFormatter
import numpy as np
import pandas as pd
from PIL import Image
import fitz

HERE = Path(__file__).resolve().parent
YEARS = np.arange(2025, 2040, dtype=int)
GRADES = np.arange(1, 6, dtype=int)
COLORS = ["#277DA1", "#76B7B2", "#E9C46A", "#E58F55", "#B75D69"]
GRADE_LABELS = ["1类 90＜S≤100", "2类 75＜S≤90", "3类 60＜S≤75", "4类 40＜S≤60", "5类 0≤S≤40"]
CANVAS_CM = (18.0, 14.1)
DPI = 600
INK = "#293B49"
MUTED = "#63727D"
GRID = "#E3E8EC"
ACTIONS = "#546F80"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_fonts() -> dict[str, str]:
    latin = font_manager.findfont(FontProperties(family="Nimbus Roman"), fallback_to_default=True)
    try:
        chinese = font_manager.findfont(FontProperties(family="Noto Sans CJK SC"), fallback_to_default=False)
    except ValueError:
        # Matplotlib normally indexes only the first (JP) face of Noto's TTC.
        # Extract the installed SC face unchanged; this changes no font outlines.
        from fontTools.ttLib import TTCollection
        candidates = [Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")]
        collection_path = next((path for path in candidates if path.exists()), None)
        if collection_path is None:
            raise RuntimeError("Chinese font unavailable: install fonts-noto-cjk before drawing.")
        font_dir = Path(os.environ["MPLCONFIGDIR"]) / "extracted_fonts"
        font_dir.mkdir(parents=True, exist_ok=True)
        extracted = font_dir / "NotoSansCJKSC-Regular.otf"
        if not extracted.exists():
            collection = TTCollection(collection_path)
            selected = next((font for font in collection.fonts
                             if font["name"].getDebugName(1) == "Noto Sans CJK SC"), None)
            if selected is None:
                raise RuntimeError("Installed Noto CJK collection has no Simplified Chinese face.")
            selected.save(extracted)
            collection.close()
        font_manager.fontManager.addfont(str(extracted))
        chinese = str(extracted)
    chinese_name = FontProperties(fname=chinese).get_name()
    if "CJK" not in chinese_name:
        raise RuntimeError("Chinese font unavailable: install fonts-noto-cjk before drawing.")
    plt.rcParams.update({
        "font.family": ["Nimbus Roman", "Noto Sans CJK SC", "DejaVu Sans"],
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 8.7,
        "axes.linewidth": 0.55,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.labelsize": 7.7,
        "ytick.labelsize": 7.7,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        # CJK SC is CFF/OpenType. PDF Type 42 CID embedding can corrupt its
        # glyph mapping in viewers; Type 3 embeds the actual vector outlines.
        "pdf.fonttype": 3,
        "ps.fonttype": 42,
        "svg.fonttype": "path",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "text.color": INK,
        "mathtext.fontset": "stix",
        "axes.unicode_minus": True,
    })
    return {"latin": latin, "chinese": chinese}


def read_inputs(data_path: Path, config_path: Path):
    frame = pd.read_csv(data_path, float_precision="round_trip")
    expected = {"scenario", "B", "year", "grade", "count", "percentage", "maintenance_actions"}
    if not expected.issubset(frame.columns):
        raise ValueError(f"CSV missing columns: {sorted(expected - set(frame.columns))}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 4:
        raise ValueError("scenario_selection.json must have four ordered entries in 'scenarios'.")
    n_units = int(config["n_units"])
    if n_units != 59:
        raise ValueError("This figure requires exactly 59 detection units.")
    if len(frame) != 300:
        raise ValueError("Expected 4 scenarios × 15 years × 5 grades = 300 rows.")
    ids = [str(item["scenario"]) for item in scenarios]
    if ids != ["no_maintenance", "low_resource", "medium_resource", "high_resource"]:
        raise ValueError("The manifest must order no-, low-, medium- and high-resource scenarios.")
    if (config["initial_condition"] != "LOCF" or config["initial_state_year"] != 2024
            or config["years"] != YEARS.tolist() or float(config["d"]) != 0.65
            or float(config["R"]) != 6.0 or int(config["capacity"]) != 8):
        raise ValueError("Manifest parameters differ from the common final 15-year scenario.")
    if set(frame.scenario.astype(str)) != set(ids):
        raise ValueError("CSV scenarios differ from the scenario-selection manifest.")
    if frame.duplicated(["scenario", "year", "grade"]).any():
        raise ValueError("Duplicated scenario/year/grade rows.")
    if frame[list(expected - {"scenario"})].isna().any().any():
        raise ValueError("Missing numeric composition data.")
    records = []
    for scenario in scenarios:
        sid = str(scenario["scenario"])
        if (scenario["initial_condition"] != config["initial_condition"]
                or float(scenario["d"]) != float(config["d"])
                or float(scenario["R"]) != float(config["R"])
                or int(scenario["planning_horizon"]) != 15
                or int(scenario["start_year"]) != YEARS[0]
                or int(scenario["end_year"]) != YEARS[-1]):
            raise ValueError(f"{sid}: common scenario parameters differ.")
        subset = frame[frame.scenario.astype(str) == sid].copy()
        if set(subset.year) != set(YEARS) or set(subset.grade) != set(GRADES):
            raise ValueError(f"{sid}: incorrect years or grades.")
        count = subset.pivot(index="year", columns="grade", values="count").loc[YEARS, GRADES].to_numpy(float)
        percentage = subset.pivot(index="year", columns="grade", values="percentage").loc[YEARS, GRADES].to_numpy(float)
        if not np.allclose(count, np.round(count), atol=1e-12) or np.any(count < 0):
            raise ValueError(f"{sid}: counts must be non-negative integers.")
        if not np.all(count.sum(axis=1) == n_units):
            raise ValueError(f"{sid}: grade counts do not total 59 every year.")
        if not np.allclose(percentage, count / n_units * 100, atol=1e-8, rtol=0):
            raise ValueError(f"{sid}: percentages do not match count / 59 × 100.")
        if not np.allclose(percentage.sum(axis=1), 100, atol=1e-8, rtol=0):
            raise ValueError(f"{sid}: grade percentages do not total 100%.")
        grouped = subset.groupby("year").maintenance_actions
        if not (grouped.nunique() == 1).all():
            raise ValueError(f"{sid}: repeated per-grade maintenance action counts are inconsistent.")
        action_count = grouped.first().loc[YEARS].to_numpy(float)
        if np.any(action_count < 0) or not np.allclose(action_count, np.round(action_count)):
            raise ValueError(f"{sid}: action counts must be non-negative integers.")
        if np.any(action_count > 8):
            raise ValueError(f"{sid}: action count exceeds the common annual capacity of eight.")
        if not np.array_equal(action_count, np.asarray(scenario["annual_actions"], dtype=int)):
            raise ValueError(f"{sid}: action counts differ from the archived-plan manifest.")
        if not np.allclose(subset.B.to_numpy(float), float(scenario["B"]), atol=1e-10, rtol=0):
            raise ValueError(f"{sid}: resource B differs from the selection manifest.")
        records.append({
            "id": sid, "label": str(scenario["scenario_zh"]), "B": float(scenario["B"]),
            "counts": count.astype(int), "percentage": percentage,
            "maintenance_actions": action_count.astype(int),
        })
    return frame, config, records


def use_cjk_font(fig, font_path: str):
    for obj in fig.findobj(match=Text):
        if re.search(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", obj.get_text()):
            obj.set_fontproperties(FontProperties(fname=font_path, size=obj.get_fontsize()))


def check_text_bounds(fig) -> list[dict[str, Any]]:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    outside = []
    for obj in fig.findobj(match=Text):
        if not obj.get_visible() or not obj.get_text().strip():
            continue
        bounds = obj.get_window_extent(renderer)
        if bounds.width <= 0 or bounds.height <= 0:
            continue
        if bounds.x0 < -0.5 or bounds.y0 < -0.5 or bounds.x1 > canvas.width + 0.5 or bounds.y1 > canvas.height + 0.5:
            outside.append({"text": obj.get_text(), "bounds_px": [float(v) for v in bounds.extents]})
    return outside


MAJOR_YEARS = np.array([2025, 2028, 2031, 2034, 2037, 2039], dtype=int)
PANEL_LABELS = ["无养护", "低资源", "中等资源", "高资源"]


def style_composition_axis(ax):
    ax.set_xlim(2024.45, 2039.55)
    ax.set_ylim(0, 100)
    ax.set_xticks(MAJOR_YEARS)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0f}"))
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    ax.tick_params(axis="y", pad=2)
    ax.grid(axis="y", color=GRID, linewidth=0.38, zorder=4)
    ax.set_axisbelow(False)
    ax.set_ylabel("检测单元占比（%）", labelpad=4.2)
    for name in ["top", "right"]:
        ax.spines[name].set_visible(False)
    ax.spines["bottom"].set_color("#9AABB5")
    ax.spines["bottom"].set_linewidth(0.4)


def draw_actions(ax, record, no_maintenance=False):
    ax.set_xlim(2024.45, 2039.55)
    ax.set_ylim(0, 8)
    ax.set_xticks(MAJOR_YEARS)
    ax.set_xticklabels([str(year) for year in MAJOR_YEARS], fontsize=7.7)
    ax.tick_params(axis="x", pad=3.1, length=2.2)
    if no_maintenance:
        if np.any(record["maintenance_actions"] != 0):
            raise ValueError("The no-maintenance baseline contains nonzero actions.")
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
    else:
        ax.bar(YEARS, record["maintenance_actions"], width=0.76,
               color=ACTIONS, edgecolor="none", linewidth=0, zorder=3)
        ax.set_yticks([0, 4, 8])
        ax.tick_params(axis="y", labelsize=6.7, pad=2, length=2)
        ax.set_ylabel("养护次数\n（次/年）", labelpad=8.0, fontsize=6.5,
                      rotation=0, ha="right", va="center")
        ax.grid(axis="y", color=GRID, linewidth=0.35, zorder=0)
    for name in ["top", "right"]:
        ax.spines[name].set_visible(False)
    ax.spines["bottom"].set_color("#9AABB5")
    ax.spines["bottom"].set_linewidth(0.45)


def draw_final(records, fonts, displayed_grades):
    fig = plt.figure(figsize=tuple(value / 2.54 for value in CANVAS_CM), dpi=144)
    labels = [GRADE_LABELS[g - 1] for g in displayed_grades]
    handles = [Patch(facecolor=COLORS[g - 1], edgecolor="none", label=label)
               for g, label in zip(displayed_grades, labels)]
    legend = fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.994),
                       ncol=len(displayed_grades), frameon=False, handlelength=1.15,
                       handleheight=0.85, handletextpad=0.45, columnspacing=2.0,
                       fontsize=8.0, borderaxespad=0.0)
    axes = []
    for index, record in enumerate(records):
        row, col = divmod(index, 2)
        left = 0.092 + col * 0.488
        bottom = 0.615 - row * 0.474
        ax = fig.add_axes([left, bottom, 0.400, 0.269])
        style_composition_axis(ax)
        lower = np.zeros(len(YEARS))
        for grade in GRADES:
            values = record["percentage"][:, grade - 1]
            ax.bar(YEARS, values, bottom=lower, width=0.76,
                   facecolor=COLORS[grade - 1], edgecolor="white", linewidth=0.25, zorder=2)
            lower += values
        fig.text(left, bottom + 0.307, f"({chr(97 + index)}) {PANEL_LABELS[index]}",
                 ha="left", va="bottom", fontsize=9.0)
        if index:
            fig.text(left, bottom + 0.279, f"B = {record['B']:.3f}",
                     ha="left", va="bottom", fontsize=7.6, color=MUTED)
        action_ax = fig.add_axes([left, bottom - 0.078, 0.400, 0.052])
        draw_actions(action_ax, record, no_maintenance=index == 0)
        if row:
            action_ax.set_xlabel("年份", labelpad=3.5, fontsize=7.5)
        axes.extend([ax, action_ax])
    use_cjk_font(fig, fonts["chinese"])
    return fig, axes, legend


def inspect_export(path: Path) -> dict[str, Any]:
    result = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
    if path.suffix.lower() in {".png", ".tif", ".tiff"}:
        with Image.open(path) as raster:
            result.update({"size_px": list(raster.size), "dpi": [float(v) for v in raster.info.get("dpi", [])],
                           "mode": raster.mode, "compression": raster.info.get("compression")})
            if raster.info.get("dpi") and min(raster.info["dpi"]) < 599.9:
                raise RuntimeError(f"{path.name}: raster resolution below 600 dpi.")
            if path.suffix.lower() in {".tif", ".tiff"} and raster.info.get("compression") != "tiff_lzw":
                raise RuntimeError(f"{path.name}: TIFF does not use LZW compression.")
    elif path.suffix.lower() == ".pdf":
        with fitz.open(path) as document:
            page = document[0]
            fonts = []
            for item in page.get_fonts(full=True):
                xref, extension, font_type, base_font, resource_name, encoding, referencer = item
                embedded = bool(document.extract_font(xref)[3]) if xref else False
                if font_type == "Type3" and xref:
                    key_type, key_value = document.xref_get_key(xref, "CharProcs")
                    procedures = (document.xref_object(int(key_value.split()[0])) if key_type == "xref"
                                  else key_value if key_type == "dict" else "")
                    glyph_xrefs = [int(value) for value in re.findall(r"/\S+\s+(\d+)\s+0\s+R", procedures)]
                    embedded = bool(glyph_xrefs) and all(document.xref_is_stream(value)
                                                       and bool(document.xref_stream(value))
                                                       for value in glyph_xrefs)
                fonts.append({"name": base_font, "type": font_type, "extension": extension, "embedded": embedded})
            result.update({"pages": len(document), "size_points": [page.rect.width, page.rect.height],
                           "raster_image_count": len(page.get_images(full=True)),
                           "vector_drawing_count": len(page.get_drawings()), "fonts": fonts,
                           "text_extractable": bool(page.get_text().strip())})
            if len(document) != 1 or page.get_images(full=True) or not page.get_drawings():
                raise RuntimeError(f"{path.name}: expected a one-page vector PDF without raster images.")
            if not all(item["embedded"] for item in fonts):
                raise RuntimeError(f"{path.name}: some font outlines are not embedded.")
            preview_dir = path.parent / "validation"
            preview_dir.mkdir(exist_ok=True)
            preview_path = preview_dir / "condition_composition_final_pdf_preview.png"
            page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(preview_path)
            rendered = Image.open(preview_path).convert("RGB")
            with Image.open(path.with_suffix(".png")) as source_png:
                reference = source_png.convert("RGB").resize(rendered.size, Image.Resampling.LANCZOS)
            width, height = rendered.size
            region_checks = []
            # Panel header regions isolate Chinese glyphs; no scientific bar pixels
            # can conceal failed font rendering in these checks.
            for label, box in [
                ("a_header", (.085, .047, .49, .079)),
                ("b_header", (.573, .047, .98, .079)),
                ("c_header", (.085, .521, .49, .553)),
                ("d_header", (.573, .521, .98, .553)),
                ("shared_legend", (.10, .003, .90, .035)),
            ]:
                pixel_box = tuple(round(value * (width if i % 2 == 0 else height)) for i, value in enumerate(box))
                pdf_ink = int(np.count_nonzero(np.asarray(rendered.crop(pixel_box).convert("L")) < 180))
                png_ink = int(np.count_nonzero(np.asarray(reference.crop(pixel_box).convert("L")) < 180))
                ratio = pdf_ink / max(1, png_ink)
                region_checks.append({"region": label, "dark_pixels_pdf": pdf_ink,
                                      "dark_pixels_png": png_ink, "ratio_pdf_to_png": ratio,
                                      "consistent": 0.80 <= ratio <= 1.20})
            result["actual_pdf_render_check"] = {
                "preview_file": str(preview_path.relative_to(path.parent)),
                "render_resolution_dpi": 144, "label_ink_checks": region_checks,
                "all_consistent": all(item["consistent"] for item in region_checks),
                "cjk_encoding": "Embedded Type3 vector glyph outlines, not CFF Type42 CID mapping.",
            }
            if not all(item["consistent"] for item in region_checks):
                raise RuntimeError(f"{path.name}: PDF glyph ink differs materially from PNG; inspect label regions.")
    return result


def default_input(name: str) -> Path:
    packaged = HERE / "input_data" / name
    return packaged if packaged.is_file() else HERE.parent / "output_condition_composition" / name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=default_input("condition_composition_by_year.csv"))
    parser.add_argument("--config", type=Path, default=default_input("scenario_selection.json"))
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args(argv)
    data_path, config_path, output = args.data.resolve(), args.config.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    before = {str(path): sha256(path) for path in (data_path, config_path)}
    fonts = configure_fonts()
    _, config, records = read_inputs(data_path, config_path)
    observed = [grade for grade in GRADES if any(np.any(r["counts"][:, grade - 1] > 0) for r in records)]
    displayed_grades = [int(grade) for grade in observed]
    fig, axes, _ = draw_final(records, fonts, displayed_grades)
    clipped = check_text_bounds(fig)
    if clipped:
        raise RuntimeError(f"Text extends beyond canvas: {clipped}")
    files = []
    for extension in ("png", "pdf", "tif"):
        path = output / f"condition_composition_final.{extension}"
        kwargs = {"pil_kwargs": {"compression": "tiff_lzw"}} if extension == "tif" else {}
        fig.savefig(path, dpi=DPI, transparent=False, **kwargs)
        files.append(inspect_export(path))
    audit = {
        "data_sources": before, "canvas_cm": CANVAS_CM, "raster_dpi": DPI, "fonts": fonts,
        "colors_by_grade": {str(i + 1): c for i, c in enumerate(COLORS)},
        "years": YEARS.tolist(), "major_year_labels": MAJOR_YEARS.tolist(),
        "annual_bars_per_panel": len(YEARS), "grade_order_bottom_to_top": GRADES.tolist(),
        "legend_grades": displayed_grades, "omitted_legend_grades_always_zero": [int(g) for g in GRADES if g not in observed],
        "scenario_order": [r["id"] for r in records],
        "common_parameters": {key: config[key] for key in
                              ["initial_condition", "initial_state_year", "n_units", "years", "d", "R",
                               "capacity", "min_gap", "max_actions_per_unit", "required_units_above75"]},
        "plot_data": [{k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in r.items()} for r in records],
        "composition_axis_limits": [[*ax.get_xlim(), *ax.get_ylim()] for ax in axes[::2]],
        "action_axis_limits": [[*ax.get_xlim(), *ax.get_ylim()] for ax in axes[1::2]],
        "composition_axis_bounds_fraction": [list(ax.get_position().bounds) for ax in axes[::2]],
        "action_axis_bounds_fraction": [list(ax.get_position().bounds) for ax in axes[1::2]],
        "composition_bar_width_years": 0.76, "action_bar_width_years": 0.76,
        "annual_action_number_annotations": False, "no_maintenance_action_marks": False,
        "printed_resource_B": {r["id"]: None if i == 0 else f"{r['B']:.3f}" for i, r in enumerate(records)},
        "all_text_within_canvas": True, "files": files,
        "independent_figure_only": True, "existing_manuscript_modified": False,
        "scientific_models_fitted": 0, "optimization_searches_run": 0, "state_replays_run": 0,
    }
    plt.close(fig)
    after = {str(path): sha256(path) for path in (data_path, config_path)}
    audit["inputs_unchanged"] = before == after
    if before != after:
        raise RuntimeError("Original plot inputs changed during export.")
    (output / "validation").mkdir(exist_ok=True)
    audit_path = output / "validation" / "plot_final_export_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported final PNG, vector PDF and 600 dpi LZW TIFF; audit: {audit_path}")


if __name__ == "__main__":
    main()
