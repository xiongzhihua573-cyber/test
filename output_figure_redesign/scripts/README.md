# 论文图1—图7重构绘图脚本

统一入口为 `redraw_figures.py`，按真实CSV生成全部图；不训练模型、不运行GJO、不修改数据。所附24份CSV均为已冻结科研文件的字节副本。resource_level_runs包含420次原运行，deterioration_runs包含90次，其中参考情景30次已复用资源中档；两表不是510个独立新运行。

## 运行

已验证Python 3.12及requirements.txt所列依赖。中文字体使用Noto Sans CJK，西文优先TeX Gyre Termes（Times兼容），回退Liberation Serif。Ubuntu可安装fonts-noto-cjk、fonts-texgyre、fonts-liberation；其它系统请调整figure_style.py中的CJK_PATH。

```bash
python -m pip install -r requirements.txt
python redraw_figures.py
python redraw_figures.py --figures 1 5 7 --output-dir ../selected
python redraw_figures.py --language en --output-dir ../figures_en
```

默认数据为本目录project_data/，默认输出为脚本上级目录的fig1/至fig7/。路径按脚本文件位置解析，可从任意工作目录运行。每图生成600 dpi PNG、LZW无损TIFF、矢量PDF、SVG。SVG中文字转路径、PDF嵌入字体。`--project`可指定包含相同冻结source_data/及results/的目录。输入哈希列在data_SHA256SUMS.json；导出时保存render_manifest.json记录输入/输出哈希和图中文字边界检查。

## 代码与数据

- figure_style.py：统一字体、蓝橙绿映射、固定17cm画布、四格式保存器。
- figures_123.py：覆盖分组柱/观测矩阵、三模型预测、配对初值/差值分布。
- figures_45.py：真实配对分布/原始点、真实资源均值与样本SD带。
- figures_67.py：15年代表方案、三情景响应及真实独立运行/首次养护分布。
- project_data/source_data/：14份观测、预测及初始状态数据。
- project_data/results/：10份最终规划结果、汇总和真实重复运行数据。

图5区间带为均值±样本SD（ddof=1），不是置信区间。虚线可行下界来自独立已验证方案，不计入本档30次统计且不表示全局最优。图4和图7散点仅为避免重叠进行确定性横向错排，纵值完全等于原始数据，箱体或均值标记按实际B/d定位。仅连接已计算情景以辅助观察，不平滑、不新增中间计算。未养护首次年份不编码为0或某一年。

画布物理宽高与上传Word原图框相同，以保留论文布局；不要使用tight裁切改变宽高比。Word采用PNG作兼容内嵌，PDF/SVG供矢量使用，TIFF可供期刊单图提交。
