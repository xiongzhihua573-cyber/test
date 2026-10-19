"""Area-share resource model, stage 6.

Every admitted action uses its unit area share, independently of its score.
B is cumulative equivalent whole-network treated area; J is unit-weighted.
There is no currency multiplier, discount, or score-dependent resource factor.
The search path is compiled and the action audit uses separate Python code.
"""
from __future__ import annotations

import numpy as np
from numba import njit

HORIZON = 20
YEARS = tuple(range(2025, 2045))
K = 3
CAPACITY = 8
MIN_GAP = 3
REQUIRED_GOOD = 57
EPS = 1e-8
R = 6.0
RULE_THRESHOLDS = tuple(range(76, 91, 2))
MODES = ("min_resource", "max_state", "budgeted")


def resource_tolerance(budget):
    return 1e-10 * max(1.0, float(budget))


def normalize_area(area):
    area = np.asarray(area, dtype=float)
    if area.ndim != 1 or not np.isfinite(area).all() or np.any(area <= 0):
        raise ValueError("Areas must be finite and positive.")
    return area / area.sum()


def action_resource(pre_scores, weights):
    """Area-share action resources; pre_scores is retained for API compatibility."""
    return np.asarray(weights, dtype=float).copy()


def _inputs(initial, weights, d):
    initial = np.asarray(initial, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if initial.ndim != 1 or weights.shape != initial.shape or initial.size == 0:
        raise ValueError("Initial scores and weights must be matching vectors.")
    if not np.isfinite(initial).all() or np.any((initial < 0) | (initial > 100)):
        raise ValueError("Initial scores must lie in [0,100].")
    if not np.isfinite(weights).all() or np.any(weights <= 0) or not np.isclose(weights.sum(), 1.0, rtol=0, atol=1e-10):
        raise ValueError("Positive area weights must sum to one.")
    if not np.isfinite(d) or d < 0:
        raise ValueError("Annual condition-score decrease must be finite and nonnegative.")
    return np.ascontiguousarray(initial), np.ascontiguousarray(weights), float(d)


def _mode(mode, budget):
    if mode not in MODES:
        raise ValueError(f"Mode must be one of {MODES}.")
    if mode == "budgeted":
        if budget is None or not np.isfinite(budget) or budget < 0:
            raise ValueError("Budgeted mode requires a finite nonnegative resource limit.")
        return True, float(budget), False
    # Explicitly ignore an otherwise supplied limit in the two auxiliary modes.
    return False, 0.0, mode == "min_resource"


@njit(cache=True)
def decode_requests(vector, n):
    requests = np.zeros((n, HORIZON), dtype=np.bool_)
    for i in range(n):
        slots = np.empty(K, dtype=np.int64)
        for k in range(K):
            slots[k] = min(HORIZON, int(np.floor((HORIZON + 1) * vector[i * K + k])))
        slots.sort()
        last = -100
        for k in range(K):
            year = slots[k]
            if year > 0 and year - last >= MIN_GAP:
                requests[i, year - 1] = True
                last = year
    return requests


@njit(cache=True)
def _evaluate_fast(vector, initial, weights, d, bounded, budget, minimize_resource):
    n = len(initial)
    for coordinate in vector:
        if not np.isfinite(coordinate) or coordinate < 0.0 or coordinate > 1.0:
            raise ValueError("Decision coordinates must be finite and lie in [0,1].")
    requests = decode_requests(vector, n)
    states = initial.copy()
    total_score = 0.0
    resource = 0.0
    minimum = 100.0
    minimum_management = n
    candidates = np.empty(n, dtype=np.int64)
    for t in range(HORIZON):
        count = 0
        for i in range(n):
            states[i] = max(0.0, states[i] - d)
            if requests[i, t]:
                # Low score first, then stable index; refused requests do not move.
                j = count
                while j > 0:
                    other = candidates[j - 1]
                    if states[other] < states[i] or (states[other] == states[i] and other < i):
                        break
                    candidates[j] = other
                    j -= 1
                candidates[j] = i
                count += 1
        for j in range(min(CAPACITY, count)):
            i = candidates[j]
            resource += weights[i]
            states[i] = min(100.0, states[i] + R)
        management = 0
        for i in range(n):
            total_score += states[i]
            minimum = min(minimum, states[i])
            if states[i] > 75.0 + EPS:
                management += 1
        minimum_management = min(minimum_management, management)
    floor_ok = minimum > 60.0 + EPS
    resource_ok = True
    resource_violation = 0.0
    if bounded:
        tolerance = 1e-10 * max(1.0, budget)
        resource_ok = resource <= budget + tolerance
        if not resource_ok:
            if budget == 0.0:
                # Explicit zero-limit branch, never divide by zero.
                resource_violation = resource
            else:
                resource_violation = max(0.0, resource / budget - 1.0)
    floor_violation = 0.0
    if not floor_ok:
        floor_violation = max(EPS, 60.0 + EPS - minimum) / 40.0
    violation = floor_violation + max(0.0, (REQUIRED_GOOD - minimum_management) / REQUIRED_GOOD) + resource_violation
    feasible = floor_ok and minimum_management >= REQUIRED_GOOD and resource_ok
    J = total_score / (n * HORIZON)
    utility = -resource if minimize_resource else J
    return feasible, violation, utility, resource


def compile_worker():
    """Compile the fixed Numba signature without performing any evaluation."""
    from numba import types
    vector_type = types.float64[::1]
    _evaluate_fast.compile((vector_type, vector_type, vector_type, types.float64,
                            types.boolean, types.float64, types.boolean))


def evaluator(initial, weights, d=0.65, mode="budgeted", budget=None):
    """Prevalidate fixed inputs and return the compiled optimizer callable."""
    initial, weights, d = _inputs(initial, weights, d)
    bounded, limit, minimize_resource = _mode(mode, budget)
    dimension = initial.size * K

    def evaluate_vector(vector):
        vector = np.asarray(vector, dtype=float)
        if vector.ndim != 1 or vector.size != dimension:
            raise ValueError(f"Decision vector must contain {dimension} coordinates.")
        return _evaluate_fast(vector, initial, weights, d, bounded, limit, minimize_resource)

    return evaluate_vector


def evaluate(vector, initial, weights, d=0.65, mode="budgeted", budget=None):
    """Return (feasible, violation, utility, resource); minimum-resource utility is -B."""
    return evaluator(initial, weights, d, mode, budget)(vector)


def decode_independent(vector, n):
    """Pure Python decoder, independent of the compiled search decoder."""
    vector = np.asarray(vector, dtype=float)
    if vector.shape != (n * K,) or not np.isfinite(vector).all() or np.any((vector < 0) | (vector > 1)):
        raise ValueError("Decision vector must have n*K finite coordinates in [0,1].")
    requests = np.zeros((n, HORIZON), dtype=bool)
    for i, row in enumerate(vector.reshape(n, K)):
        years = sorted(set(min(HORIZON, int(np.floor((HORIZON + 1) * float(v)))) for v in row))
        accepted = []
        for year in years:
            if year > 0 and (not accepted or year - accepted[-1] >= MIN_GAP):
                accepted.append(year)
        for year in accepted:
            requests[i, year - 1] = True
    return requests


def encode_schedule(actions):
    actions = np.asarray(actions, dtype=bool)
    if actions.ndim != 2 or actions.shape[1] != HORIZON or np.any(actions.sum(axis=1) > K):
        raise ValueError("Action matrix must have 20 years and at most K actions per unit.")
    vector = np.zeros((actions.shape[0], K))
    for i, row in enumerate(actions):
        years = np.flatnonzero(row) + 1
        for j, year in enumerate(years):
            vector[i, j] = (float(year) + 0.5) / (HORIZON + 1)
    return vector.ravel()


def simulate_actions(initial, weights, actions, d=0.65, budget=None):
    """Audit literal actions without cancellation, decoding, or optimization.

    This recurrence and resource calculation do not call the compiled evaluator.
    Invalid capacity, gap and frequency are retained and reported as violations.
    """
    initial, weights, d = _inputs(initial, weights, d)
    raw_actions = np.asarray(actions)
    if raw_actions.shape != (len(initial), HORIZON) or not np.isin(raw_actions, [0, 1]).all():
        raise ValueError("Actions must be a binary n-by-20 matrix.")
    actions = raw_actions.astype(bool, copy=True)
    if budget is not None and (not np.isfinite(budget) or budget < 0):
        raise ValueError("Resource limit must be finite and nonnegative, or None.")
    scores = np.empty(actions.shape, dtype=float)
    pre_scores = np.empty_like(scores)
    resources = np.zeros_like(scores)
    state = initial.copy()
    for t in range(HORIZON):
        before = np.maximum(0.0, state - d)
        pre_scores[:, t] = before
        # Independent expression, deliberately not action_resource or fast core.
        resources[:, t] = actions[:, t] * weights
        state = np.minimum(100.0, before + 6.0 * actions[:, t])
        scores[:, t] = state
    grades = np.select([scores > 90, scores > 75, scores > 60, scores > 40], [1, 2, 3, 4], default=5)
    good = (grades <= 2).sum(axis=0)
    management = (scores > 75.0 + EPS).sum(axis=0)
    floor = scores > 60.0 + EPS
    counts = actions.sum(axis=0)
    per_unit = actions.sum(axis=1)
    gaps = [int(g) for row in actions for g in np.diff(np.flatnonzero(row))]
    structural = bool(np.all(counts <= CAPACITY) and np.all(per_unit <= K) and all(g >= MIN_GAP for g in gaps))
    resource = float(resources.sum())
    tolerance = resource_tolerance(budget) if budget is not None else 0.0
    resource_ok = budget is None or resource <= budget + tolerance
    feasible = bool(floor.all() and np.all(management >= REQUIRED_GOOD) and structural and resource_ok)
    minimum = float(scores.min())
    violation = 0.0 if floor.all() else max(EPS, 60.0 + EPS - minimum) / 40.0
    violation += max(0.0, (REQUIRED_GOOD - int(management.min())) / REQUIRED_GOOD)
    if not resource_ok:
        violation += resource if budget == 0 else max(0.0, resource / budget - 1.0)
    violation += float(np.maximum(counts - CAPACITY, 0).sum()) / (CAPACITY * HORIZON)
    violation += float(np.maximum(per_unit - K, 0).sum()) / (len(initial) * K)
    violation += sum(max(0, MIN_GAP - g) / MIN_GAP for g in gaps)
    violations = []
    cumulative = resources.sum(axis=0).cumsum()
    for t, year in enumerate(YEARS):
        if not floor[:, t].all():
            violations.append((year, "minimum_score"))
        if management[t] < REQUIRED_GOOD:
            violations.append((year, "management_count"))
        if counts[t] > CAPACITY:
            violations.append((year, "annual_capacity"))
        if budget is not None and cumulative[t] > budget + tolerance:
            violations.append((year, "resource_limit"))
    for row in actions:
        years = np.flatnonzero(row)
        if len(years) > K:
            violations.append((YEARS[int(years[K])], "unit_frequency"))
        for first, second in zip(years[:-1], years[1:]):
            if second - first < MIN_GAP:
                violations.append((YEARS[int(second)], "maintenance_interval"))
    metrics = dict(feasible=feasible, violation=float(violation), J=float(scores.mean()), resource=resource,
                   terminal_mean=float(scores[:, -1].mean()), minimum_score=minimum,
                   min_good_count=int(good.min()), min_good_ratio=float(good.min() / len(initial)),
                   min_management_count=int(management.min()), maintenance_count=int(actions.sum()),
                   annual_mean_count=float(actions.sum() / HORIZON), max_annual_count=int(counts.max()),
                   max_unit_count=int(per_unit.max()), min_gap=min(gaps) if gaps else np.nan,
                   first_violation_year=min(v[0] for v in violations) if violations else np.nan,
                   violation_types=";".join(sorted(set(v[1] for v in violations))))
    return dict(scores=scores, pre_scores=pre_scores, actions=actions, resources=resources,
                grades=grades, good_counts=good, management_counts=management, metrics=metrics)


def simulate_vector(vector, initial, weights, d=0.65, mode="budgeted", budget=None):
    initial, weights, d = _inputs(initial, weights, d)
    bounded, limit, minimize_resource = _mode(mode, budget)
    requests = decode_independent(vector, len(initial))
    actions = np.zeros_like(requests)
    state = initial.copy()
    for t in range(HORIZON):
        before = np.maximum(0.0, state - d)
        selected = sorted(np.flatnonzero(requests[:, t]).tolist(), key=lambda i: (before[i], i))[:CAPACITY]
        actions[selected, t] = True
        state = np.minimum(100.0, before + R * actions[:, t])
    report = simulate_actions(initial, weights, actions, d, limit if bounded else None)
    report["requests"] = requests
    report["metrics"]["utility"] = -report["metrics"]["resource"] if minimize_resource else report["metrics"]["J"]
    return report


def audit_vector(vector, initial, weights, d=0.65, mode="budgeted", budget=None):
    report = simulate_vector(vector, initial, weights, d, mode, budget)
    fast = evaluate(vector, initial, weights, d, mode, budget)
    metrics = report["metrics"]
    if bool(fast[0]) != metrics["feasible"] or not np.allclose(
        fast[1:], [metrics["violation"], metrics["utility"], metrics["resource"]], rtol=1e-10, atol=1e-9
    ):
        raise AssertionError("Compiled evaluation and independent action audit disagree.")
    return report


def rule_seed(initial, weights, d=0.65, mode="budgeted", budget=None):
    """Eight frozen low-score-first rules; select by the current task objective."""
    initial, weights, d = _inputs(initial, weights, d)
    bounded, limit, _ = _mode(mode, budget)
    rows, vectors = [], []
    for threshold in RULE_THRESHOLDS:
        states = initial.copy()
        actions = np.zeros((len(initial), HORIZON), dtype=bool)
        used = np.zeros(len(initial), dtype=int)
        last = np.full(len(initial), -100)
        total_resource = 0.0
        for t in range(HORIZON):
            before = np.maximum(0.0, states - d)
            candidates = sorted([i for i in range(len(initial)) if before[i] < threshold and used[i] < K and t - last[i] >= MIN_GAP], key=lambda i: (before[i], i))
            admitted = 0
            for i in candidates:
                if admitted >= CAPACITY:
                    break
                resource = weights[i]
                if not bounded or total_resource + resource <= limit + resource_tolerance(limit):
                    actions[i, t] = True
                    used[i] += 1
                    last[i] = t
                    total_resource += resource
                    admitted += 1
            states = np.minimum(100.0, before + R * actions[:, t])
        vector = encode_schedule(actions)
        report = audit_vector(vector, initial, weights, d, mode, budget)
        rows.append(dict(threshold=threshold, **report["metrics"]))
        vectors.append(vector)
    keys = [(not row["feasible"], 0.0 if row["feasible"] else row["violation"], -row["utility"], j) for j, row in enumerate(rows)]
    chosen = min(range(len(rows)), key=keys.__getitem__)
    for j, row in enumerate(rows):
        row["selected"] = j == chosen
        row["preprocessing_evaluations"] = len(RULE_THRESHOLDS)
        row["mode"] = mode
    return vectors[chosen], rows
