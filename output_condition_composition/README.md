# 桥梁检测单元评分等级构成：独立候选图

方案A为四面板100%堆叠柱状图；方案B为相同数据的四面板堆叠面积图。建议优先选用方案A以呈现离散年度。没有修改现有论文或图1—图7。

## 查看文件

- `condition_composition_stacked_bars.pdf / .png / .tif`：方案A。
- `condition_composition_stacked_area.pdf / .png`：方案B。
- `condition_composition_data_check.md`：情景选择、完整B值、评分来源、核验结果及限制。
- `condition_composition_by_year.csv`：300条构成统计。
- `unit_year_scores.csv`：3540条单元年度评分和行动。
- `scenario_selection.json`：共同参数、四情景方案标识及来源。
- `validation/`：数据复算、独立核验、图形导出及复现审计。
- `source_data/`：与冻结最终15年模型逐字节相同的输入、代表行动及原始年度结果。

无养护对照的B=0表示固定零行动。低/中/高资源采用原15年结果的level1/3/6，B分别为0.39411974051622595、1.1547285587180505、2.2956417860207874。四情景同用2024 LOCF初值，d=0.65、R=6、59单元、2025—2039年。

无养护从2036年起不满足研究管理条件；三个养护方案可行。4类和5类在全部年度均为0，图中完整保留五类图例。本结果为连续评分的模型区间分类，不是正式技术状况评定或实测等级转移概率。

## 复现

在本目录运行，或对脚本使用绝对路径：

```bash
python prepare_condition_data.py
python plot_condition_composition.py
```

第一步仅对已有固定行动方案进行原递推和独立标量复算，并统计等级。第二步导出两套图。不训练模型、不运行GJO、不调整任何养护计划。所有数据路径以脚本所在目录为基准，不依赖当前工作目录。

保留现有交付文件而复现至其他目录：

```bash
python prepare_condition_data.py --output-dir /tmp/condition_composition_reproduced
python plot_condition_composition.py --data /tmp/condition_composition_reproduced/condition_composition_by_year.csv --config /tmp/condition_composition_reproduced/scenario_selection.json --output /tmp/condition_composition_reproduced
```

使用本包固定依赖时需要Python 3.11以上；依赖见 `requirements.txt`。本次实际验证环境为Python 3.12。Linux需要 `fonts-noto-cjk`（简体中文）及 `fonts-urw-base35`（Nimbus Roman）。绘图代码会从系统Noto字库选择SC字体面；缓存位于系统临时目录。PDF内置Type3矢量字形，避免中文CFF字体兼容问题，打开已导出的文件无需另装字体。图幅18×15.8cm，PNG/TIFF为600dpi，TIFF使用LZW压缩；PDF以矢量绘制。

`validation/independent_verify.py` 是本次云端对冻结原项目、输出及旧文件保全的独立审计器。它不导入准备或绘图代码；默认冻结项目路径为 `/workspace/revision15_work/prior_project/manuscript_sci_stage12`，可通过 `--project` 指定。独立保全核验优先读取已随包保存的 `validation/independent_preservation_baseline.json`；可通过 `--preservation-baseline` 指定其他基线。该审计仍需要原科研项目和基线所列云端绝对路径中的旧文件，普通绘图复现不依赖这些路径，也无需运行该审计器。

完整来源及SHA-256见 `source_data/source_provenance.json`。参考文献Fig.17仅用于图形表达形式，未引入其数字或半马尔可夫模型。
