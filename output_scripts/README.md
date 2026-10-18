# 图1—图7独立重绘脚本

本目录包含统一绘图入口、样式模块、3个分图模块与22个冻结CSV。仅生成图，不训练预测模型、不运行排程优化、不重新估计实验统计量。

## 环境

已验证：Python 3.12，requirements.txt中所列依赖。中文字体为Noto Sans CJK；西文字体优先TeX Gyre Termes（Times兼容），回退Liberation Serif。Ubuntu可安装 `fonts-noto-cjk fonts-texgyre fonts-liberation`；若字体安装位置不同，请调整figure16_style.py的CJK_PATH。中文SVG中文字转为路径，PDF嵌入字体。

```bash
python -m pip install -r requirements.txt
python redraw_all_figures.py
python redraw_all_figures.py --language en --output-dir ../output_figures_en
```

也可仅生成部分图：`python redraw_all_figures.py --figures 1 5 6 7 --output-dir ../selected_figures`。以上命令均以脚本文件位置解析默认数据目录，因此可从任意工作目录运行。绘图入口是redraw_all_figures.py；分图模块中的原始脚本比对函数仅用于原工作区审计，不是独立重绘所需步骤。

## 数据与输出

- `project_data/source_data/`：14个已保存观测、预测和初始状态CSV。
- `project_data/results/`：8个已保存配对运行、资源响应、代表方案、敏感性CSV。
- `data_SHA256SUMS.json`：这22个CSV的SHA-256，用于核对冻结输入。
- 默认输出为上一级的 `output_figures_redrawn/`，每图生成600dpi PNG、矢量SVG、PDF，另生成render_manifest.json记录输入与输出哈希。
- `--project <目录>` 可指定具有source_data/及results/子目录的相同结构数据；`--output-dir`指定输出目录。
- 英文参数仅切换图内文字，不生成或修改英文论文。

所有画布宽17cm，高度与作者现稿内原图框一致；不要使用紧裁切参数改变画布长宽比。Word内嵌PNG保证固定尺寸及兼容性，矢量文件另行保留。

## 科学语义

保留所有样本、方法顺序、均值、样本SD、独立最好值、箱线参数和年度数据。图4均值菱形来自已有汇总CSV；图5点线形式的可行下界来自已有验证方案，独立展示，不计入30次独立运行统计。保留LOCF局部下降及搜索最好值低于已验证可行下界的情况。图7箱线上的观测点只做确定性的横向错排，纵向仍为原整数年份。

已从本目录的打包数据运行全套中文及英文重绘；CSV保持不变。PNG应可精确复现；SVG/PDF的文件哈希可能因导出时间或内部标识不同而变化，不表示科研值变化。
