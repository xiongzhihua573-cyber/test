# 两套已保存养护排程：seed20261025

直接读取现有15年项目中两个指定运行JSON的 `actions` 数组导出；没有重新优化，没有改动行动，没有绘图或修改论文。

## 固定配置

- 规划期：2025—2039年（15年），59个检测单元。
- `level_id=3`，`B=B_limit=1.1547285587180505`。
- `d=0.65`，`seed=20261025`，算法GJO。
- LOCF：`y15__locf__d065__level3__gjo__seed20261025`。
- Ridge：`y15__ridge__d065__level3__gjo__seed20261025`。

## 数据文件

| 文件 | 内容 |
| --- | --- |
| `paired_maintenance_actions_seed20261025.csv` | 885行；严格采用 `unit_id,year,LOCF_action,Ridge_action` 四列。 |
| `maintenance_matrix_LOCF_seed20261025.csv` | LOCF矩阵；59行×15个年度行动值，另带 `unit_id` 行标识列。 |
| `maintenance_matrix_Ridge_seed20261025.csv` | Ridge矩阵；59行×15个年度行动值，另带 `unit_id` 行标识列。 |
| `bridge_unit_mapping.csv` | Br01—Br59、原始桥名、原始数字编号和分组映射；未更名、未合并单元。 |
| `verification_report.json` | 固定配置、实际计数、预期差异、源文件哈希及导出一致性核验。 |
| `source_data/` | 原始运行JSON、初始状态、原桥名编号映射的字节一致副本及来源路径记录。 |
| `export_saved_actions.py` | 仅用Python标准库从所附原始数组重导出数据；不调用优化算法。 |

所有CSV采用UTF-8 BOM，便于Excel读取中文桥名。`1`代表该单元该年实施养护，`0`代表不实施。长表按原始Br01—Br59顺序，再按2025—2039年升序；矩阵年度列同样按该年份顺序。

## 核验结果

| 指标 | 从原始行动逐项计算的结果 |
| --- | ---: |
| 配对行数 | 885 |
| LOCF行动总数 | 94 |
| Ridge行动总数 | 89 |
| 同单元同年双方均行动 | 12 |
| 行动并集 | 171 |
| Jaccard | 12/171 = 0.07017543859649122 |

全部行动值为整数0或1。以上四项计数与用户给定值的差异均为0。长表和两个矩阵均在写入后重新读取，并逐项对照原JSON行动数组。

JSON数组本身没有行标签，因此采用项目原始 `source_data/initial_state_2024.csv` 行序解释：第1—59行对应Br01—Br59；第1—15列对应2025—2039年。原 `bridge_group_mapping.csv` 的数字编号1—59、Br编号、桥名及分组逐项核对一致。没有根据行动总数或Jaccard反推、调换或补造任何行动。

另行只读核验采用保存行动、原始初值和面积按原行序复算；两方案的资源与保存值之差不超过2.23×10⁻¹⁶，J之差不超过1.43×10⁻¹⁴，终期均分一致。这是固定行动审计，没有开展搜索。原运行的 `schedule_replay_passed` 和五项 `replay_checks` 也均通过；该保存标记与本次导出逐项一致性检查分别记录。

## 来源与复现

原项目：`/workspace/revision15_work/prior_project/manuscript_sci_stage12/`。

- 两运行原文件：`results/runs/<run_id>.json`。
- 原始行序与初值：`source_data/initial_state_2024.csv`。
- 原编号与桥名：`source_data/bridge_group_mapping.csv`。
- 所附4份原始文件的SHA256均核对项目冻结清单 `source/frozen_scientific_inputs.json`；完整路径与哈希见 `source_data/source_provenance.json`。

复现导出：在Python 3环境执行 `python export_saved_actions.py`。脚本仅重写本交付目录内派生CSV和核验JSON，不会写入原项目或论文，也不会重新优化。计数若与预期不同会原样报告差异，不修改行动以匹配统计。

实际交付目录：`/workspace/output_paired_maintenance_seed20261025/`。
