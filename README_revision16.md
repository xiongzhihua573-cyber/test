# 修改指令16：图1—图7完整重绘交付

本轮以第15轮最新Word为源，重新绘制全部7图，重点升级图1、5、6、7。没有改动正文科研内容、数值、图号、图题、作者手动修正的题目、摘要格式及分页；此前版本均保留。无未完成事项。

## 下载

- [新论文Word（15页）](output_final/小论文_中文终稿候选_高质量图片重绘版.docx?raw=true)
- [第二轮图片重绘说明（1页）](output_final/第二轮图片重绘说明.docx?raw=true)
- [全部7图：21份600dpi PNG/SVG/PDF](output_figures_redrawn.zip?raw=true)
- [统一绘图脚本及22份冻结CSV](output_scripts.zip?raw=true)
- [论文PDF预览](revision16_verification/小论文_中文终稿候选_高质量图片重绘版.pdf)

## 文件路径与图片列表

两份DOCX均在output_final/。工作区绝对保存路径分别为：

- `/workspace/output_final/小论文_中文终稿候选_高质量图片重绘版.docx`
- `/workspace/output_final/第二轮图片重绘说明.docx`

[output_figures_redrawn/](output_figures_redrawn/)中每个文件基名各有`.png`、`.svg`、`.pdf`三种格式：

1. Figure_01_redrawn：检测覆盖与缺失
2. Figure_02_redrawn：连续评分预测
3. Figure_03_redrawn：2024年规划初始状态
4. Figure_04_redrawn：配对排程差异
5. Figure_05_redrawn：资源响应与相对增益
6. Figure_06_redrawn：代表方案年度状态与养护安排
7. Figure_07_redrawn：年评分下降量敏感性

[output_scripts/README.md](output_scripts/README.md)提供中文、英文重绘命令及字体要求。全部图均由原始观测或已保存实验CSV重绘，无截图估值；新增均值与既有可行下界读取已有结果，与30次独立运行统计分开。没有重跑预测模型、排程优化或新增实验。

## 验证

- 26个Word包成员中，仅7个PNG媒体成员更换，其余19个部件逐字节一致。
- 最终Word渲染15页，逐页文字、文字坐标、图框、页眉页脚、图题和页码一致；图片框之外的页面像素差为0。
- 7图均经放大检查，无发现裁字、关键数据遮挡或图片变形。
- 原模型比较、误差棒、箱线、最好值、样本数量和年度数据按冻结输入核对；不利结果及LOCF局部下降均保留。
- 661份原科研冻结文件和22份打包CSV未变。中英文入口均成功生成全部7图，中文PNG与交付图逐一精确复现。

详细记录见[revision16_verification/](revision16_verification/)，交付文件SHA-256在final_redraw16_verification.json中。该PDF页数为本环境渲染结果。
