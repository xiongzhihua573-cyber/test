#!/usr/bin/env python3
"""Export saved literal actions only; no optimizer or action reconstruction."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source_data"
YEARS = list(range(2025, 2040))
RUNS = {
    "LOCF": "y15__locf__d065__level3__gjo__seed20261025",
    "Ridge": "y15__ridge__d065__level3__gjo__seed20261025",
}
SOURCE_HASHES = {
    f"{RUNS['LOCF']}.json": "d2b00f6a6ada81ef8e5d8e901d2023fed43a597b4e0239c1732168f317cf44cc",
    f"{RUNS['Ridge']}.json": "aee39ff567529965ac8b9e5712502bb2fdb19d10a0b11884b205c5dae87dbdbb",
    "initial_state_2024.csv": "dbb09638cdaeb3b162aef6fed5c33422e8dfb384f74023f007906ec06e3c392b",
    "bridge_group_mapping.csv": "a75e3ef781c77a1010d0980ebb6a750f08770d449aa34cf83a22c861c576f735",
}
CONFIG = {
    "planning_horizon": 15, "start_year": 2025, "end_year": 2039,
    "level_id": 3, "B": 1.1547285587180505,
    "B_limit": 1.1547285587180505, "d": 0.65,
    "seed": 20261025, "algorithm": "GJO",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    for name, expected in SOURCE_HASHES.items():
        actual = hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
        require(actual == expected, f"Source hash mismatch: {name}")
    initial = read_csv(SOURCE / "initial_state_2024.csv")
    unit_ids = [row["unit_id"] for row in initial]
    require(unit_ids == [f"Br{i:02d}" for i in range(1, 60)],
            "Unexpected source unit order")
    require(all(row["bridge_name"] for row in initial), "Missing bridge name")
    original_mapping = read_csv(SOURCE / "bridge_group_mapping.csv")
    require([r["unit_id"] for r in original_mapping] == unit_ids,
            "Original bridge mapping unit-order mismatch")
    require(all(r["bridge_name"] == s["bridge_name"] and
                r["bridge_group"] == s["group_id"] and
                int(r["raw_unit_id"]) == i + 1
                for i, (r, s) in enumerate(zip(original_mapping, initial))),
            "Original bridge names/IDs/groups disagree with initial-state source")
    matrices, records = {}, {}
    for method, run_id in RUNS.items():
        saved = json.loads((SOURCE / f"{run_id}.json").read_text(encoding="utf-8"))
        row, actions = saved["row"], saved["actions"]
        require(row["run_id"] == run_id, f"Run ID mismatch: {method}")
        for key, expected in CONFIG.items():
            require(row[key] == expected, f"Configuration mismatch: {method}/{key}")
        require(row["initial"] == method and row["initial_condition"] == method,
                f"Initial-state mismatch: {method}")
        require(len(actions) == 59 and all(len(r) == 15 for r in actions),
                f"Not a 59x15 matrix: {method}")
        require(all(type(value) is int and value in (0, 1)
                    for r in actions for value in r), f"Nonbinary action: {method}")
        require(sum(map(sum, actions)) == row["maintenance_count"],
                f"Saved maintenance count inconsistent with actions: {method}")
        matrices[method], records[method] = actions, saved

    paired_rows = [
        [unit_id, year, matrices["LOCF"][i][j], matrices["Ridge"][i][j]]
        for i, unit_id in enumerate(unit_ids) for j, year in enumerate(YEARS)
    ]
    paired_path = ROOT / "paired_maintenance_actions_seed20261025.csv"
    write_csv(paired_path, ["unit_id", "year", "LOCF_action", "Ridge_action"], paired_rows)
    for method, matrix in matrices.items():
        path = ROOT / f"maintenance_matrix_{method}_seed20261025.csv"
        write_csv(path, ["unit_id", *YEARS],
                  ([unit_id, *matrix[i]] for i, unit_id in enumerate(unit_ids)))
        back = read_csv(path)
        require([r["unit_id"] for r in back] == unit_ids, "Matrix unit-order mismatch")
        require([[int(r[str(y)]) for y in YEARS] for r in back] == matrix,
                f"Matrix export differs from literal source actions: {method}")
    mapping_header = ["unit_id", "bridge_name", "raw_unit_id", "group_id"]
    mapping_rows = [
        [r["unit_id"], r["bridge_name"], original_mapping[i]["raw_unit_id"], r["group_id"]]
        for i, r in enumerate(initial)
    ]
    write_csv(ROOT / "bridge_unit_mapping.csv", mapping_header, mapping_rows)

    back = read_csv(paired_path)
    require(len(back) == 885, "Not 885 paired rows")
    require(len({(r["unit_id"], r["year"]) for r in back}) == 885, "Duplicate unit/year")
    require([[r["unit_id"], int(r["year"]), int(r["LOCF_action"]), int(r["Ridge_action"])]
             for r in back] == paired_rows, "Paired CSV differs from source matrices")
    require(read_csv(ROOT / "bridge_unit_mapping.csv") ==
            [dict(zip(mapping_header, r)) for r in mapping_rows],
            "Bridge mapping differs from original source")
    locf = sum(r[2] for r in paired_rows)
    ridge = sum(r[3] for r in paired_rows)
    overlap = sum(r[2] == r[3] == 1 for r in paired_rows)
    union = sum(r[2] == 1 or r[3] == 1 for r in paired_rows)
    actual_counts = {"LOCF_action_count": locf, "Ridge_action_count": ridge,
                     "overlap_count": overlap, "union_count": union}
    expected_counts = {"LOCF_action_count": 94, "Ridge_action_count": 89,
                       "overlap_count": 12, "union_count": 171}
    report = {
        "recovery_method": "Direct export of literal saved JSON actions arrays",
        "optimization_rerun": False, "actions_modified": False,
        "configuration": CONFIG, "run_ids": RUNS,
        "paired_rows": len(back), "matrix_shape_per_method": [59, 15],
        "matrix_rows": unit_ids, "matrix_columns": YEARS,
        "binary_actions": True, "exports_exactly_equal_saved_actions": True,
        "original_bridge_mapping_preserved": True,
        "actual": {**actual_counts, "jaccard_fraction": f"{overlap}/{union}",
                   "jaccard": overlap / union if union else None},
        "expected": expected_counts,
        "differences_actual_minus_expected":
            {key: actual_counts[key] - expected_counts[key] for key in expected_counts},
        "all_expected_counts_match": actual_counts == expected_counts,
        "source_sha256": SOURCE_HASHES,
        "source_saved_replay_checks": {m: r["replay_checks"] for m, r in records.items()},
    }
    (ROOT / "verification_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(back), **report["actual"],
                      "all_expected_counts_match": report["all_expected_counts_match"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
