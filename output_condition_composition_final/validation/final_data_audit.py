#!/usr/bin/env python3
"""Audit saved scores and fixed schedules for the final composition figure.

No predictor, state-generation script, schedule decoder, or optimizer is run.
All plotted counts are independently recomputed from the already saved scores.
Default inputs: sibling ../input_data when packaged, otherwise the previous
stage's output_condition_composition. External preservation is strict by
default; use --skip-external-preservation only outside the original workspace.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = (HERE.parent / 'input_data' if (HERE.parent / 'input_data').is_dir()
                  else Path('/workspace/output_condition_composition'))
DEFAULT_BASELINE = (HERE / 'preservation_baseline.json'
                    if (HERE / 'preservation_baseline.json').is_file()
                    else Path('/workspace/drawing3_work/preservation_baseline.json'))
YEARS = list(range(2025, 2040))
ORDER = ['no_maintenance', 'low_resource', 'medium_resource', 'high_resource']
EXPECTED_2039 = [[0, 54, 5, 0, 0], [19, 39, 1, 0, 0],
                 [40, 18, 1, 0, 0], [58, 1, 0, 0, 0]]
EXPECTED_TOTAL_ACTIONS = [0, 58, 93, 114]
N, D, R, MANAGEMENT_EPS = 59, 0.65, 6.0, 1e-8


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> pd.DataFrame:
    # Essential for preserving unrounded binary scores near class boundaries.
    return pd.read_csv(path, float_precision='round_trip')


def grade(score: float) -> int:
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(f'Score outside [0,100]: {score!r}')
    if score > 90:
        return 1
    if score > 75:
        return 2
    if score > 60:
        return 3
    if score > 40:
        return 4
    return 5


def boundary_tests() -> list[dict]:
    pairs = [(0., 5), (40., 5), (60., 4), (75., 3), (90., 2), (100., 1)]
    for threshold, lower, higher in [(40., 5, 4), (60., 4, 3),
                                      (75., 3, 2), (90., 2, 1)]:
        pairs.extend([(float(np.nextafter(threshold, -np.inf)), lower),
                      (float(np.nextafter(threshold, np.inf)), higher)])
    pairs += [(float(np.nextafter(0., np.inf)), 5),
              (float(np.nextafter(100., -np.inf)), 1)]
    result = []
    for score, expected in pairs:
        actual = grade(score)
        assert actual == expected, (score, actual, expected)
        result.append(dict(score=score, score_hex=score.hex(), expected=expected,
                           actual=actual, passed=True))
    for invalid in [float(np.nextafter(0., -np.inf)),
                    float(np.nextafter(100., np.inf)), -1., 101.,
                    float('nan'), float('inf'), -float('inf')]:
        try:
            grade(invalid)
        except ValueError:
            continue
        raise AssertionError(f'Invalid score accepted: {invalid}')
    return result


def close(value, expected, context):
    assert math.isclose(float(value), float(expected), rel_tol=0, abs_tol=1e-10), (
        context, value, expected)


def preservation(baseline_path: Path) -> dict:
    baseline = json.loads(baseline_path.read_text())
    previous = Path(baseline['previous_stage_root'])
    previous_actual = {str(p.relative_to(previous)): sha(p)
                       for p in sorted(previous.rglob('*')) if p.is_file()}
    assert previous_actual == baseline['previous_stage_file_tree_sha256'], (
        'Previous-stage tree changed, added files, or removed files',
        sorted(set(previous_actual) ^ set(baseline['previous_stage_file_tree_sha256'])),
        [name for name, value in baseline['previous_stage_file_tree_sha256'].items()
         if previous_actual.get(name) != value])
    originals = baseline['current_paper_and_original_figures']
    assert len(originals) == 29
    changed = [name for name, value in originals.items()
               if not Path(name).is_file() or sha(Path(name)) != value]
    assert not changed, ('Original manuscript / figures changed', changed)
    project = Path(baseline['scientific_project'])
    manifest = Path(baseline['frozen_manifest_path'])
    assert sha(manifest) == baseline['frozen_manifest_sha256']
    frozen = baseline['frozen_scientific_files']
    assert len(frozen) == 661
    assert json.loads(manifest.read_text())['files'] == frozen
    changed = [rel for rel, value in frozen.items()
               if not (project / rel).is_file() or sha(project / rel) != value]
    assert not changed, ('Frozen scientific input changed', changed)
    return dict(status='passed', baseline_sha256=sha(baseline_path),
                previous_stage_files_checked=len(previous_actual),
                previous_stage_whole_tree_unchanged=True,
                original_manuscript_and_figure_exports_checked=len(originals),
                original_manuscript_and_figure_exports_unchanged=True,
                frozen_scientific_files_checked=len(frozen),
                frozen_scientific_files_unchanged=True, changed_files=[])


def run(args) -> dict:
    source = args.source.resolve()
    frozen = source / 'source_data'
    baseline = json.loads(args.baseline.read_text())
    prior_hashes = baseline['previous_stage_file_tree_sha256']
    data_snapshot_paths = [source / name for name in
                           ['condition_composition_by_year.csv',
                            'unit_year_scores.csv', 'scenario_selection.json']]
    data_snapshot_paths += sorted(p for p in frozen.rglob('*') if p.is_file())
    for path in data_snapshot_paths:
        relative = str(path.relative_to(source))
        assert sha(path) == prior_hashes[relative], ('Previous-stage scientific data copy changed', relative)
    composition = read(source / 'condition_composition_by_year.csv')
    unit_year = read(source / 'unit_year_scores.csv')
    selection = json.loads((source / 'scenario_selection.json').read_text())
    provenance = json.loads((frozen / 'source_provenance.json').read_text())
    for name, row in provenance['copied_sources'].items():
        assert sha(frozen / name) == row['sha256'], ('Frozen source bytes', name)
    engine = provenance['original_engine']
    assert sha(frozen / engine['local_file']) == engine['sha256']
    # The historical engine is hashed for provenance, never imported/executed.
    init = read(frozen / 'initial_state_2024.csv')
    assert len(init) == N and init.unit_id.is_unique
    unit_order = init.unit_id.tolist()
    initial = init.LOCF_score.to_numpy(float)
    weights = init.area.to_numpy(float) / init.area.to_numpy(float).sum()
    parameters = read(frozen / 'Table_03_parameters_15y.csv').set_index('parameter').value
    common = dict(n_units=N, planning_horizon=15, year_start=2025, year_end=2039,
                  d=D, R=R, annual_capacity=8, min_gap=3, max_unit_actions=3)
    for name, expected in common.items():
        assert float(parameters[name]) == expected, (name, parameters[name], expected)
    assert selection['initial_condition'] == 'LOCF'
    assert selection['initial_state_year'] == 2024
    assert selection['n_units'] == N and selection['years'] == YEARS
    assert selection['d'] == D and selection['R'] == R
    assert selection['capacity'] == 8 and selection['min_gap'] == 3
    assert selection['max_actions_per_unit'] == 3
    assert selection['required_units_above75'] == 57
    assert selection['grade_intervals'] == {
        '1': '90 < S <= 100', '2': '75 < S <= 90', '3': '60 < S <= 75',
        '4': '40 < S <= 60', '5': '0 <= S <= 40'}
    selected = {entry['scenario']: entry for entry in selection['scenarios']}
    assert len(selected) == 4 and set(selected) == set(ORDER)
    assert len(composition) == 300 and len(unit_year) == 3540
    assert set(composition.scenario) == set(unit_year.scenario) == set(ORDER)
    assert not composition.duplicated(['scenario', 'year', 'grade']).any()
    assert not unit_year.duplicated(['scenario', 'year', 'unit_id']).any()
    assert set(composition.grade) == set(range(1, 6))
    assert np.isfinite(unit_year.score).all() and unit_year.score.between(0, 100).all()
    assert np.isin(unit_year.action, [0, 1]).all()
    for frame in (composition, unit_year):
        assert frame.year.isin(YEARS).all() and set(frame.year) == set(YEARS)
        assert set(frame.initial_condition) == {'LOCF'}
        assert (frame.d == D).all() and (frame.R == R).all()
    tests = boundary_tests()
    source_annual = read(frozen / 'resource_representative_annual_15y.csv')
    zero_annual = read(frozen / 'no_maintenance_baselines_annual_15y.csv')
    zero_annual = zero_annual[(zero_annual.initial_condition == 'LOCF') & (zero_annual.d == D)]
    source_summary = read(frozen / 'resource_level_summary_15y.csv')
    no_maintenance = read(frozen / 'no_maintenance_baselines_15y.csv')
    zero_summary = no_maintenance[(no_maintenance.initial_condition == 'LOCF') &
                                  (no_maintenance.d == D)].iloc[0]
    scenario_results, largest_percentage_error, minimum_boundary_distance = {}, 0., math.inf
    for index, name in enumerate(ORDER):
        entry = selected[name]
        assert entry['initial_condition'] == 'LOCF'
        assert entry['planning_horizon'] == 15
        assert entry['start_year'] == 2025 and entry['end_year'] == 2039
        assert entry['d'] == D and entry['R'] == R
        upart = unit_year[unit_year.scenario == name]
        cpart = composition[composition.scenario == name]
        assert set(upart.unit_id) == set(unit_order)
        assert set(upart.year) == set(cpart.year) == set(YEARS)
        assert len(upart) == 885 and len(cpart) == 75
        if name == 'no_maintenance':
            literal_actions = np.zeros((N, len(YEARS)), dtype=int)
            row = zero_summary
            actual_B = 0.
            run_id = 'fixed_zero_action_baseline'
            annual_source = zero_annual.sort_values('year')
            assert entry['run_id'] is None
        else:
            run_id = entry['run_id']
            archive_path = frozen / (run_id + '.json')
            archive = json.loads(archive_path.read_text())
            row = archive['row']
            literal_actions = np.asarray(archive['actions'], dtype=int)
            assert literal_actions.shape == (N, len(YEARS))
            assert np.isin(literal_actions, [0, 1]).all()
            assert row['feasible'] is True and row['schedule_replay_passed'] is True
            assert all(archive['replay_checks'].values())
            assert row['initial_condition'] == 'LOCF' and row['d'] == D
            assert row['planning_horizon'] == 15
            actual_B = float(row['B_limit'])
            assert row['B'] == actual_B == entry['B']
            saved_summary = source_summary[(source_summary.initial_condition == 'LOCF') &
                                           (source_summary.level_id == entry['level_id'])].iloc[0]
            assert saved_summary.best_run_id == run_id
            assert float(saved_summary.B_limit) == actual_B
            annual_source = source_annual[source_annual.run_id == run_id].sort_values('year')
        assert entry['B'] == actual_B
        assert (upart.B == actual_B).all() and (cpart.B == actual_B).all()
        assert set(upart.run_id) == set(cpart.run_id) == {run_id}
        assert annual_source.year.tolist() == YEARS
        scores, exported_actions, annual_report = [], [], []
        for year in YEARS:
            uc = upart[upart.year == year].set_index('unit_id').loc[unit_order]
            cc = cpart[cpart.year == year].set_index('grade').loc[list(range(1, 6))]
            assert len(uc) == N and len(cc) == 5
            assert np.array_equal(uc.initial_score.to_numpy(float), initial)
            values = uc.score.to_numpy(float)
            actions = uc.action.to_numpy(int)
            assert np.array_equal(actions, literal_actions[:, year - 2025])
            computed_grades = [grade(float(value)) for value in values]
            assert computed_grades == uc.grade.tolist()
            counts = [computed_grades.count(g) for g in range(1, 6)]
            assert counts == cc['count'].tolist() and sum(counts) == N
            expected_percent = np.asarray(counts, dtype=float) / N * 100
            assert np.allclose(cc.percentage, expected_percent, rtol=0, atol=1e-12)
            percentage_error = abs(float(cc.percentage.sum()) - 100.)
            assert percentage_error <= 1e-12
            largest_percentage_error = max(largest_percentage_error, percentage_error)
            assert (cc.maintenance_actions == int(actions.sum())).all()
            saved = annual_source[annual_source.year == year].iloc[0]
            close(values.mean(), saved.mean_score, f'{name} {year} saved annual mean')
            close(values.min(), saved.minimum_score, f'{name} {year} saved annual minimum')
            if name == 'no_maintenance':
                assert counts[0] == int(saved.grade1_count)
                assert counts[1] == int(saved.grade2_count)
            else:
                assert int(actions.sum()) == int(saved.maintenance_count)
                assert counts[0] + counts[1] == int(saved.good_count)
                close(float((actions * weights).sum()), saved.B_used,
                      f'{name} {year} saved annual resource')
            annual_report.append(dict(year=year, grade_counts=counts, total_units=N,
                                      percentage_sum=float(cc.percentage.sum()),
                                      maintenance_actions=int(actions.sum())))
            scores.append(values)
            exported_actions.append(actions)
        scores = np.asarray(scores).T
        actions = np.asarray(exported_actions).T
        # Check consistency between already saved neighboring states. This does
        # not generate new trajectories or modify any saved score or action.
        previous_saved = np.column_stack((initial, scores[:, :-1]))
        expected_neighbor = np.minimum(100., np.maximum(0., previous_saved - D) + R * actions)
        assert np.array_equal(scores, expected_neighbor)
        annual_counts = actions.sum(axis=0).tolist()
        total_actions = int(actions.sum())
        assert annual_counts == entry['annual_actions']
        assert total_actions == entry['total_actions'] == EXPECTED_TOTAL_ACTIONS[index]
        assert annual_report[-1]['grade_counts'] == EXPECTED_2039[index]
        assert (actions.sum(axis=0) <= 8).all()
        assert (actions.sum(axis=1) <= 3).all()
        gaps = [int(g) for act in actions for g in np.diff(np.flatnonzero(act))]
        assert all(g >= 3 for g in gaps)
        resource = float((actions * weights[:, None]).sum())
        assert resource <= actual_B + 1e-10 * max(1., actual_B)
        floor_ok = (scores > 60 + MANAGEMENT_EPS).all(axis=0)
        good_counts = (scores > 75 + MANAGEMENT_EPS).sum(axis=0)
        good_ok = good_counts >= 57
        feasible = bool(floor_ok.all() and good_ok.all())
        violations = np.flatnonzero(~(floor_ok & good_ok))
        first_violation = int(YEARS[violations[0]]) if len(violations) else None
        assert feasible == entry['feasible_management_strategy']
        if name == 'no_maintenance':
            assert not feasible and first_violation == 2036
            assert floor_ok.all() and not good_ok.all()
        else:
            assert feasible and first_violation is None
        close(resource, entry['B_used'], f'{name} resource')
        close(resource, row['resource'], f'{name} original source resource')
        close(scores.mean(), entry['J'], f'{name} J')
        close(scores.mean(), row['J'], f'{name} original source J')
        close(scores[:, -1].mean(), row['terminal_mean'], f'{name} terminal mean')
        close(scores.min(), row['minimum_score'], f'{name} minimum score')
        assert total_actions == int(row['maintenance_count'])
        assert int(good_counts.min()) == int(row['min_management_count'])
        grade45_zero = all(annual['grade_counts'][3:] == [0, 0] for annual in annual_report)
        assert grade45_zero
        boundary_distance = float(np.min(np.abs(scores[:, :, None] - np.array([40., 60., 75., 90.]))))
        minimum_boundary_distance = min(minimum_boundary_distance, boundary_distance)
        assert boundary_distance > 1e-10
        scenario_results[name] = dict(
            scenario_zh=entry['scenario_zh'], actual_B=actual_B,
            displayed_B_three_decimal_places=f'{actual_B:.3f}', B_used=resource,
            source_run_id=run_id, grade_counts_2039=annual_report[-1]['grade_counts'],
            annual_actions=annual_counts, total_actions=total_actions,
            saved_actions_match_literal_json=True,
            same_LOCF_initial_scores_for_every_unit=True,
            saved_neighboring_states_match_original_recurrence=True,
            all_unit_year_strict_grades_and_annual_counts_match=True,
            grade4_and_grade5_counts_zero_every_year=grade45_zero,
            J=float(scores.mean()), terminal_mean=float(scores[:, -1].mean()),
            min_score=float(scores.min()), minimum_units_above75=int(good_counts.min()),
            feasible_management_strategy=feasible,
            first_management_violation_year=first_violation,
            annual_capacity_max=int(actions.sum(axis=0).max()),
            unit_action_max=int(actions.sum(axis=1).max()),
            minimum_gap=min(gaps) if gaps else None,
            budget_constraint_satisfied=True, annual_composition=annual_report)
    preserved = (dict(status='explicitly_skipped', reason='--skip-external-preservation')
                 if args.skip_external_preservation else preservation(args.baseline))
    report = dict(
        checks_passed=True,
        audit_method='Read saved unit-year scores; recompute strict grades/counts/percentages; compare unchanged fixed actions to original literal JSON; no score regeneration, model fitting, schedule selection, decoding, or optimizer execution',
        source=str(source), unit_count=N, unit_year_rows_checked=len(unit_year),
        composition_rows_checked=len(composition), years=YEARS,
        initial_condition='LOCF', initial_state_year=2024, d=D, R=R,
        grade_intervals=selection['grade_intervals'],
        classification_epsilon_used=False, classification_decimal_rounding_used=False,
        boundary_tests=tests, invalid_boundary_inputs_rejected=True,
        management_feasibility_epsilon_separate_from_grades=MANAGEMENT_EPS,
        maximum_percentage_sum_error=largest_percentage_error,
        minimum_score_distance_to_internal_grade_boundary=minimum_boundary_distance,
        frozen_source_byte_copies_verified=len(provenance['copied_sources']),
        all_packaged_scientific_input_bytes_match_previous_stage=True,
        packaged_scientific_input_files_verified=len(data_snapshot_paths),
        historical_original_engine_byte_hash_verified_but_never_executed=True,
        all_grade4_and_grade5_counts_zero=True, scenarios=scenario_results,
        scientific_input_hashes={name: sha(source / name) for name in
                                 ['condition_composition_by_year.csv',
                                  'unit_year_scores.csv', 'scenario_selection.json']},
        preservation=preserved,
        limitations=[
            'The zero-action comparison fails the management constraint from 2036; it is not a feasible maintenance schedule.',
            'The score classes are model simulation score intervals for 59 detection units, not 59 independent bridges, formal technical-condition certification, or Markov transition probabilities.',
            'The three saved finite-search resource representatives are preserved; global optimality or an optimal real-world budget is not established.',
            'Composition has threshold sensitivity and does not fully show continuous within-class score differences.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(checks_passed=True, report=str(args.output),
                         grade_counts_2039={name: r['grade_counts_2039'] for name, r in scenario_results.items()},
                         preservation=preserved), ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=HERE / 'final_data_audit.json')
    parser.add_argument('--baseline', type=Path, default=DEFAULT_BASELINE)
    parser.add_argument('--skip-external-preservation', action='store_true',
                        help='Only outside original workspace; skips external manuscript/project/tree hashes, not scientific-data checks')
    run(parser.parse_args())
