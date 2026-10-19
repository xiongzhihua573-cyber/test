# 宁波研究区地图：已核实部分交付

此目录包含用户要求的六项输出，但科学范围必须明确：**当前是可核实GIS背景图，59个检测单元、S1研究线及研究走廊尚未定位核实，不能作为精确桥位图直接投稿。** 图内以“Pending verification — not mapped”说明相应图例符号尚未上图。

## 文件

- `Fig1_StudyArea_Final.svg`：37条路径、12处可编辑文字、0嵌入图片；真实矢量图层。
- `Fig1_StudyArea_Final.pdf`：单页矢量PDF，0嵌入栅格图。
- `Fig1_StudyArea_Final.png`：4724×3543像素，600dpi，20×15cm。
- `plot_study_area.py`：离线复图代码，保留单幅地图布局。
- `bridge_locations_check.csv`：全部59项，坐标及逐单元路线字段为空，未核实单元未上图。
- `map_revision_notes.md`：地理核查、数据来源、所删要素和全部限制。

作者提供的最新真实截图及Bing在线链接已与此前AI示意稿区分，来源记录见 `validation/bing_reference.json`。当前云端对Bing、OSM实际访问被代理拒绝，相关域名配置草稿已保存但尚未应用。

数据来自Natural Earth固定提交，1:10,000,000通用概化尺度。只有真实来源支持的陆海、海岸、15条匿名背景道路及Ningbo城市标签被绘制。没有将匿名道路冒称S1，没有从AI图描摹，也未补画数据源中没有的小河、小湖或地名。省略不代表当地实际没有这些要素。

## 离线复现

本次验证Python3.12；依赖见 `requirements.txt`。在本目录执行：

```bash
python plot_study_area.py
```

另存到新目录：

```bash
python plot_study_area.py --output-dir /tmp/study_map_reproduced
```

默认读取随包 `geodata/` 和 `bridge_locations_check.csv`，不联网、不插值桥位、不读取原PNG作背景。所有地理路径和文字均为独立SVG元素，可在Illustrator或Inkscape中编辑。字体优先Nimbus Roman，缺失时自动选择系统中的其他衬线字体；完全相同字体可获得逐字节复现。

`geodata/GIS_source_manifest.json` 提供固定来源、原始与裁剪文件哈希；原始全球文件未重复附带，正常复图只需本包。若需从原始GIS重做裁剪，按清单取得七份原文件后执行：

```bash
python prepare_verified_gis.py --source-dir /path/to/original_geojson --output-dir /tmp/study_map_geodata
```

独立检查绘图和本地子集：

```bash
python validation/independent_map_check.py --map-dir . --output-json /tmp/study_map_check.json
```

在原云端还会检查原始全球数据及输入Word/Excel保全；脱离原工作区时这部分证据不可重查，报告将如实标记为未执行/不可用，包内SVG、投影、比例尺、GIS子集、空坐标及复现检查仍执行。完整云端核验记录已随包保留。

## 继续正式制图所需

启用已保存的Bing/OSM域名草稿并重新验证访问；补充定检报告、S1与各匝道的可核验路线/里程标定，或逐单元坐标及坐标系。59个检测单元不能按数量均匀排点，截图中的标记也未建立逐单元对应关系。论文正文及原研究文件保持不变。
