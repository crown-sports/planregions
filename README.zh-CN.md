# PlanRegions

[English](README.md) · [核心方法与论文](docs/methods.zh-CN.md) · [复现实跑笔记](docs/reproduction.zh-CN.md) · [完整验证](docs/validation.md) · [发布版本](https://github.com/chrischen-coder/planregions/releases)

一个房间的轮廓里可能有柱子和庭院，两个区域合并后，这些孔洞也应当留下。PlanRegions 从墙体掩码建立区域实例，让多边形、像素面积、区域内点和合并操作始终有同一份标签图可以核对。它可独立运行，也可读取 WallGraph 输出。

**当前状态：实验几何工具库。** 默认几何划分不需要神经模型，房间属性在缺少语义证据时保持未知。相同墙体输入的 PQ 改善尚不显著，新完整两阶段流程仍有退步；真实数据和外部模型保持私有。

## 背景与问题

墙体像素不能直接回答“这里有几个区域”“柱子和庭院是否属于可用空间”“区域是否可以合并”等问题。简单填充轮廓可能把内部障碍物填掉；门洞会让多个房间连为一个区域；仅凭狭长形状给区域命名，也容易把办公室错误地当成走廊。

PlanRegions 将几何划分、语义赋值和结果导出分为独立模块。默认先排除连接到图像边缘的外部空间，再从非墙体像素的连通域获得候选区域，并保留孔洞。没有语义证据时输出未知属性。门洞和开放空间通过显式分隔线、建筑范围掩码或可选分水岭策略处理，每种操作都记录参数。

## 快速开始

从 GitHub 安装已发布的版本：

```bash
python -m pip install "git+https://github.com/chrischen-coder/planregions.git@v0.1.1"
planregions demo --output runs/demo
```

也可下载 [Release 中的 wheel](https://github.com/chrischen-coder/planregions/releases/tag/v0.1.1) 并校验 SHA256。以下开发安装命令在克隆本仓库后执行：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
planregions demo --output runs/demo
planregions detect --walls /private/walls.png --output runs/regions
```

本工程不提交任何数据图片。`demo` 在内存中生成一张简单三房间示意图，与 WallGraph 的公开简单图具有相同几何；它仅用于检查接口。真实图片、标注、模型、分类映射和逐张结果由使用者在仓库外管理。

输入墙体掩码中 255 是墙、0 是背景。旧系统的黑墙白底图需显式使用 `--wall-value 0`。如果提供 `--wall-metadata walls.json`，会检查 WallGraph 的 schema、尺寸、坐标和墙体极性，避免把坐标错位的结果继续处理。

```bash
# 安装 WallGraph 与 PlanRegions 后的两阶段联用
wallgraph detect --image /private/plan.png --model /private/wall.onnx \
  --output /private/walls
planregions detect --walls /private/walls/walls.png \
  --wall-metadata /private/walls/walls.json --output /private/regions
```

输出包含 `regions.json`、`labels.npz`、`regions.png` 与 `regions.polygons.json`。NPZ 保存精确 int32 实例 ID，0 表示墙体、外部空间或被过滤的像素；PNG 只是预览。多边形使用原图像素坐标，含闭合外环与内孔；polygon JSON 是平面坐标的 FeatureCollection 结构，不是经纬度 GeoJSON。

面积是实例像素数量；轮廓由像素中心和简化容差构造，轮廓面积可能和像素计数不同。`centroid` 是像素质心，在凹形区域或带孔区域中可能落在区域外；`interior_point` 是距离边界最远的区域像素，保证在区域内部。bbox 为左上角闭区间、右下角开区间。没有比例尺时不输出平方米面积。

## 技术难点与工程贡献

| 难点 | 处理方式 | 边界 |
| --- | --- | --- |
| 外部空间泄漏 | 默认排除触边连通域；支持显式 footprint | 外墙开口时可能丢弃整个内部区域，需要范围输入 |
| 开放区域与门洞 | 可配置分隔线；可选基于距离的分水岭 | 分水岭可能过分割，不默认猜测门洞 |
| 柱子、庭院与内部孔洞 | 用轮廓层级生成多边形内环；像素图作为面积依据 | 简化后的轮廓与像素面积不同 |
| 语义标签缺少依据 | 属性策略单独注入；类别映射显式提供；覆盖率不足时保持未知 | 覆盖率不是分类概率，也不表示语义正确率 |
| 合并与拓扑混淆 | 合并保留墙体和孔洞；不相连区域可输出 MultiPolygon；语义冲突变为未知 | 这是实例分组，不是拆墙或证明房间可互通 |
| 任意实例编号影响评估 | 使用 IoU 矩阵和一对一匹配评估实例 | 需要独立人工标注；不能用预测结果作为真值 |

核心工作集中在划分前排除外部、平坦距离平台的有效种子、孔洞保留和像素依据不变的显式合并。轮廓、分水岭和指派求解使用成熟库；PQ 借鉴 [Panoptic Segmentation](https://arxiv.org/abs/1801.00868)，同时明确本工程无类别、阈值包含等号等差异。[方法与论文](docs/methods.zh-CN.md) 将这些依据对应到源码。

[复现实跑笔记](docs/reproduction.zh-CN.md) 讲清同一墙体对照的用途，以及外部泄漏、长房间重复播种和真实预测墙体上的过分割。30 张标注测试中，相同旧墙体的 PQ 差值区间跨零，新完整流程的 PQ 下降；这些结果也决定了默认继续使用连通域。见 [设计](docs/architecture.md) 与 [结果](docs/results.md)。

## 可替换策略

```python
from planregions import RegionPipeline, RegionConfig
from planregions.partition import WatershedPartition
from planregions.operations import merge_regions

# walls 为用户自己的 2D 二值掩码，255 表示墙
pipeline = RegionPipeline(RegionConfig(min_area=64))
result = pipeline.run(walls)
# 合并既有实例；不改变墙体和外部像素
merged = merge_regions(result, [[1, 2]])
```

对于外墙开口图，提供 `--footprint /private/footprint.png`，255 表示建筑范围。手动分隔线文件为 JSON 数组，每项包含两个 `[x, y]` 端点；端点必须在原图内，例如 `[[[90, 10], [90, 90]]]`。使用 `--separators` 注入；几何分水岭通过 `--watershed --peak-distance 20` 开启。默认 `--close-radius 0`，避免自动闭合真实开口。

语义策略可接受对齐的 class map，或外部 ONNX 模型。类别名称 JSON 的 key 为模型类别 ID、value 为标签名；只映射确认语义的类别。ONNX 支持 float32 NCHW 三通道输入与多类分割输出，输入直接缩放到模型尺寸（当前适配器使用最近邻），通道顺序通过 `--attribute-color rgb/bgr` 指定。

```bash
python -m pip install -e '.[onnx]'
planregions detect --walls /private/walls.png --image /private/plan.png \
  --attribute-model /private/attributes.onnx --class-names /private/class-names.json \
  --attribute-color rgb --min-coverage 0.6 --output /private/regions
planregions merge --input /private/regions --groups /private/merge-groups.json \
  --output /private/merged
```

语义模型会话复用，当前仅使用 CPU，原图必须与墙体掩码同尺寸。`attribute.confidence` 表示该区域中多数类别占比，不是模型概率；类别无映射或多数占比不足则输出未知。邻近边的 `kind` 固定为 `spatial_proximity`，不代表存在门、可通行或具备业务关联。

## 私有评估与发布

评估 manifest 为 JSONL，每行包含 `walls`、`instances`、`group`，可选 `footprint`。路径相对于 manifest，也可以为绝对路径。人工实例标注使用二维整数 PNG 或带 `labels` 数组的 NPZ：0 为排除区域、其他正数为实例 ID。运行以下命令获得 IoU 阈值 0.5 的实例 F1 和 PQ；这评估给定墙体掩码上的区域几何，不包含语义准确率。

```bash
planregions evaluate --manifest /private/test.jsonl --output /private/reports/regions.json
# 无标注性能实测：manifest 每行提供 walls，以及可选 image / footprint
planregions benchmark --manifest /private/benchmark.jsonl --warmup 1 --repeats 3 \
  --output /private/reports/latency.json
ruff check .
ruff format --check .
pytest
python tools/release.py --check
python -m build
python tools/release.py --output dist/planregions-source.zip
```

公开发布工具只打包白名单源码、文档与测试，不打包模型、图片、数据和结果。新实现采用 MIT；外部数据/权重和依赖使用各自的许可，见 [NOTICE](NOTICE.md)。

协作规范见 [CONTRIBUTING](CONTRIBUTING.md)、[行为准则](CODE_OF_CONDUCT.md)、[安全报告](SECURITY.md) 和 [发布流程](docs/releasing.md)。`CITATION.cff` 提供软件引用信息。
