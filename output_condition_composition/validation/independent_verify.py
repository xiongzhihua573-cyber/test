#!/usr/bin/env python3
"""Independent audit: frozen literal schedules, original recurrence, strict grades.

This audit never imports preparation/plotting code or invokes any optimizer/model.
It uses the frozen project JSON/CSV as authority and cross-checks a scalar
fixed-action recurrence against the original archived audit recurrence and saved
annual metrics before auditing new exports. It does not decode vectors, select new
actions, fit a prediction model, or execute GJO.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path('/workspace')
DEFAULT_PROJECT = BASE / 'revision15_work/prior_project/manuscript_sci_stage12'
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1]
PACKAGED_BASELINE = Path(__file__).resolve().with_name('independent_preservation_baseline.json')
DEFAULT_BASELINE = (PACKAGED_BASELINE if PACKAGED_BASELINE.exists()
                    else BASE / 'drawing2_work/independent_preservation_baseline.json')
YEARS = list(range(2025, 2040))
N = 59
D = 0.65
R = 6.0
ENGINE_SHA = 'cf8f22ae3f5c904cc8e1e201adb56be847b9eb562427fea60d48e558b6a773d1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    # Preserve float64 representations across CSV serialization, including values
    # near rating thresholds. No decimal rounding or epsilon for classification.
    return pd.read_csv(path, float_precision='round_trip')


def grade_scalar(score):
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(f'Score outside [0,100]: {score!r}')
    if 90 < score <= 100:
        return 1
    if 75 < score <= 90:
        return 2
    if 60 < score <= 75:
        return 3
    if 40 < score <= 60:
        return 4
    return 5


def boundary_tests():
    tests = [(100., 1), (90., 2), (75., 3), (60., 4), (40., 5), (0., 5)]
    for bound, lower_grade, higher_grade in [(90., 2, 1), (75., 3, 2), (60., 4, 3), (40., 5, 4)]:
        tests.extend([(float(np.nextafter(bound, -np.inf)), lower_grade),
                      (float(np.nextafter(bound, np.inf)), higher_grade)])
    tests.extend([(float(np.nextafter(100., -np.inf)), 1),
                  (float(np.nextafter(0., np.inf)), 5)])
    rows = []
    for score, expected in tests:
        actual = grade_scalar(score)
        assert actual == expected, (score, actual, expected)
        rows.append(dict(score=score, float_hex=score.hex(), expected=expected, actual=actual, passed=True))
    for invalid in [-1., 101., float('nan'), float('inf')]:
        try:
            grade_scalar(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid score accepted: {invalid}')
    return rows


def archived_simulator(path):
    assert sha(path) == ENGINE_SHA, ('Original archived engine SHA mismatch', path)
    tree = ast.parse(path.read_text())
    names = {'_inputs', 'resource_tolerance', 'simulate_actions'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == names
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    env = dict(np=np, HORIZON=15, YEARS=tuple(YEARS), K=3, CAPACITY=8,
               MIN_GAP=3, REQUIRED_GOOD=57, EPS=1e-8, R=R)
    # Only frozen literal-action audit functions execute. No decode/search/core.
    exec(compile(module, str(path), 'exec'), env)
    return env['simulate_actions']


def scalar_recurrence(initial, actions):
    # Each unit evolves independently after the already fixed literal actions.
    scores = np.empty((N, 15))
    for i in range(N):
        state = float(initial[i])
        for t in range(15):
            state = min(100., max(0., state - D) + R * int(actions[i, t]))
            scores[i, t] = state
    return scores


def close(actual, expected, name):
    assert np.isclose(actual, expected, rtol=0, atol=1e-10), (name, actual, expected)


def preservation(project, baseline):
    manifest_path = project / 'source/frozen_scientific_inputs.json'
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest['files']) == 661
    changed = [rel for rel, expected in manifest['files'].items()
               if not (project / rel).exists() or sha(project / rel) != expected]
    assert not changed, ('Frozen scientific source changed', changed)
    old = json.loads(baseline.read_text())
    assert len(old['current_paper_and_original_figures']) == 29
    paper_fig_changed = [path for path, expected in old['current_paper_and_original_figures'].items()
                         if not Path(path).exists() or sha(path) != expected]
    assert not paper_fig_changed, ('Previous paper/figures changed', paper_fig_changed)
    assert sha(manifest_path) == old['frozen_manifest_sha256']
    return dict(current_paper_and_28_original_exports_checked=29,
                current_paper_and_original_figures_unchanged=True,
                frozen_scientific_files_checked=len(manifest['files']),
                all_661_frozen_scientific_files_unchanged=True,
                changed=[])


def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(x) for x in value]
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def run(args):
    project, out = args.project, args.output
    source = out / 'source_data'
    init = read(project / 'source_data/initial_state_2024.csv')
    assert len(init) == N and init.unit_id.is_unique
    unit_ids = list(init.unit_id)
    initial = init.LOCF_score.to_numpy(float)
    areas = init.area.to_numpy(float)
    weights = areas / areas.sum()
    params = read(project / 'tables/Table_03_parameters_15y.csv')
    parameter_values = params.set_index('parameter').value
    for name, expected in dict(n_units=N, planning_horizon=15, year_start=2025,
                               year_end=2039, d=D, R=R, annual_capacity=8,
                               min_gap=3, max_unit_actions=3).items():
        assert float(parameter_values[name]) == expected, (name, parameter_values[name])
    provenance = json.loads((source / 'source_provenance.json').read_text())
    for filename, entry in provenance['copied_sources'].items():
        assert sha(source / filename) == sha(project / entry['original_relative_path']) == entry['sha256']
    simulator = archived_simulator(source / 'original_area_model_stage7.py')
    tests = boundary_tests()
    test_scores = np.array([r['score'] for r in tests])
    test_sim = simulator(test_scores, np.full(len(test_scores), 1/len(test_scores)),
                         np.zeros((len(test_scores), 15), dtype=int), d=0, budget=0)
    assert test_sim['grades'][:, 0].tolist() == [r['expected'] for r in tests]
    summary = read(project / 'results/resource_level_summary_15y.csv')
    all_runs = read(project / 'results/resource_level_runs_15y.csv')
    old_annual = read(project / 'results/resource_representative_annual_15y.csv')
    zero_annual = read(project / 'results/no_maintenance_baselines_annual_15y.csv')
    zero_row = read(project / 'results/no_maintenance_baselines_15y.csv')
    zero_annual = zero_annual[(zero_annual.initial_condition == 'LOCF') & (zero_annual.d == D)].sort_values('year')
    zero_row = zero_row[(zero_row.initial_condition == 'LOCF') & (zero_row.d == D)].iloc[0]
    scenarios = {}
    # Scenario labels are joined to the independently verified selected source IDs.
    for level in [1, 3, 6]:
        srow = summary[(summary.initial_condition == 'LOCF') & (summary.level_id == level)].iloc[0]
        run_id = str(srow.best_run_id)
        original_path = project / f'results/runs/{run_id}.json'
        archive = json.loads(original_path.read_text())
        assert sha(source / original_path.name) == sha(original_path)
        row = archive['row']
        assert row['initial_condition'] == 'LOCF' and row['d'] == D
        assert row['planning_horizon'] == 15 and row['start_year'] == 2025 and row['end_year'] == 2039
        assert row['feasible'] is True and row['schedule_replay_passed'] is True
        assert all(archive['replay_checks'].values())
        assert row['B_limit'] == float(srow.B_limit)
        cohort = all_runs[(all_runs.initial_condition == 'LOCF') & (all_runs.level_id == level)]
        assert len(cohort) == 30 and cohort.feasible.all()
        close(row['J'], cohort.loc[cohort.feasible, 'J'].max(), f'{run_id} stored cohort best J')
        actions = np.asarray(archive['actions'], dtype=int)
        assert actions.shape == (N, 15) and np.isin(actions, [0, 1]).all()
        scores = scalar_recurrence(initial, actions)
        report = simulator(initial, weights, actions, d=D, budget=row['B_limit'])
        assert np.array_equal(scores, report['scores']), f'{run_id} scalar != archived simulator'
        assert report['metrics']['feasible'] is True
        for key in ['J', 'resource', 'terminal_mean', 'minimum_score', 'min_good_count',
                    'min_management_count', 'maintenance_count', 'max_annual_count',
                    'max_unit_count', 'min_gap']:
            close(report['metrics'][key], row[key], f'{run_id} stored {key}')
        annual = old_annual[old_annual.run_id == run_id].sort_values('year')
        assert annual.year.tolist() == YEARS
        annual_error = []
        for t, saved in enumerate(annual.itertuples(index=False)):
            current = dict(mean_score=float(scores[:, t].mean()), minimum_score=float(scores[:, t].min()),
                           good_count=int((scores[:, t] > 75).sum()),
                           management_count=int((scores[:, t] > 75 + 1e-8).sum()),
                           maintenance_count=int(actions[:, t].sum()),
                           B_used=float((actions[:, t] * weights).sum()))
            for key, value in current.items():
                close(value, getattr(saved, key), f'{run_id} {YEARS[t]} {key}')
                annual_error.append(abs(value - getattr(saved, key)))
        assert (actions.sum(axis=0) <= 8).all()
        assert (actions.sum(axis=1) <= 3).all()
        gaps = [int(gap) for row_actions in actions for gap in np.diff(np.flatnonzero(row_actions))]
        assert all(gap >= 3 for gap in gaps)
        assert (scores > 60 + 1e-8).all()
        assert ((scores > 75 + 1e-8).sum(axis=0) >= 57).all()
        assert float((actions * weights[:, None]).sum()) <= row['B_limit'] + 1e-10 * max(1., row['B_limit'])
        scenarios[{1: 'low_resource', 3: 'medium_resource', 6: 'high_resource'}[level]] = dict(
            level_id=level, B=float(row['B_limit']), source_run_id=run_id,
            original_json_sha256=sha(original_path), metrics=report['metrics'],
            actions=actions, scores=scores, annual_actions=actions.sum(axis=0).tolist(),
            maximum_saved_annual_numeric_difference=max(annual_error),
            frozen_literal_action_matrix_used_without_changes=True,
            saved_replay_checks_all_true=True, scalar_original_engine_scores_bitwise_equal=True,
            source_row_metrics_agree=True, source_annual_metrics_agree=True)
    zero_actions = np.zeros((N, 15), dtype=int)
    zero_scores = scalar_recurrence(initial, zero_actions)
    zero_report = simulator(initial, weights, zero_actions, d=D, budget=0)
    assert np.array_equal(zero_scores, zero_report['scores'])
    for key in ['J', 'resource', 'terminal_mean', 'minimum_score', 'min_good_count',
                'min_management_count', 'maintenance_count']:
        close(zero_report['metrics'][key], zero_row[key], f'no maintenance stored {key}')
    assert zero_report['metrics']['feasible'] is False
    assert zero_report['metrics']['first_violation_year'] == 2036
    assert zero_report['metrics']['violation_types'] == 'management_count'
    assert zero_annual.year.tolist() == YEARS
    for t, saved in enumerate(zero_annual.itertuples(index=False)):
        close(zero_scores[:, t].mean(), saved.mean_score, f'no maintenance {YEARS[t]} mean')
        close(zero_scores[:, t].min(), saved.minimum_score, f'no maintenance {YEARS[t]} minimum')
        assert int((zero_scores[:, t] > 90).sum()) == int(saved.grade1_count)
        assert int(((zero_scores[:, t] > 75) & (zero_scores[:, t] <= 90)).sum()) == int(saved.grade2_count)
    scenarios['no_maintenance'] = dict(level_id=None, B=0., source_run_id='no_maintenance_LOCF_d065_15y',
        metrics=zero_report['metrics'], actions=zero_actions, scores=zero_scores,
        annual_actions=[0]*15, source_row_metrics_agree=True, source_annual_metrics_agree=True,
        scalar_original_engine_scores_bitwise_equal=True,
        role='Counterfactual control; not a management-feasible maintenance schedule')
    # New output interface is intentionally read only after original-source replay.
    composition = read(out / 'condition_composition_by_year.csv')
    unit_year = read(out / 'unit_year_scores.csv')
    selection = json.loads((out / 'scenario_selection.json').read_text())
    assert selection['initial_condition'] == 'LOCF'
    assert selection['initial_state_year'] == 2024
    assert selection['n_units'] == N and selection['years'] == YEARS
    assert selection['d'] == D and selection['R'] == R
    assert selection['capacity'] == 8 and selection['min_gap'] == 3
    assert selection['max_actions_per_unit'] == 3 and selection['required_units_above75'] == 57
    assert selection['grade_intervals'] == {
        '1': '90 < S <= 100', '2': '75 < S <= 90', '3': '60 < S <= 75',
        '4': '40 < S <= 60', '5': '0 <= S <= 40'}
    selected = {s['scenario']: s for s in selection['scenarios']}
    assert len(selected) == 4 and set(selected) == set(scenarios)
    assert len(composition) == 4*15*5 and len(unit_year) == 4*15*N
    assert set(composition.scenario) == set(scenarios) == set(unit_year.scenario)
    assert not composition.duplicated(['scenario', 'year', 'grade']).any()
    assert not unit_year.duplicated(['scenario', 'year', 'unit_id']).any()
    assert set(composition.grade) == set(range(1, 6))
    assert np.isfinite(unit_year.score).all() and unit_year.score.between(0, 100).all()
    assert np.isin(unit_year.action, [0, 1]).all()
    for frame in [composition, unit_year]:
        assert set(frame.initial_condition) == {'LOCF'}
        assert (frame.d == D).all() and (frame.R == R).all()
        assert set(frame.year) == set(YEARS)
    maximum_percent_error = 0.
    minimum_boundary_distance = math.inf
    for name, audit in scenarios.items():
        entry = selected[name]
        close(entry['B'], audit['B'], f'{name} manifest B')
        assert entry['initial_condition'] == 'LOCF'
        assert entry['d'] == D and entry['R'] == R
        assert entry['planning_horizon'] == 15 and entry['start_year'] == 2025 and entry['end_year'] == 2039
        assert entry['annual_actions'] == audit['annual_actions']
        assert entry['total_actions'] == int(audit['actions'].sum())
        assert entry['feasible_management_strategy'] is audit['metrics']['feasible']
        close(entry['B_used'], audit['metrics']['resource'], f'{name} manifest used resource')
        close(entry['J'], audit['metrics']['J'], f'{name} manifest J')
        close(entry['terminal_mean'], audit['metrics']['terminal_mean'], f'{name} terminal mean')
        close(entry['min_score'], audit['metrics']['minimum_score'], f'{name} minimum score')
        assert entry['minimum_grade12_count'] == audit['metrics']['min_good_count']
        expected_id = audit.get('source_run_id') if name != 'no_maintenance' else 'fixed_zero_action_baseline'
        if name != 'no_maintenance':
            assert entry['run_id'] == expected_id
            assert entry['seed'] == int(expected_id.rsplit('seed', 1)[1])
        cpart = composition[composition.scenario == name]
        upart = unit_year[unit_year.scenario == name]
        assert set(cpart.run_id) == {expected_id} == set(upart.run_id)
        assert (cpart.B == audit['B']).all() and (upart.B == audit['B']).all()
        assert set(upart.unit_id) == set(unit_ids)
        assert set(cpart.scenario_zh) == {entry['scenario_zh']} == set(upart.scenario_zh)
        count_table = []
        for t, year in enumerate(YEARS):
            uc = upart[upart.year == year].set_index('unit_id').loc[unit_ids]
            assert len(uc) == N
            assert np.array_equal(uc.initial_score.to_numpy(float), initial)
            assert np.array_equal(uc.score.to_numpy(float), audit['scores'][:, t]), (name, year, 'score exactness')
            assert np.array_equal(uc.action.to_numpy(int), audit['actions'][:, t])
            grades = [grade_scalar(float(s)) for s in audit['scores'][:, t]]
            assert grades == uc.grade.tolist()
            cc = cpart[cpart.year == year].set_index('grade').loc[list(range(1, 6))]
            counts = [grades.count(g) for g in range(1, 6)]
            percentages = np.array(counts, dtype=float) / N * 100.
            assert counts == cc['count'].tolist()
            assert sum(counts) == N and int(cc['count'].sum()) == N
            assert np.allclose(cc.percentage, percentages, rtol=0, atol=1e-12)
            assert np.isclose(cc.percentage.sum(), 100, rtol=0, atol=1e-12)
            maximum_percent_error = max(maximum_percent_error, abs(float(cc.percentage.sum()) - 100.))
            assert (cc.maintenance_actions == int(audit['actions'][:, t].sum())).all()
            count_table.append(dict(year=year, grade_counts=counts, total_units=sum(counts),
                                    percentage_sum=float(cc.percentage.sum()),
                                    maintenance_actions=int(audit['actions'][:, t].sum())))
        boundary_distance = float(np.min(np.abs(audit['scores'][:, :, None] - np.array([40., 60., 75., 90.]))))
        minimum_boundary_distance = min(minimum_boundary_distance, boundary_distance)
        assert boundary_distance > 1e-10
        audit['all_exported_unit_year_scores_bitwise_equal'] = True
        audit['all_exported_literal_actions_equal'] = True
        audit['all_strict_grades_counts_percentages_equal'] = True
        audit['grade4_and_grade5_counts_zero_every_year'] = all(r['grade_counts'][3:] == [0, 0] for r in count_table)
        audit['minimum_distance_from_any_internal_grade_boundary'] = boundary_distance
        audit['annual_composition'] = count_table
        del audit['actions'], audit['scores']
    preserved = preservation(project, args.preservation_baseline)
    report = clean(dict(
        audit_method='Independent scalar fixed-literal-action replay; no preparation/plot module imports, vector decoding, action selection, optimizer, or predictor fitting',
        checks_passed=True, initial_condition='LOCF', initial_state_year=2024,
        d=D, R=R, unit_count=N, years=YEARS,
        source_file_byte_copies_verified=len(provenance['copied_sources']),
        original_recurrence_engine_sha256=ENGINE_SHA,
        engine_scope='AST extract _inputs, resource_tolerance, simulate_actions only; bind HORIZON15 and YEARS2025..2039; recurrence unchanged',
        complete_saved_unit_year_state_archive_for_all_four_scenarios_present=False,
        unit_year_states_source='Exact fixed-action replay validated against original saved per-run and per-year metrics',
        unit_year_rows_checked=len(unit_year), composition_rows_checked=len(composition),
        boundary_tests=tests, invalid_boundary_inputs_rejected=True,
        classification_epsilon_used=False, classification_decimal_rounding_used=False,
        management_feasibility_epsilon_separate_from_grades=1e-8,
        maximum_percentage_sum_error=maximum_percent_error,
        minimum_score_distance_from_internal_boundaries=minimum_boundary_distance,
        no_reference_paper_numerical_values_used=True,
        scenarios=scenarios, preservation=preserved,
        output_sha256={name: sha(out / name) for name in ['condition_composition_by_year.csv', 'unit_year_scores.csv', 'scenario_selection.json']},
        limitations=[
            'The requested zero-action control fails the study management_count constraint from 2036; it is not claimed to be a feasible maintenance strategy.',
            'Only three saved finite-search feasible representatives are compared; no mathematical global optimality claim is made.',
            'All grade4/5 counts are genuinely zero for these four 15-year score scenarios.',
            'Score interval classes are model scenario results for detection units, not complete formal technical-condition certification or observed transition probabilities.',
            'This independent audit verifies data/provenance/preservation, not final image readability; visual QA is separate.']))
    destination = out / 'validation/independent_data_check.json'
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(dict(checks_passed=report['checks_passed'], unit_year_rows=report['unit_year_rows_checked'],
                         composition_rows=report['composition_rows_checked'], preservation=preserved,
                         maximum_percentage_sum_error=maximum_percent_error,
                         output=str(destination)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=Path, default=DEFAULT_PROJECT)
    ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument('--preservation-baseline', type=Path,
                    default=DEFAULT_BASELINE)
    run(ap.parse_args())
