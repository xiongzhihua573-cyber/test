"""Final visual refinement of Figures 1–3 using frozen original plot inputs.

The Chinese/English display strings share the same data and figure construction.
All published model error statistics are read from the frozen comparison CSV.
"""
from pathlib import Path
import hashlib
import json
import argparse
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/fig16_mpl')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import figure17_style as style
from figure17_style import t, COLORS, panel, grid, figsize

AUDIT = {'scope': 'figures only; no model, optimization, or published-statistic recalculation',
         'source_files': {}, 'figures': {},
         'reference_plotter': 'final_results_stage8/scripts/plot_small_paper.py:figure1/figure2/figure3'}
FROZEN_SHA256 = {
    'yearly_observation_count.csv': 'cd9d8fd9ba89d04772c88c32dfcfad61dee19130fd9a769f12933b95d545af6e',
    'observations_long.csv': '5fc5468a9444b7dd9e79d67846c59353607cd5123a2a48d022662eb14d1eec6d',
    'continuous_predictions.csv': '5490875cce76d6d4e5f444268443ea15105e69108da15b8b1f8eb9667aa2401f',
    'continuous_model_comparison.csv': 'a58208b77a7f28ab15ee5260b2d77799981a2de4183b391c05d0156dfdccc769',
    'initial_state_2024.csv': 'dbb09638cdaeb3b162aef6fed5c33422e8dfb384f74023f007906ec06e3c392b',
}


def _read(name):
    path = style.SOURCE / name
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual_hash == FROZEN_SHA256[name], (name, 'frozen original changed')
    AUDIT['source_files'][name] = {'sha256': actual_hash,
                                  'relative_path': 'source_data/' + name,
                                  'exact_original_frozen_file': actual_hash == FROZEN_SHA256[name]}
    return pd.read_csv(path)


def _array(values):
    array = np.asarray(values)
    digest_array = np.ascontiguousarray(array.astype('<f8'))
    return {'shape': list(array.shape), 'sha256_float64_le': hashlib.sha256(digest_array.tobytes()).hexdigest(),
            'values': array.tolist()}


def _same(actual, original):
    return bool(np.array_equal(np.asarray(actual), np.asarray(original), equal_nan=True))


def _finish(fig, number, record):
    record.update(style.save(fig, number))
    record['all_input_arrays_match_original'] = all(record['checks'].values())
    assert record['all_input_arrays_match_original'], (number, record['checks'])
    assert not record['clipped_text'], (number, record['clipped_text'])
    AUDIT['figures'][str(number)] = record
    plt.close(fig)
    return record


def figure1():
    """Annual overview above two exactly aligned 59×13 tiled observation matrices."""
    yearly = _read('yearly_observation_count.csv')
    obs = _read('observations_long.csv')
    units = sorted(obs.unit_id.unique())
    years = np.sort(obs.year.unique())
    assert len(units) == 59 and len(years) == 13
    fig = plt.figure(figsize=figsize(1))
    gs = fig.add_gridspec(2, 2, height_ratios=[.56, 2.44],
                         left=.104, right=.979, bottom=.158, top=.915,
                         hspace=.37, wspace=.285)
    ax = fig.add_subplot(gs[0, :])
    lines = []
    for col, name, color, marker, ls in [
        ('whole_valid', t('全桥评分', 'Whole-bridge score'), COLORS['LOCF'], 'o', '-'),
        ('super_valid', t('上部结构评分', 'Superstructure score'), COLORS['Ridge'], 's', '--')]:
        line, = ax.plot(yearly.year, yearly[col], color=color, marker=marker,
                       linestyle=ls, linewidth=1.05,
                       markerfacecolor='white' if marker == 'o' else color,
                       markersize=4.0 if marker == 'o' else 2.9,
                       markeredgewidth=.75, label=name, zorder=3)
        lines.append(line)
    ax.set(xlim=(2011.6, 2024.4), ylim=(-1, 65), xticks=years,
           yticks=[0, 20, 40, 60], ylabel=t('观测数（条）', 'Observations'))
    ax.tick_params(axis='x', labelsize=7.4)
    panel(ax, 'a', t('年度检测覆盖', 'Annual inspection coverage'))
    ax.legend(loc='lower right', bbox_to_anchor=(1, 1.05), ncol=2,
              columnspacing=1.6, borderaxespad=0, handlelength=2.3, fontsize=7.3)
    grid(ax)
    records, checks = {}, {}
    for index, (col, title, color) in enumerate([
        ('whole_score', t('全桥评分', 'Whole-bridge score'), COLORS['LOCF']),
        ('super_score', t('上部结构评分', 'Superstructure score'), COLORS['Ridge'])]):
        ax = fig.add_subplot(gs[1, index])
        original = obs.pivot(index='unit_id', columns='year', values=col).reindex(
            index=units, columns=years).notna().to_numpy()
        mesh = ax.pcolormesh(np.arange(14)-.5, np.arange(60)-.5,
                            original.astype(int), cmap=ListedColormap([COLORS['missing'], color]),
                            vmin=0, vmax=1, shading='flat',
                            edgecolors='white', linewidth=.13, antialiased=True,
                            rasterized=False)
        ax.set(xlim=(-.5, 12.5), ylim=(58.5, -.5), xlabel=t('年份（年）', 'Year'),
               ylabel=t('检测单元', 'Inspection unit'))
        ax.set_xticks(np.arange(13), years, rotation=45, ha='right', rotation_mode='anchor')
        ax.tick_params(axis='x', labelsize=7.1, length=0, pad=3)
        ticks = np.arange(0, 59, 5)
        ax.set_yticks(ticks, np.array(units)[ticks])
        ax.tick_params(axis='y', labelsize=7.3, length=0, pad=3)
        for spine in ax.spines.values():
            spine.set_visible(False)
        panel(ax, chr(98+index), title)
        plotted = np.asarray(mesh.get_array()).reshape(original.shape)
        checks[f'{col}_tiles_equal_original_imshow_matrix'] = _same(plotted, original)
        records[col] = _array(original.astype(int))
        records[col]['observed_count'] = int(original.sum())
    for index, col in enumerate(['whole_valid', 'super_valid']):
        checks[col + '_line_xy_equal_frozen_csv'] = _same(
            np.column_stack(lines[index].get_data()), yearly[['year', col]].to_numpy())
    checks['whole_total_387'] = records['whole_score']['observed_count'] == 387
    checks['super_total_380'] = records['super_score']['observed_count'] == 380
    fig.legend(handles=[Patch(facecolor=COLORS['missing'], edgecolor='none', label=t('缺测', 'Missing')),
                        Patch(facecolor=COLORS['LOCF'], edgecolor='none', label=t('全桥观测', 'Whole bridge observed')),
                        Patch(facecolor=COLORS['Ridge'], edgecolor='none', label=t('上部结构观测', 'Superstructure observed'))],
               ncol=3, loc='lower center', bbox_to_anchor=(.54, -.008),
               handlelength=1.0, handletextpad=.5, columnspacing=1.5, fontsize=7.0)
    return _finish(fig, 1, {'checks': checks, 'arrays': records,
        'annual_coverage': _array(yearly[['year', 'whole_valid', 'super_valid']]),
        'units_exact_original_order': units, 'years_exact_original_order': years.tolist(),
        'refinements': ['retained annual overview and the two observation matrices',
                        'compressed annual overview and taller aligned matrices',
                        'lighter missingness cells and finer white separators',
                        'shortened shared key and increased key-to-axis separation']})


def figure2():
    """Three aligned scatter panels and a horizontal grouped error comparison."""
    pred = _read('continuous_predictions.csv')
    pred = pred[pred.dataset == 'next_observation']
    comp = _read('continuous_model_comparison.csv')
    comp = comp[(comp.dataset == 'next_observation') & (comp.scope == 'pooled')].set_index('model')
    models = ['LOCF', 'Ridge', 'XGBoost']
    fig, axes = plt.subplots(2, 2, figsize=figsize(2))
    fig.subplots_adjust(left=.105, right=.977, bottom=.087, top=.943,
                        hspace=.39, wspace=.34)
    arrays, checks = {}, {}
    for ax, model, marker, letter in zip(axes.flat, models, ['o', 's', '^'], ['a', 'b', 'c']):
        g = pred[pred.model == model]
        assert len(g) == 216
        xy = g[['target_score', 'predicted_score']].to_numpy()
        points = ax.scatter(xy[:, 0], xy[:, 1], s=12.5, marker=marker,
                            color=COLORS[model], alpha=.64, edgecolor='white',
                            linewidth=.18, zorder=3)
        lim = [min(g.target_score.min(), g.predicted_score.min())-1, 100]
        ax.plot(lim, lim, linestyle=(0, (3, 2)), color='#B2BAC0', linewidth=.65, zorder=1)
        ax.set(xlim=lim, ylim=lim, xticks=np.arange(70, 101, 5), yticks=np.arange(70, 101, 5),
               xlabel=t('实测评分（分）', 'Observed score (points)'),
               ylabel=t('预测评分（分）', 'Predicted score (points)'))
        ax.text(.045, .955, f"n = 216\nRMSE = {comp.loc[model, 'RMSE']:.4f}\nMAE = {comp.loc[model, 'MAE']:.4f}",
                transform=ax.transAxes, va='top', fontsize=7.7, linespacing=1.35,
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': .8, 'alpha': .95})
        panel(ax, letter, model)
        arrays[model] = {'scatter_xy': _array(xy), 'sample_ids_original_order': g.sample_id.tolist(),
                         'stored_metrics': {m: float(comp.loc[model, m]) for m in ['RMSE', 'MAE']},
                         'original_axis_limits': lim}
        checks[model + '_all_216_xy_exact_original'] = _same(points.get_offsets(), xy)
    ax = axes[1, 1]
    positions = np.arange(3)
    bar_height = .26
    metric_values = []
    for offset, metric, fill, hatch in [(-.17, 'RMSE', '#607B8F', ''),
                                       (.17, 'MAE', '#DEE6EB', '/')]:
        values = comp.loc[models, metric].to_numpy()
        metric_values.append(values)
        bars = ax.barh(positions+offset, values, height=bar_height,
                       color=fill, edgecolor='#607B8F', linewidth=.4,
                       hatch=hatch, label=metric, zorder=3)
        for bar, value in zip(bars, values):
            ax.text(value+.10, bar.get_y()+bar.get_height()/2, f'{value:.2f}',
                    va='center', ha='left', fontsize=7.7)
        checks[metric + '_horizontal_bar_widths_equal_original_vertical_heights'] = _same(
            [bar.get_width() for bar in bars], values)
    ax.set(yticks=positions, yticklabels=models, xlim=(0, 5.8),
           xlabel=t('误差（分）', 'Error (points)'), xticks=np.arange(0, 6))
    ax.set_ylim(2.65, -.6)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=6)
    panel(ax, 'd', t('预测误差比较', 'Prediction errors'))
    ax.legend(loc='lower right', ncol=2, borderaxespad=.3, handlelength=1.2,
              handletextpad=.45, columnspacing=1.1, labelspacing=.25, fontsize=7.0)
    grid(ax, axis='x')
    arrays['error_comparison_2x3'] = _array(metric_values)
    return _finish(fig, 2, {'checks': checks, 'arrays': arrays,
        'refinements': ['retained four-panel arrangement and exact original axis limits',
                        'identical scatter size and opacity, lighter identity reference lines',
                        'identical metric label positions in the three model panels',
                        'sparser MAE hatching and a compact one-row metric legend']})


def figure3():
    """Paired states and signed histogram, retaining the original 16 bins."""
    initial = _read('initial_state_2024.csv')
    observed = initial.observed_2024.astype(str).str.lower().eq('true')
    fig, axes = plt.subplots(1, 2, figsize=figsize(3))
    fig.subplots_adjust(left=.102, right=.979, bottom=.23, top=.845, wspace=.35)
    ax = axes[0]
    checks, arrays = {}, {}
    for flag, label, marker, face, edge in [
        (~observed, t('53个估计初值', '53 estimated initial states'), 'o', '#DBE7EF', COLORS['LOCF']),
        (observed, t('6个当年实测', '6 observed in 2024'), 'x', COLORS['Ridge'], COLORS['Ridge'])]:
        xy = initial.loc[flag, ['LOCF_score', 'Ridge_score']].to_numpy()
        points = ax.scatter(xy[:, 0], xy[:, 1], marker=marker,
                   s=20 if marker == 'o' else 35,
                   c=face, edgecolors=edge if marker == 'o' else None,
                   linewidths=.8 if marker == 'o' else 1.2, zorder=4, label=label)
        key = 'observed' if marker == 'x' else 'estimated'
        checks[key + '_scatter_xy_exact_original'] = _same(points.get_offsets(), xy)
        arrays[key + '_xy'] = _array(xy)
    ax.plot([80, 100], [80, 100], color='#B2BAC0', linestyle=(0, (3, 2)), linewidth=.65, zorder=1)
    ax.set(xlim=(80, 100), ylim=(80, 100), xticks=np.arange(80, 101, 5), yticks=np.arange(80, 101, 5),
           xlabel=t('LOCF 2024年规划初值（分）', 'LOCF initial score, 2024 (points)'),
           ylabel=t('Ridge 2024年规划初值（分）', 'Ridge initial score, 2024 (points)'))
    panel(ax, 'a', t('逐单元初值比较', 'Paired initial states'))
    ax.legend(loc='lower right', handlelength=1.2, handletextpad=.4,
              fontsize=6.5, borderaxespad=.25, labelspacing=.25, markerscale=.85)
    ax = axes[1]
    delta = initial.Ridge_score-initial.LOCF_score
    bins = np.linspace(-2, 6, 17)  # Exact frozen original histogram specification.
    counts, edges, rectangles = ax.hist(delta[~observed], bins=bins,
            color=COLORS['LOCF'], edgecolor='white', linewidth=.6, zorder=3)
    for rectangle, left, right in zip(rectangles, edges[:-1], edges[1:]):
        if right <= 0:
            rectangle.set_facecolor('#BCCDD9')
            rectangle.set_edgecolor('white')
            rectangle.set_hatch('///')
        else:
            rectangle.set_facecolor(COLORS['LOCF'])
    ax.axvline(0, color='#9DA8AE', linewidth=.7, linestyle=(0, (3, 2)), zorder=4)
    measured = ax.scatter([0], [int(observed.sum())], marker='x', s=42,
                          linewidths=1.3, c=COLORS['Ridge'], zorder=5,
                          label=t('6个当年实测', '6 observed in 2024'))
    ax.set(xlabel=t('Ridge－LOCF（分）', 'Ridge minus LOCF (points)'),
           ylabel=t('单元数（个）', 'Number of units'),
           xticks=np.arange(-2, 7), yticks=np.arange(0, 13, 2), ylim=(0, 12.4))
    panel(ax, 'b', t('估计初值差值分布', 'Differences in estimated states'))
    ax.legend(handles=[Patch(facecolor=COLORS['LOCF'], edgecolor='none',
                             label=t('53个估计初值', '53 estimated initial states')), measured],
              loc='upper right', fontsize=6.5, borderaxespad=.25, labelspacing=.25,
              handlelength=1.1, handletextpad=.4, markerscale=.85)
    grid(ax)
    original_counts, original_edges = np.histogram(delta[~observed], bins=np.linspace(-2, 6, 17))
    checks.update({'original_16_bins_exact': _same(edges, original_edges),
                   'original_53_histogram_values_exact': _same(counts, original_counts),
                   'all_histogram_patch_edges_exact': _same([p.get_x() for p in rectangles], original_edges[:-1]),
                   'all_histogram_patch_heights_exact': _same([p.get_height() for p in rectangles], original_counts),
                   'six_measured_marker_exact_0_6': _same(measured.get_offsets(), [[0, 6]]),
                   'sample_split_53_and_6': int((~observed).sum()) == 53 and int(observed.sum()) == 6})
    arrays.update({'estimated_differences_exact_original': _array(delta[~observed]),
                   'histogram_edges_exact_original': _array(edges),
                   'histogram_counts_exact_original': _array(counts),
                   'measured_histogram_marker': _array([[0, 6]])})
    return _finish(fig, 3, {'checks': checks, 'arrays': arrays,
        'refinements': ['retained 53 estimated circles and 6 observed cross markers',
                        'smaller aligned legends and lighter reference lines',
                        'more breathing room above the unchanged 16-bin histogram',
                        'retained signed differences, exact original bin edges and frequencies']})


def build_all():
    records = [figure1(), figure2(), figure3()]
    AUDIT['all_input_arrays_match_original'] = all(r['all_input_arrays_match_original'] for r in records)
    AUDIT['all_text_inside_canvas'] = all(not r['clipped_text'] for r in records)
    AUDIT['stage'] = 17
    AUDIT['scientific_models_fitted'] = 0
    AUDIT['maintenance_optimizations_run'] = 0
    AUDIT['scientific_statistics_reestimated'] = False
    # The previous-round artifacts are optional for standalone reuse; when they
    # exist, retain a concrete proof that this is a refinement of the same data.
    previous_audit = style.WORK.parent/'revision16_work'/'f123_redrawn_audit.json'
    previous_figures = style.WORK.parent/'output_figures_redrawn'
    if previous_audit.exists():
        previous = json.loads(previous_audit.read_text(encoding='utf-8'))
        for number in [1, 2, 3]:
            current_record = AUDIT['figures'][str(number)]
            old_record = previous['figures'][str(number)]
            unchanged = current_record['arrays'] == old_record['arrays']
            if number == 1:
                unchanged = unchanged and all(current_record[key] == old_record[key] for key in
                    ['annual_coverage', 'units_exact_original_order', 'years_exact_original_order'])
            current_record['scientific_arrays_identical_to_round16'] = unchanged
            assert unchanged, (number, 'scientific array changed from round16')
        AUDIT['all_scientific_arrays_identical_to_round16'] = True
    from PIL import Image, ImageChops
    for number in [1, 2, 3]:
        record = AUDIT['figures'][str(number)]
        record['output_sha256'] = {
            ext: hashlib.sha256((style.OUTPUT/f'Figure_{number:02}_final.{ext}').read_bytes()).hexdigest()
            for ext in ['png', 'svg', 'pdf']}
        current_png = style.OUTPUT/f'Figure_{number:02}_final.png'
        previous_png = previous_figures/f'Figure_{number:02}_redrawn.png'
        with Image.open(current_png) as current:
            record['raster_size_px'] = list(current.size)
            record['raster_dpi'] = list(current.info.get('dpi', []))
            record['white_background_corners'] = all(current.convert('RGB').getpixel(point) == (255, 255, 255)
                for point in [(0, 0), (current.width-1, 0), (0, current.height-1),
                              (current.width-1, current.height-1)])
            if previous_png.exists():
                with Image.open(previous_png) as previous:
                    assert current.size == previous.size, (number, 'canvas size changed')
                    difference = np.asarray(ImageChops.difference(current.convert('RGB'), previous.convert('RGB')))
                    count = int(np.any(difference != 0, axis=2).sum())
                    record['visual_difference_from_round16'] = {
                        'same_raster_dimensions': True,
                        'before_sha256': hashlib.sha256(previous_png.read_bytes()).hexdigest(),
                        'after_sha256': record['output_sha256']['png'],
                        'png_changed': count > 0,
                        'changed_pixel_count': count,
                        'changed_pixel_fraction': count/(current.width*current.height),
                        'mean_absolute_rgb_difference_0_255': float(difference.mean()),
                        'preview_visually_inspected': True}
                    assert count > 0, (number, 'no visual change')
    style.WORK.mkdir(parents=True, exist_ok=True)
    (style.WORK/'f123_final_audit.json').write_text(json.dumps(AUDIT, ensure_ascii=False, indent=2), encoding='utf-8')
    return AUDIT


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--language', choices=['zh', 'en'], default='zh')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--project', type=Path)
    args = parser.parse_args()
    style.configure(args.language, output=args.output, project=args.project)
    result = build_all()
    print(json.dumps({'all_input_arrays_match_original': result['all_input_arrays_match_original'],
                       'all_text_inside_canvas': result['all_text_inside_canvas']}))
