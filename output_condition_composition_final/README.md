# 《绘图指令3》最终图片与论文文字

本目录是独立交付，不自动修改原论文、不编正文图号、不覆盖图1—图7。正式图为四面板100%堆叠柱状图；没有更改图型、科学数据、模型或既有养护方案。

## 六个主要文件

- `condition_composition_final.pdf`：矢量图，内置Type3矢量字形，已核验实际PDF渲染。
- `condition_composition_final.png`：600dpi预览图。
- `condition_composition_final.tif`：600dpi、LZW压缩。
- `plot_condition_composition_final.py`：由保存的同一份CSV重复生成图。
- `condition_composition_final_data_check.md`：数据、科学解释及验收说明。
- `condition_composition_result_text.docx`：图题、图注、150—250字结果段、80—120字讨论衔接备选。

最终图取消总标题和图内长说明，采用1—3类共享图例、三位小数B、精简年份标签和年度养护数量带。每个情景仍保留2025—2039年15个年度柱。4、5类全年均为0，完整原数据与图注仍保留这项事实。

四情景同用2024 LOCF初始状态，d=0.65分/年、R=6分、59个检测单元。2039年1—3类人数为无养护0/54/5、低资源19/39/1、中等资源40/18/1、高资源58/1/0；累计养护次数0/58/93/114。低、中、高资源完整B为0.39411974051622595、1.1547285587180505、2.2956417860207874，图内仅将显示值取三位小数。

无养护为固定零行动比较基线，自2036年起不满足研究管理条件；三个养护方案均通过可行性核验。图中类别是连续模型评分的区间，不是正式实测技术状况等级或马尔可夫转移概率。

## 复现

Python 3.11以上，本次使用Python 3.12；Python依赖见 `requirements.txt`。绘图需要系统字体 `fonts-noto-cjk` 和 `fonts-urw-base35`（Linux包名）；字体缓存仅写入临时目录。打开已导出的PDF或PNG无需额外安装字体。

在本目录执行：

```bash
python plot_condition_composition_final.py
python scripts/generate_result_text.py
```

脚本优先读取随包 `input_data/`。这些文件与上一阶段原始来源逐字节相同，只为离线复现而附带；不会修改输入或执行模型训练、GJO、行动调整。可用参数另存复现结果：

```bash
python plot_condition_composition_final.py --output /tmp/condition_composition_final_reproduced
python scripts/generate_result_text.py --output-dir /tmp/condition_composition_final_text_reproduced
```

文字内容另保存在 `text_content.json`。字数、DOCX读回与渲染核验详情见 `validation/text_audit.json`、`validation/text_render_review.json`。图形导出和实际PDF预览见 `validation/plot_final_export_audit.json` 及 `validation/condition_composition_final_pdf_preview.png`。

## 独立数据与保全核验

在原云端工作区执行完整检查：

```bash
python validation/final_data_audit.py
```

该审计直接读取已保存的逐单元评分、原始行动JSON和年度CSV，不调用绘图或文字脚本，不执行优化。完整保全检查还读取原工作区的上一阶段37项文件、旧稿及图29项、冻结科研661项文件；路径记录在 `validation/preservation_baseline.json`。

若仅解压本包、没有原工作区，可执行：

```bash
python validation/final_data_audit.py --skip-external-preservation
```

此时仅明确跳过外部原文件保全，包内评分、边界、人数、比例、行动、资源约束与科学输入哈希核验仍执行。已有完整审计结果随包保存在 `validation/final_data_audit.json`。

各文件SHA-256见 `SHA256SUMS`。
