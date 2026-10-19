"""Scientific chart redesign of Figures 1–3 using frozen original plot inputs.

The Chinese/English display strings share the same data and figure construction.
All published model error statistics are read from the frozen comparison CSV.
"""
from pathlib import Path
import hashlib
import json
import argparse
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/figure_redesign_mpl')
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import figure_style as style
from figure_style import t, COLORS, panel, grid, figsize

AUDIT = {'scope': 'figures only; no model, optimization, or published-statistic recalculation',
         'source_files': {}, 'figures': {},
         'reference': 'frozen source CSVs; no external plotting module required'}
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
    """Grouped annual counts and exact 59 × 13 observation-presence matrices."""
    yearly = _read('yearly_observation_count.csv')
    obs = _read('observations_long.csv')
    units = sorted(obs.unit_id.unique())
    years = np.arange(2012, 2025)
    assert len(units) == 59 and len(years) == 13
    assert np.array_equal(np.sort(obs.year.unique()), years)
    yearly = yearly.set_index('year').loc[years].reset_index()
    fig = plt.figure(figsize=figsize(1))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 2],
                         left=.104, right=.979, bottom=.16, top=.90,
                         hspace=.31, wspace=.285)
    ax = fig.add_subplot(gs[0, :])
    checks, records, bar_heights = {}, {}, {}
    width = .34
    for offset, col, name, color in [
        (-width/2, 'whole_valid', t('全桥评分', 'Whole-bridge score'), COLORS['LOCF']),
        ( width/2, 'super_valid', t('上部结构评分', 'Superstructure score'), COLORS['Ridge'])]:
        values = yearly[col].to_numpy()
        bars = ax.bar(years+offset, values, width=width, color=color,
                      linewidth=0, label=name, zorder=3)
        bar_heights[col] = np.array([bar.get_height() for bar in bars])
        checks[col+'_bar_heights_exact_frozen_csv'] = _same(bar_heights[col], values)
        # A missing inspection year is explicitly a zero count, never a zero score.
        for year, value in zip(years, values):
            if value == 0:
                ax.text(year+offset, 1.1, '0', ha='center', va='bottom', color=color,
                        fontsize=6.8, zorder=4)
    ax.set(xlim=(2011.45, 2024.55), ylim=(0, 65), xticks=years,
           yticks=[0, 20, 40, 60], ylabel=t('观测数（条）', 'Observations'))
    ax.tick_params(axis='x', labelsize=7.4)
    panel(ax, 'a', t('年度观测数量', 'Annual observation counts'))
    ax.legend(loc='lower right', bbox_to_anchor=(1, 1.07), ncol=2,
              columnspacing=1.6, borderaxespad=0, handlelength=1.3, fontsize=7.3)
    grid(ax)
    for index, (col, annual_col, title, color) in enumerate([
        ('whole_score', 'whole_valid', t('全桥评分观测矩阵', 'Whole-bridge observations'), COLORS['LOCF']),
        ('super_score', 'super_valid', t('上部结构评分观测矩阵', 'Superstructure observations'), COLORS['Ridge'])]):
        ax = fig.add_subplot(gs[1, index])
        original = obs.pivot(index='unit_id', columns='year', values=col).reindex(
            index=units, columns=years).notna().to_numpy()
        mesh = ax.pcolormesh(np.arange(14)-.5, np.arange(60)-.5,
                            original.astype(int), cmap=ListedColormap([COLORS['missing'], color]),
                            vmin=0, vmax=1, shading='flat',
                            edgecolors='white', linewidth=.12, antialiased=True,
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
        checks[f'{col}_tiles_equal_original_presence_matrix'] = _same(plotted, original)
        checks[f'{annual_col}_bar_equals_matrix_column_sum'] = _same(
            bar_heights[annual_col], original.sum(axis=0))
        records[col] = _array(original.astype(int))
        records[col]['observed_count'] = int(original.sum())
        records[col]['annual_column_sums'] = original.sum(axis=0).tolist()
    checks['whole_total_387'] = records['whole_score']['observed_count'] == 387
    checks['super_total_380'] = records['super_score']['observed_count'] == 380
    checks['all_59_units_and_13_years_preserved'] = all(
        x['shape'] == [59, 13] for x in records.values())
    fig.legend(handles=[Patch(facecolor=COLORS['missing'], edgecolor='none', label=t('缺测', 'Missing')),
                        Patch(facecolor=COLORS['LOCF'], edgecolor='none', label=t('全桥有观测', 'Whole bridge observed')),
                        Patch(facecolor=COLORS['Ridge'], edgecolor='none', label=t('上部结构有观测', 'Superstructure observed'))],
               ncol=3, loc='lower center', bbox_to_anchor=(.54, -.008),
               handlelength=1.0, handletextpad=.5, columnspacing=1.5, fontsize=7.0)
    record = _finish(fig, 1, {'checks': checks, 'arrays': records,
        'annual_coverage': _array(yearly[['year', 'whole_valid', 'super_valid']]),
        'annual_bar_heights': {k:v.tolist() for k,v in bar_heights.items()},
        'units_exact_original_order': units, 'years_exact_original_order': years.tolist(),
        'old_chart_type': 'two annual line series plus two observation matrices',
        'new_chart_type': 'annual grouped columns plus two aligned observation-presence heatmaps',
        'missing_data_semantics': 'Not-na presence mask only; missing scores remain missing and are not zero scores.',
        'refinements': ['replaced two annual line series with grouped columns',
                        'explicit zero labels on both series in 2014, 2015 and 2017',
                        'verified every annual column count against each matrix column sum',
                        'preserved all 59 units and 13 years in aligned fine-grid matrices']})
    from PIL import Image, ImageChops
    folder = style.OUTPUT/'fig1'
    current_png = folder/'Figure_01_redesigned.png'
    previous_png = style.HERE.parent.parent/'output_figures_final'/'Figure_01_final.png'
    record['output_sha256'] = {ext: hashlib.sha256((folder/f'Figure_01_redesigned.{ext}').read_bytes()).hexdigest()
                               for ext in ['png', 'svg', 'pdf', 'tiff']}
    with Image.open(current_png) as current:
        record['raster_size_px'] = list(current.size)
        record['raster_dpi'] = list(current.info.get('dpi', []))
        record['white_background_corners'] = all(current.convert('RGB').getpixel(point) == (255,255,255)
            for point in [(0,0),(current.width-1,0),(0,current.height-1),(current.width-1,current.height-1)])
        if previous_png.exists():
            with Image.open(previous_png) as previous:
                assert current.size == previous.size
                diff = np.asarray(ImageChops.difference(current.convert('RGB'), previous.convert('RGB')))
                changed = int(np.any(diff != 0, axis=2).sum())
                record['visual_difference_from_previous'] = {'same_canvas': True, 'changed_pixel_count': changed,
                    'png_changed': changed > 0, 'old_sha256': hashlib.sha256(previous_png.read_bytes()).hexdigest(),
                    'new_sha256': record['output_sha256']['png']}
                assert changed > 0
    record['source_files'] = {n: AUDIT['source_files'][n] for n in ['yearly_observation_count.csv', 'observations_long.csv']}
    for n in record['source_files']:
        assert hashlib.sha256((style.SOURCE/n).read_bytes()).hexdigest() == FROZEN_SHA256[n]
    record['source_sha256_unchanged_after_plotting'] = True
    record['scientific_models_fitted'] = 0
    record['maintenance_optimizations_run'] = 0
    record['preview_visually_inspected'] = False
    style.WORK.mkdir(parents=True, exist_ok=True)
    (style.WORK/'fig1_data_audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record


def figure2():
    """Three equal-scale scatter panels and six frozen pooled error metrics."""
    pred = _read('continuous_predictions.csv')
    pred = pred[pred.dataset == 'next_observation']
    comp = _read('continuous_model_comparison.csv')
    comp = comp[(comp.dataset == 'next_observation') & (comp.scope == 'pooled')].set_index('model')
    models = ['LOCF', 'Ridge', 'XGBoost']
    common_min = float(min(pred.target_score.min(), pred.predicted_score.min()) - 1)
    common_limits = [common_min, 100.0]
    fig, axes = plt.subplots(2, 2, figsize=figsize(2))
    fig.subplots_adjust(left=.105, right=.977, bottom=.087, top=.943,
                        hspace=.39, wspace=.34)
    arrays, checks = {}, {}
    scatter_axes = []
    for ax, model, marker, letter in zip(axes.flat, models, ['o', 's', '^'], ['a', 'b', 'c']):
        scatter_axes.append(ax)
        g = pred[pred.model == model]
        assert len(g) == 216 and int(comp.loc[model,'n']) == 216
        xy = g[['target_score', 'predicted_score']].to_numpy()
        points = ax.scatter(xy[:, 0], xy[:, 1], s=12.5, marker=marker,
                            color=COLORS[model], alpha=.64, edgecolor='white',
                            linewidth=.18, zorder=3)
        identity, = ax.plot(common_limits, common_limits, linestyle=(0, (3, 2)),
                            color='#ADB9C1', linewidth=.65, zorder=1)
        ax.set(xlim=common_limits, ylim=common_limits,
               xticks=np.arange(70, 101, 5), yticks=np.arange(70, 101, 5),
               xlabel=t('实测评分（分）', 'Observed score (points)'),
               ylabel=t('预测评分（分）', 'Predicted score (points)'))
        ax.set_aspect('equal', adjustable='box')
        ax.text(.045, .955,
                f"n = {int(comp.loc[model, 'n'])}\nRMSE = {comp.loc[model, 'RMSE']:.4f}\nMAE = {comp.loc[model, 'MAE']:.4f}",
                transform=ax.transAxes, va='top', fontsize=7.7, linespacing=1.35,
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': .8, 'alpha': .95})
        panel(ax, letter, model)
        arrays[model] = {'scatter_xy': _array(xy), 'sample_ids_original_order': g.sample_id.tolist(),
                         'stored_metrics': {m: float(comp.loc[model, m]) for m in ['RMSE', 'MAE']},
                         'n_from_stored_metrics': int(comp.loc[model,'n']),
                         'display_limits_xy': common_limits, 'marker': marker,
                         'point_size_pt2': 12.5, 'point_alpha': .64}
        checks[model + '_all_216_xy_exact_original'] = _same(points.get_offsets(), xy)
        checks[model + '_n216_matches_stored_metrics'] = len(g) == int(comp.loc[model,'n']) == 216
        checks[model + '_identity_line_exact_common_limits'] = _same(
            identity.get_xydata(), np.column_stack([common_limits,common_limits]))
        checks[model + '_equal_xy_aspect'] = ax.get_aspect() == 1
    ax = axes[1, 1]
    positions = np.arange(3)
    bar_height = .26
    metric_values = []
    for offset, metric, fill, hatch in [(-.17, 'RMSE', '#6F8493', ''),
                                       (.17, 'MAE', '#DEE6EB', '/')]:
        values = comp.loc[models, metric].to_numpy()
        metric_values.append(values)
        bars = ax.barh(positions+offset, values, height=bar_height,
                       color=fill, edgecolor='#6F8493', linewidth=.45,
                       hatch=hatch, label=metric, zorder=3)
        for bar, value in zip(bars, values):
            ax.text(value+.10, bar.get_y()+bar.get_height()/2, f'{value:.2f}',
                    va='center', ha='left', fontsize=7.7)
        checks[metric + '_horizontal_bar_widths_exact_stored_values'] = _same(
            [bar.get_width() for bar in bars], values)
        arrays[metric+'_ascending_error_order'] = comp.loc[models,metric].sort_values().index.tolist()
    ax.set(yticks=positions, yticklabels=models, xlim=(0, 5.8),
           xlabel=t('误差（分）', 'Error (points)'), xticks=np.arange(0, 6))
    ax.set_ylim(2.65, -.6)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=6)
    panel(ax, 'd', t('预测误差', 'Prediction errors'))
    ax.legend(loc='lower right', bbox_to_anchor=(1,1.03), ncol=2, borderaxespad=0,
              handlelength=1.2, handletextpad=.45, columnspacing=1.1, fontsize=7.0)
    grid(ax, axis='x')
    style.format_text(fig)
    fig.canvas.draw()
    dims = [[float(a.get_window_extent().width),float(a.get_window_extent().height)] for a in scatter_axes]
    checks['all_three_scatter_limits_identical'] = all(
        _same(a.get_xlim(),common_limits) and _same(a.get_ylim(),common_limits) for a in scatter_axes)
    checks['all_three_scatter_boxes_equal_dimensions'] = bool(np.allclose(dims,dims[0],atol=1e-8,rtol=0))
    checks['all_three_scatter_boxes_square'] = all(abs(w-h)<1e-8 for w,h in dims)
    checks['RMSE_method_order_Ridge_XGBoost_LOCF'] = arrays['RMSE_ascending_error_order'] == ['Ridge','XGBoost','LOCF']
    checks['MAE_method_order_Ridge_XGBoost_LOCF'] = arrays['MAE_ascending_error_order'] == ['Ridge','XGBoost','LOCF']
    arrays['error_comparison_2x3'] = _array(metric_values)
    record = _finish(fig, 2, {'checks': checks, 'arrays': arrays,
        'old_chart_type': 'three prediction scatters and grouped horizontal metric bars',
        'new_chart_type': 'three identical-square prediction scatters and grouped horizontal metric bars',
        'scatter_display_boxes_px_at_100dpi': dims,
        'scatter_common_xlim_ylim': common_limits,
        'method_row_order': models,
        'no_error_bars_added_to_stored_single_metrics': True,
        'refinements': ['set identical x/y data ranges and equal square display aspect for all three scatters',
                        'retained every one of 216 observations in each method and exact stored pooled metrics',
                        'kept stable blue circle / orange square / green triangle model styling',
                        'separated neutral metric fill/hatch key above the direct-labelled horizontal bars'],
        'scientific_models_fitted': 0, 'maintenance_optimizations_run': 0})
    from PIL import Image, ImageChops
    folder = style.OUTPUT/'fig2'
    current_png = folder/'Figure_02_redesigned.png'
    previous_png = style.HERE.parent.parent/'output_figures_final'/'Figure_02_final.png'
    record['output_sha256'] = {ext: hashlib.sha256((folder/f'Figure_02_redesigned.{ext}').read_bytes()).hexdigest()
                               for ext in ['png', 'svg', 'pdf', 'tiff']}
    with Image.open(current_png) as current:
        record['raster_size_px'] = list(current.size)
        record['raster_dpi'] = list(current.info.get('dpi', []))
        record['white_background_corners'] = all(current.convert('RGB').getpixel(point) == (255,255,255)
            for point in [(0,0),(current.width-1,0),(0,current.height-1),(current.width-1,current.height-1)])
        if previous_png.exists():
            with Image.open(previous_png) as previous:
                assert current.size == previous.size
                diff = np.asarray(ImageChops.difference(current.convert('RGB'), previous.convert('RGB')))
                changed = int(np.any(diff != 0, axis=2).sum())
                record['visual_difference_from_previous'] = {'same_canvas': True, 'changed_pixel_count': changed,
                    'png_changed': changed > 0, 'old_sha256': hashlib.sha256(previous_png.read_bytes()).hexdigest(),
                    'new_sha256': record['output_sha256']['png']}
                assert changed > 0
    record['source_files'] = {n:AUDIT['source_files'][n] for n in
                             ['continuous_predictions.csv','continuous_model_comparison.csv']}
    for n in record['source_files']:
        assert hashlib.sha256((style.SOURCE/n).read_bytes()).hexdigest() == FROZEN_SHA256[n]
    record['source_sha256_unchanged_after_plotting'] = True
    record['preview_visually_inspected'] = False
    style.WORK.mkdir(parents=True, exist_ok=True)
    (style.WORK/'fig2_data_audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record


def figure3():
    """Paired 2024 initial states and their exact signed difference distribution."""
    initial = _read('initial_state_2024.csv')
    observed = initial.observed_2024.astype(str).str.lower().eq('true')
    assert int(observed.sum()) == 6 and int((~observed).sum()) == 53
    fig, axes = plt.subplots(1, 2, figsize=figsize(3))
    fig.subplots_adjust(left=.096, right=.979, bottom=.22, top=.86, wspace=.36)
    ax = axes[0]
    checks, arrays = {}, {}
    for flag, label, marker in [
        (~observed, t('53个估计单元', '53 estimated units'), 'o'),
        (observed, t('6个2024年实测单元', '6 units observed in 2024'), 'x')]:
        xy = initial.loc[flag, ['LOCF_score', 'Ridge_score']].to_numpy()
        if marker == 'o':
            points = ax.scatter(xy[:, 0], xy[:, 1], marker=marker, s=17,
                facecolors='none', edgecolors=COLORS['LOCF'], linewidths=.8,
                alpha=.88, zorder=3, label=label)
        else:
            points = ax.scatter(xy[:, 0], xy[:, 1], marker=marker, s=29,
                c=COLORS['Ridge'], linewidths=1.15, zorder=5, label=label)
        key = 'observed' if marker == 'x' else 'estimated'
        checks[key + '_scatter_xy_exact_original'] = _same(points.get_offsets(), xy)
        arrays[key + '_xy'] = _array(xy)
        arrays[key + '_unit_ids_original_order'] = initial.loc[flag, 'unit_id'].tolist()
    identity, = ax.plot([80, 100], [80, 100], color='#9CA8AF',
                        linestyle=(0, (3, 2)), linewidth=.7, zorder=1)
    ax.set(xlim=(80, 100), ylim=(80, 100), xticks=np.arange(80, 101, 5), yticks=np.arange(80, 101, 5),
           xlabel=t('LOCF规划初值（分）', 'LOCF initial score (points)'),
           ylabel=t('Ridge规划初值（分）', 'Ridge initial score (points)'))
    panel(ax, 'a', t('2024年初值配对比较', 'Paired initial states, 2024'))
    ax.legend(loc='lower right', handlelength=1.1, handletextpad=.35,
              fontsize=6.4, borderaxespad=.25, labelspacing=.35, markerscale=.9)
    checks['identity_line_exact_80_100'] = _same(identity.get_xydata(), [[80,80],[100,100]])
    ax = axes[1]
    delta = initial.Ridge_score-initial.LOCF_score
    estimated_delta = delta[~observed].to_numpy()
    measured_delta = delta[observed].to_numpy()
    bins = np.linspace(-2, 6, 17)  # Frozen original 16-bin specification.
    counts, edges, rectangles = ax.hist(estimated_delta, bins=bins,
            color=COLORS['LOCF'], edgecolor='white', linewidth=.6, zorder=3)
    for rectangle, left, right in zip(rectangles, edges[:-1], edges[1:]):
        if right <= 0:
            rectangle.set_facecolor('#B7CFDE')
            rectangle.set_hatch('///')
    zero = ax.axvline(0, color='#7F8C8D', linewidth=.8, linestyle=(0, (3, 2)), zorder=4)
    # The rug displays each exact estimated difference, below the count baseline.
    rug = ax.scatter(estimated_delta, np.full(len(estimated_delta), -.68), marker='|',
                     s=14, linewidths=.55, c=COLORS['LOCF'], alpha=.75, zorder=4)
    measured = ax.scatter([0], [int(observed.sum())], marker='x', s=35,
                          linewidths=1.25, c=COLORS['Ridge'], zorder=5)
    ax.axhline(0, color='#B3BEC6', linewidth=.45, zorder=2)
    ax.set(xlabel=t('初值差值 Ridge－LOCF（分）', 'Initial-score difference: Ridge − LOCF (points)'),
           ylabel=t('单元数（个）', 'Number of units'), xlim=(-2, 6),
           xticks=np.arange(-2, 7), yticks=np.arange(0, 13, 2), ylim=(-1.25, 12.5))
    panel(ax, 'b', t('初值差值分布', 'Initial-score differences'))
    ax.legend(handles=[Patch(facecolor=COLORS['LOCF'], edgecolor='none',
                             label=t('53个估计：柱与短线', '53 estimated: bars and rug')),
                       Line2D([], [], color=COLORS['Ridge'], linestyle='none', marker='x',
                              markersize=4.8, markeredgewidth=1.1,
                              label=t('6个实测：差值均为0', '6 observed: differences all zero'))],
              loc='upper right', fontsize=6.3, borderaxespad=.2, labelspacing=.35,
              handlelength=1.1, handletextpad=.4)
    grid(ax)
    original_counts, original_edges = np.histogram(estimated_delta, bins=np.linspace(-2, 6, 17))
    checks.update({'original_16_bins_exact': _same(edges, original_edges),
                   'original_53_histogram_values_exact': _same(counts, original_counts),
                   'all_histogram_patch_edges_exact': _same([p.get_x() for p in rectangles], original_edges[:-1]),
                   'all_histogram_patch_heights_exact': _same([p.get_height() for p in rectangles], original_counts),
                   'all_53_estimated_differences_retained': int(counts.sum()) == 53,
                   'rug_exact_53_raw_signed_differences': _same(rug.get_offsets()[:,0], estimated_delta),
                   'six_measured_marker_exact_0_6': _same(measured.get_offsets(), [[0, 6]]),
                   'all_six_measured_differences_exactly_zero': _same(measured_delta, np.zeros(6)),
                   'sample_split_53_and_6': int((~observed).sum()) == 53 and int(observed.sum()) == 6,
                   'sign_definition_Ridge_minus_LOCF': _same(delta, initial.Ridge_score-initial.LOCF_score)})
    arrays.update({'estimated_differences_exact_original': _array(estimated_delta),
                   'measured_differences': _array(measured_delta),
                   'histogram_edges_exact_original': _array(edges),
                   'histogram_counts_exact_original': _array(counts),
                   'measured_histogram_marker': _array([[0, 6]])})
    record = _finish(fig, 3, {'checks': checks, 'arrays': arrays,
        'old_chart_type': 'paired scatter and signed histogram',
        'new_chart_type': 'open estimated circles / measured crosses with identity reference; signed histogram with raw-value rug',
        'refinements': ['open circles separate the 53 estimated units from the six measured crosses',
                        'placed the shared 2024 reference year in panel title and shortened axis labels',
                        'retained exact 16 original bins and their frequencies',
                        'added a compact rug containing all 53 exact signed differences',
                        'explicitly identified six observed units as zero-difference measurements'],
        'difference_direction': 'Ridge_score minus LOCF_score',
        'all_59_units_accounted_for': True,
        'scientific_models_fitted': 0, 'maintenance_optimizations_run': 0})
    from PIL import Image, ImageChops
    folder = style.OUTPUT/'fig3'
    current_png = folder/'Figure_03_redesigned.png'
    previous_png = style.HERE.parent.parent/'output_figures_final'/'Figure_03_final.png'
    record['output_sha256'] = {ext: hashlib.sha256((folder/f'Figure_03_redesigned.{ext}').read_bytes()).hexdigest()
                               for ext in ['png', 'svg', 'pdf', 'tiff']}
    with Image.open(current_png) as current:
        record['raster_size_px'] = list(current.size)
        record['raster_dpi'] = list(current.info.get('dpi', []))
        record['white_background_corners'] = all(current.convert('RGB').getpixel(point) == (255,255,255)
            for point in [(0,0),(current.width-1,0),(0,current.height-1),(current.width-1,current.height-1)])
        if previous_png.exists():
            with Image.open(previous_png) as previous:
                assert current.size == previous.size
                diff = np.asarray(ImageChops.difference(current.convert('RGB'), previous.convert('RGB')))
                changed = int(np.any(diff != 0, axis=2).sum())
                record['visual_difference_from_previous'] = {'same_canvas': True, 'changed_pixel_count': changed,
                    'png_changed': changed > 0, 'old_sha256': hashlib.sha256(previous_png.read_bytes()).hexdigest(),
                    'new_sha256': record['output_sha256']['png']}
                assert changed > 0
    record['source_files'] = {'initial_state_2024.csv': AUDIT['source_files']['initial_state_2024.csv']}
    assert hashlib.sha256((style.SOURCE/'initial_state_2024.csv').read_bytes()).hexdigest() == FROZEN_SHA256['initial_state_2024.csv']
    record['source_sha256_unchanged_after_plotting'] = True
    record['preview_visually_inspected'] = False
    style.WORK.mkdir(parents=True, exist_ok=True)
    (style.WORK/'fig3_data_audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record


def build_all(numbers=(1, 2, 3)):
    """Reproduce selected figures using only the bundled, hash-verified CSVs."""
    functions = {1: figure1, 2: figure2, 3: figure3}
    numbers = list(numbers)
    if not numbers or any(n not in functions for n in numbers):
        raise ValueError('Figure numbers must be a non-empty selection of 1, 2, 3.')
    records = [functions[number]() for number in numbers]
    result = {'scope': AUDIT['scope'], 'figure_numbers': numbers,
              'source_files': AUDIT['source_files'],
              'figures': {str(r['number']):r for r in records},
              'all_input_arrays_match_original': all(r['all_input_arrays_match_original'] for r in records),
              'all_text_inside_canvas': all(not r['clipped_text'] for r in records),
              'all_source_sha256_unchanged': all(r['source_sha256_unchanged_after_plotting'] for r in records),
              'scientific_models_fitted': 0, 'maintenance_optimizations_run': 0,
              'scientific_statistics_reestimated': False,
              'data_reconstruction_from_images': False}
    style.WORK.mkdir(parents=True, exist_ok=True)
    (style.WORK/'figures_123_data_audit.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=['zh', 'en'], default='zh')
    parser.add_argument('--output', '--output-dir', dest='output', type=Path)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--figures', type=int, nargs='+', choices=[1, 2, 3], default=[1, 2, 3])
    args = parser.parse_args()
    style.configure(args.language, output=args.output, project=args.project)
    result = build_all(args.figures)
    print(json.dumps({'all_input_arrays_match_original': result['all_input_arrays_match_original'],
                       'all_text_inside_canvas': result['all_text_inside_canvas'],
                       'all_source_sha256_unchanged': result['all_source_sha256_unchanged']}))
