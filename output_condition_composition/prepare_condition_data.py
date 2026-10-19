#!/usr/bin/env python3
"""Replay four already fixed 15-year scenarios and count score intervals.

No prediction model is fitted, no optimizer is imported/run, and no action is
changed. Inputs are the original LOCF scores, area and three archived literal
59 x 15 action matrices. The historical original audit recurrence is extracted
by AST, with only horizon/year globals configured for the saved 15-year run.
An independent scalar recurrence must match every reconstructed score exactly.

Run from anywhere: python prepare_condition_data.py [--output-dir DIRECTORY]
Dependencies: Python >=3.10, numpy, pandas. All input paths are bundle-relative.
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

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'source_data'
YEARS = tuple(range(2025, 2040))
D = 0.65
R = 6.0
EPS_MANAGEMENT = 1e-8  # Original feasibility audit only; NEVER grade membership.
SCENARIOS = (
    ('no_maintenance', '无养护', None),
    ('low_resource', '低资源养护', 1),
    ('medium_resource', '中等资源养护', 3),
    ('high_resource', '高资源养护', 6),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(name):
    # Round-trip preserves the binary doubles stored in the scientific CSVs.
    return pd.read_csv(SOURCE / name, float_precision='round_trip')


def json_write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def grade_of(scores):
    """Exact interval boundaries; no rounding, tolerance, or score correction."""
    values = np.asarray(scores, dtype=float)
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 100)):
        raise AssertionError('Classification requires finite scores in [0,100].')
    return np.select([values > 90, values > 75, values > 60, values > 40],
                     [1, 2, 3, 4], default=5).astype(int)


def original_recurrence():
    """Load only non-search original audit functions, without importing Numba.

    The historical original engine is copied byte for byte. Its only configured
    change is the planning horizon/year vector already present in the selected
    final run metadata. This does not truncate/redecode 20-year decisions:
    literal actions are the stored 59 x 15 matrices from the final 15-year runs.
    """
    source = (SOURCE / 'original_area_model_stage7.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    allowed = {'_inputs', 'resource_tolerance', 'simulate_actions'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in allowed]
    assert len(nodes) == 3
    minimal = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    scope = dict(np=np, HORIZON=15, YEARS=YEARS, K=3, CAPACITY=8,
                 MIN_GAP=3, REQUIRED_GOOD=57, EPS=EPS_MANAGEMENT, R=R)
    exec(compile(minimal, 'original_area_model_stage7.py:selected_audit_functions', 'exec'), scope)
    return scope['simulate_actions']


def scalar_recurrence(initial, actions):
    """Independent per-unit/per-year check of the unchanged state equation."""
    result = np.empty((59, 15), dtype=float)
    for i in range(59):
        value = float(initial[i])
        for t in range(15):
            value = min(100.0, max(0.0, value - D) + R * int(actions[i, t]))
            result[i, t] = value
    return result


def compare_number(actual, expected, context):
    if expected is None or pd.isna(expected):
        assert actual is None or pd.isna(actual), (context, actual, expected)
    elif isinstance(expected, (bool, np.bool_)):
        assert bool(actual) == bool(expected), (context, actual, expected)
    elif isinstance(expected, str):
        assert str(actual) == expected, (context, actual, expected)
    else:
        assert np.isclose(float(actual), float(expected), rtol=0, atol=1e-10), (context, actual, expected)


def prepare(output_dir=None):
    output = Path(output_dir) if output_dir else HERE
    output.mkdir(parents=True, exist_ok=True)
    (output / 'validation').mkdir(exist_ok=True)
    source_hashes = {str(p.relative_to(SOURCE)): sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    provenance = json.loads((SOURCE / 'source_provenance.json').read_text(encoding='utf-8'))
    for name, item in provenance['copied_sources'].items():
        assert sha(SOURCE / name) == item['sha256'], f'Frozen input modified: {name}'
    assert sha(SOURCE / provenance['original_engine']['local_file']) == provenance['original_engine']['sha256']

    source = read_csv('initial_state_2024.csv')
    assert len(source) == 59 and source.unit_id.is_unique
    initial = source.LOCF_score.to_numpy(float)
    area = source.area.to_numpy(float)
    weights = area / area.sum()
    assert np.isfinite(initial).all() and np.isfinite(weights).all() and np.all(weights > 0)
    summaries = read_csv('resource_level_summary_15y.csv')
    all_runs = read_csv('resource_level_runs_15y.csv')
    annual_saved = read_csv('resource_representative_annual_15y.csv')
    baseline_annual = read_csv('no_maintenance_baselines_annual_15y.csv')
    baseline_saved = read_csv('no_maintenance_baselines_15y.csv')
    replay = original_recurrence()

    # Exact boundary examples, including adjacent representable floats.
    boundary_values = np.array([0.0, 40.0, np.nextafter(40.0, np.inf), 60.0,
                               np.nextafter(60.0, np.inf), 75.0,
                               np.nextafter(75.0, np.inf), 90.0,
                               np.nextafter(90.0, np.inf), 100.0])
    expected_grades = [5, 5, 4, 4, 3, 3, 2, 2, 1, 1]
    assert grade_of(boundary_values).tolist() == expected_grades
    units, composition, selection, audits, close_boundaries = [], [], [], [], []

    for scenario, scenario_zh, level in SCENARIOS:
        run_id = None
        seed = None
        original_row = None
        if level is None:
            B = 0.0
            actions = np.zeros((59, 15), dtype=np.int8)
            rows = baseline_saved[(baseline_saved.initial_condition == 'LOCF') & (baseline_saved.d == D)]
            assert len(rows) == 1
            original_row = rows.iloc[0].to_dict()
            annual_reference = baseline_annual[(baseline_annual.initial_condition == 'LOCF') & (baseline_annual.d == D)].sort_values('year')
            selection_reason = 'Fixed zero-action baseline already evaluated in the final 15-year model; B=0 denotes this baseline, not an additional optimized resource level.'
            action_source = 'Fixed all-zero action matrix; same model baseline in no_maintenance_baselines_15y.csv and no_maintenance_baselines_annual_15y.csv.'
        else:
            chosen = summaries[(summaries.initial_condition == 'LOCF') & (summaries.level_id == level)]
            assert len(chosen) == 1
            chosen = chosen.iloc[0]
            B = float(chosen.B_limit)
            run_id = str(chosen.best_run_id)
            stored = json.loads((SOURCE / f'{run_id}.json').read_text(encoding='utf-8'))
            original_row = stored['row']
            seed = int(original_row['seed'])
            for key, value in dict(planning_horizon=15, start_year=2025, end_year=2039,
                                   initial_condition='LOCF', d=D, B_limit=B, level_id=level,
                                   feasible=True, schedule_replay_passed=True).items():
                assert original_row[key] == value, (scenario, key, original_row[key], value)
            assert all(stored['replay_checks'].values())
            actions = np.asarray(stored['actions'])
            assert actions.shape == (59, 15) and np.isin(actions, [0, 1]).all()
            actions = actions.astype(np.int8)
            candidates = all_runs[(all_runs.initial_condition == 'LOCF') & (all_runs.level_id == level)]
            assert len(candidates) == 30 and candidates.feasible.all()
            # Confirm the saved best identifier and original tie rule without
            # solving, adjusting or choosing a different action schedule.
            best_J = float(candidates.J.max())
            tied = candidates[best_J - candidates.J <= 1e-10]
            expected = tied.sort_values(['B_used', 'seed'], kind='stable').iloc[0]
            assert str(expected.run_id) == run_id, (scenario, expected.run_id, run_id)
            assert int(chosen.best_seed) == seed
            annual_reference = annual_saved[annual_saved.run_id == run_id].sort_values('year')
            selection_reason = 'Use the final summary best_run_id from the 30 independent feasible GJO runs at this saved resource level: highest feasible J; ties within 1e-10 use lower B_used, then lower seed. This is a finite-search representative, not a mathematical global optimum.'
            action_source = f'{run_id}.json: actions (literal archived 59 x 15 matrix).'

        report = replay(initial, weights, actions, D, B)
        scores = report['scores']
        assert np.array_equal(scores, scalar_recurrence(initial, actions)), f'Independent scalar replay mismatch: {scenario}'
        assert np.array_equal(actions, report['actions'])
        grades = grade_of(scores)
        assert scores.shape == (59, 15) and np.array_equal(grades, report['grades'])
        metrics = report['metrics']
        # Every available original scalar recurrence metric is checked. Aliases
        # and improved performance statistics are intentionally not estimated.
        metric_checks = []
        for key, actual in metrics.items():
            if key in original_row:
                compare_number(actual, original_row[key], f'{scenario}.{key}')
                metric_checks.append(key)
        compare_number(metrics['resource'], original_row['B_used'], f'{scenario}.B_used')
        assert len(annual_reference) == 15 and annual_reference.year.tolist() == list(YEARS)
        annual_count = actions.sum(axis=0)
        annual_resources = (actions * weights[:, None]).sum(axis=0)
        cumulative = np.cumsum(annual_resources)
        annual_checks = []
        for t, (_, saved) in enumerate(annual_reference.iterrows()):
            good = int((scores[:, t] > 75).sum())
            manage = int((scores[:, t] > 75 + EPS_MANAGEMENT).sum())
            values = dict(mean_score=float(scores[:, t].mean()), minimum_score=float(scores[:, t].min()),
                          good_count=good, management_count=manage, maintenance_count=int(annual_count[t]),
                          cumulative_resource=float(cumulative[t]))
            if 'good_ratio' in saved.index:
                values['good_ratio'] = good / 59
            if level is None:
                values.update(grade1_count=int((grades[:, t] == 1).sum()),
                              grade2_count=int((grades[:, t] == 2).sum()), resource=float(annual_resources[t]))
            else:
                values['B_used'] = float(annual_resources[t])
            for key, actual in values.items():
                compare_number(actual, saved[key], f'{scenario}.{YEARS[t]}.{key}')
            annual_checks.append({'year': YEARS[t], 'fields_checked': list(values)})

        structural = bool(np.all(annual_count <= 8) and np.all(actions.sum(axis=1) <= 3) and
                          all(np.all(np.diff(np.flatnonzero(row)) >= 3) for row in actions))
        bounds_ok = bool(np.all(scores > 60))
        good_ok = bool(np.all((scores > 75).sum(axis=0) >= 57))
        original_manage_ok = bool(np.all((scores > 75 + EPS_MANAGEMENT).sum(axis=0) >= 57))
        resource_ok = bool(metrics['resource'] <= B + 1e-10 * max(1, B))
        if level is not None:
            assert metrics['feasible'] and structural and bounds_ok and good_ok and original_manage_ok and resource_ok
        # An infeasible zero-action comparison remains a valid baseline. Do not
        # silently label it a feasible management strategy or alter its actions.
        if level is None:
            assert not metrics['feasible'] and metrics['first_violation_year'] == 2036
            assert metrics['violation_types'] == 'management_count'

        for t, year in enumerate(YEARS):
            for i, row in source.iterrows():
                score = float(scores[i, t])
                units.append(dict(scenario=scenario, scenario_zh=scenario_zh, B=B,
                                  initial_condition='LOCF', d=D, R=R,
                                  run_id=run_id or 'fixed_zero_action_baseline',
                                  unit_id=str(row.unit_id), year=year,
                                  initial_score=float(initial[i]), score=score,
                                  action=int(actions[i, t]), grade=int(grades[i, t])))
                for boundary in (40.0, 60.0, 75.0, 90.0):
                    if abs(score - boundary) <= 1e-10:
                        close_boundaries.append(dict(scenario=scenario, unit_id=str(row.unit_id), year=year,
                                                     score_repr=repr(score), score_hex=score.hex(),
                                                     nearest_boundary=boundary, exact_boundary=bool(score == boundary),
                                                     grade=int(grades[i, t]), adjusted=False))
            counts = [int((grades[:, t] == grade).sum()) for grade in range(1, 6)]
            percentages = [n / 59 * 100 for n in counts]
            assert sum(counts) == 59 and abs(sum(percentages) - 100) < 1e-12
            for grade, count, percentage in zip(range(1, 6), counts, percentages):
                composition.append(dict(scenario=scenario, scenario_zh=scenario_zh, B=B, year=year,
                                        grade=grade, count=count, percentage=percentage,
                                        maintenance_actions=int(annual_count[t]),
                                        initial_condition='LOCF', d=D, R=R,
                                        run_id=run_id or 'fixed_zero_action_baseline'))

        first_bad = [year for t, year in enumerate(YEARS) if (scores[:, t] > 75 + EPS_MANAGEMENT).sum() < 57]
        selection.append(dict(scenario=scenario, scenario_zh=scenario_zh, level_id=level, B=B,
                              B_used=float(metrics['resource']), run_id=run_id,
                              seed=seed, initial_condition='LOCF', planning_horizon=15,
                              start_year=2025, end_year=2039, d=D, R=R,
                              action_source=action_source, selection_reason=selection_reason,
                              feasible_management_strategy=bool(metrics['feasible']),
                              annual_actions=annual_count.astype(int).tolist(),
                              total_actions=int(actions.sum()), min_score=float(scores.min()),
                              minimum_grade12_count=int((scores > 75).sum(axis=0).min()),
                              first_management_violation_year=first_bad[0] if first_bad else None,
                              J=float(scores.mean()), terminal_mean=float(scores[:, -1].mean()),
                              scores_source='Exact fixed-action replay of archived final model results; original recurrence and independent scalar recurrence agree at every unit/year.',
                              action_sha256=hashlib.sha256(actions.tobytes()).hexdigest(),
                              score_sha256=hashlib.sha256(scores.tobytes()).hexdigest()))
        audits.append(dict(scenario=scenario, archived_scalar_metrics_checked=metric_checks,
                           archived_annual_records_checked=annual_checks,
                           all_scores_exactly_match_independent_scalar_replay=True,
                           actions_identical_to_archived_actions=True,
                           original_feasible=bool(metrics['feasible']),
                           max_annual_actions=int(annual_count.max()), max_unit_actions=int(actions.sum(axis=1).max()),
                           min_action_gap=None if pd.isna(metrics['min_gap']) else int(metrics['min_gap']),
                           structural_constraints_passed=structural, resource_constraint_passed=resource_ok,
                           strict_all_scores_above60_passed=bounds_ok,
                           strict_57_of59_above75_every_year_passed=good_ok,
                           original_eps_management_constraint_passed=original_manage_ok,
                           baseline_constraint_violation_retained=(level is None),
                           first_violation_year=first_bad[0] if first_bad else None))

    frame_units = pd.DataFrame(units)
    frame_composition = pd.DataFrame(composition)
    assert len(frame_units) == 4 * 59 * 15 == 3540
    assert len(frame_composition) == 4 * 15 * 5 == 300
    assert not frame_units.duplicated(['scenario', 'unit_id', 'year']).any()
    assert not frame_composition.duplicated(['scenario', 'year', 'grade']).any()
    frame_units.to_csv(output / 'unit_year_scores.csv', index=False, encoding='utf-8-sig')
    frame_composition.to_csv(output / 'condition_composition_by_year.csv', index=False, encoding='utf-8-sig')
    json_write(output / 'scenario_selection.json', {
        'initial_condition': 'LOCF', 'initial_state_year': 2024, 'n_units': 59,
        'years': list(YEARS), 'd': D, 'R': R,
        'capacity': 8, 'min_gap': 3, 'max_actions_per_unit': 3,
        'required_units_above75': 57,
        'resource_meaning': 'Cumulative treated area share relative to total network area; not currency.',
        'recurrence': 'S_it = min(100, max(0, S_i,t-1 - d) + R*a_it); annual end-of-year score after actions.',
        'grade_intervals': {'1': '90 < S <= 100', '2': '75 < S <= 90', '3': '60 < S <= 75',
                            '4': '40 < S <= 60', '5': '0 <= S <= 40'},
        'scenarios': selection,
        'limitations': ['Fixed zero-action baseline violates the research management constraint from 2036; retained as the requested no-maintenance comparison, not a feasible strategy.',
                        'The three maintenance representatives are selected finite-search results, not mathematical global optima.',
                        'Score interval composition is model scenario output for detection units, not formal bridge condition certification or measured transition probabilities.']})
    assert source_hashes == {str(p.relative_to(SOURCE)): sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    audit = {
        'all_data_checks_passed': True,
        'all_maintenance_representatives_feasible': True,
        'no_maintenance_baseline_is_feasible': False,
        'baseline_management_violation_is_reported_not_hidden': True,
        'data_source': 'Original final 15-year model inputs, archived literal actions and saved scalar/annual results.',
        'full_unit_score_archive_available_in_compact_project': False,
        'scores_exactly_replayed_from_original_actions': True,
        'original_recurrence_source': provenance['original_engine'],
        'source_hashes_unchanged': source_hashes,
        'rows_unit_scores': len(frame_units), 'rows_composition': len(frame_composition),
        'year_count': 15, 'scenario_count': 4, 'units_per_scenario_year': 59,
        'every_scenario_year_count_sum_59': True, 'every_scenario_year_percentage_sum_100': True,
        'percentage_tolerance': 1e-12,
        'grade_membership_tolerance': 0, 'grade_scores_rounded_before_classification': False,
        'boundary_test_cases': [{'score_repr': repr(float(x)), 'grade': int(g)} for x, g in zip(boundary_values, expected_grades)],
        'near_boundary_values_preserved': close_boundaries,
        'original_feasibility_score_epsilon': EPS_MANAGEMENT,
        'original_feasibility_epsilon_used_for_grades': False,
        'original_metric_comparison_absolute_tolerance': 1e-10,
        'reference_paper_numeric_values_used': 0,
        'new_prediction_model_fits': 0, 'new_GJO_runs': 0,
        'existing_action_changes': 0, 'score_smoothing': False,
        'per_scenario': audits,
        'output_sha256': {'unit_year_scores.csv': sha(output / 'unit_year_scores.csv'),
                          'condition_composition_by_year.csv': sha(output / 'condition_composition_by_year.csv'),
                          'scenario_selection.json': sha(output / 'scenario_selection.json')},
    }
    json_write(output / 'validation/replay_audit.json', audit)
    print(f'PASS: {len(frame_units)} exact unit/year scores; {len(frame_composition)} grade-composition rows; no training/optimization.')
    for item in selection:
        print(f"{item['scenario']}: B={item['B']!r}, B_used={item['B_used']!r}, actions={item['total_actions']}, feasible_strategy={item['feasible_management_strategy']}")
    return frame_composition


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE)
    args = parser.parse_args()
    prepare(args.output_dir)
