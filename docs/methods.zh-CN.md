# 一个区域怎样保持完整的几何含义

[English](methods.md) · [复现与实跑笔记](reproduction.zh-CN.md) · [完整验证](validation.md)

房间轮廓里可能有柱子、庭院和障碍物。区域合并之后，这些孔洞还应存在，面积也应继续对应实际像素。PlanRegions 的核心是建立可靠的实例标签图，再由它生成多边形、内点、属性和邻近关系。

## 核心技术落在哪里

| 技术环节 | 解决的问题 | 对应实现 |
| --- | --- | --- |
| 先识别外部，再划分实例 | 防止分水岭把连接外部的自由空间切成伪室内；开放边界接受显式建筑范围 | [pipeline.py](../src/planregions/pipeline.py) |
| 每个极大值平台一个有效种子 | 避免长方形房间沿平坦距离脊线重复播种；没有种子的连通域补一个种子 | [partition.py](../src/planregions/partition.py) |
| 标签像素驱动带孔几何 | 保留轮廓层级，分别计算像素面积、质心与保证位于内部的像素点 | [geometry.py](../src/planregions/geometry.py) |
| 显式合并与属性策略 | 保留墙体和孔洞，支持不相连的 MultiPolygon；语义冲突保持未知，操作留下映射记录 | [operations.py](../src/planregions/operations.py)、[attributes.py](../src/planregions/attributes.py) |
| 实例编号无关的配对评估 | 紧凑编号后一次统计交叉像素，保留背景对面积的贡献，再求一对一指派 | [metrics.py](../src/planregions/metrics.py) |

这些处理需要完整的墙体或明确的范围证据。连到图像边缘的空间默认排除，缺口可能因此导致室内丢失。分水岭修复了平台播种问题，预测墙体上的噪声多峰仍会过分割，所以连通域继续作为默认策略。

## 论文依据与使用方式

| 论文或原始资料 | 本工程使用的部分 | 复现范围 |
| --- | --- | --- |
| Suzuki 等：[Topological structural analysis of digitized binary images by border following](https://docs.opencv.org/4.13.0/d0/de3/citelist.html)，CVGIP 1985 | OpenCV `findContours` 与 `RETR_CCOMP` 的外环／内孔层级 | 使用库提供的轮廓算法，本工程组织带孔输出、坐标恢复和合并；[API 说明](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html) 给出论文关联 |
| Soille、Ansoult：[Automated basin delineation from digital elevation models using mathematical morphology](https://doi.org/10.1016/0165-1684(90)90127-K)，Signal Processing 1990 | 标记控制分水岭的算法背景 | [scikit-image 文档](https://scikit-image.org/docs/stable/api/skimage.segmentation.html#skimage.segmentation.watershed) 指出部分队列思想来源；本工程调用其库实现，补充距离图、平台种子和外部排除，未复现地形实验 |
| Crouse：[On implementing 2D rectangular assignment algorithms](https://doi.org/10.1109/TAES.2016.140952)，IEEE TAES 2016 | SciPy `linear_sum_assignment` 求一对一最优指派 | [实际求解器](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html) 是改进的 Jonker–Volgenant 变体；没有自行实现经典 Hungarian 算法 |
| Kirillov 等：[Panoptic Segmentation](https://arxiv.org/abs/1801.00868)，CVPR 2019 | PQ 的匹配 IoU 与 FP/FN 惩罚形式 | 本工程报告无类别匹配、`IoU >= 0.5` 的几何版本，按图 macro／实例 micro 聚合；不等同于论文的分语义类别、严格 `IoU > 0.5` 完整协议 |
| Kalervo 等：[CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image Analysis](https://arxiv.org/abs/1904.01920)，2019 | 官方 SVG Space 与结构 Wall 标注作为私有评测依据 | 未复现完整多任务模型或全量榜单；没有对应业务属性的人工真值 |

连通域和欧氏距离变换调用 SciPy。骨架式墙体识别由上游完成；本包不训练区域神经网络，也不从区域形状猜测房间用途。

## 匹配目标与指标边界

设 `K = min(预测实例数, 真值实例数)`，指派收益为 `1[IoU >= t]*(K+1) + IoU`。达标配对数量先占优，全部指派配对的 IoU 总和用于平局选择；最后只保留达标配对计算 F1/PQ。背景交叉参与实例面积，0 不作为房间。这里说明的是当前实现，结果没有因文档澄清而重算。

论文建立的方法、库实现和本工程的数据规则共同决定结果。它们的对应关系写清楚，读者才能知道哪一步可以替换、哪些成绩可以比较。已有实验支持接口与几何不变量，尚未证明端到端精度提升，也未验证属性语义准确率。
