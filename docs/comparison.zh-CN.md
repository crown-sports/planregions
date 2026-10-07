# 看清哪些区域发生了变化

[English](comparison.md) · [使用场景](use-cases.zh-CN.md) · [研究路线](research-roadmap.zh-CN.md)

墙体分数只变化一点，几个房间却可能合并或消失。比较同一图纸的两份实例标签图，可以直接定位这种变化。它适合复核模型版本、阈值、显式分隔线或人工合并；两份输入都可以是预测结果。

## 先比较两份结果

安装 PlanRegions 0.2.0 或更新版本，使用两次运行输出的精确整数标签图：

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json
```

也支持二维整数标签图片，不能用彩色预览图代替。输入必须来自同一原图像素网格；尺寸相同并不能证明已经配准。0 表示排除空间，正数是在各自结果中使用的实例编号，两次编号无需一致。

```python
from planregions import compare_regions

report = compare_regions(before_labels, after_labels)
for group in report["groups"]:
    if group["kind"] != "unchanged":
        print(group["kind"], group["before_ids"], group["after_ids"])
```

## 报告怎样解释

只要两个正编号实例有像素重叠，就建立对应关系；这些关系的连通组给出变化类型：

| 类型 | 对应关系 |
| --- | --- |
| `unchanged` | 一对一且像素归属完全相同，允许重新编号 |
| `reshaped` | 一对一，但有像素进入或离开排除空间；孔洞也可能变化 |
| `split` | 一个旧实例与多个新实例重叠 |
| `merge` | 多个旧实例与一个新实例重叠 |
| `reorganized` | 两边都有多个实例，通过重叠连成一个对应组 |
| `appeared` | 新实例与任何旧实例都没有正像素重叠 |
| `disappeared` | 旧实例与任何新实例都没有正像素重叠 |

`overlaps` 保存实际重叠的编号对、像素数和双方覆盖比例。`before_regions` 记录各旧实例流向背景的像素与比例，`after_regions` 记录反向流量。`groups` 给出每组编号与像素账目。`summary.group_counts` 数的是对应组，不是房间数；schema 为 `planregions-comparison/1`。

默认连一个像素的重叠也计入，因此轻微边界移动可能连接成较大的对应组。没有隐式容差，也没有一对一匹配截断。复核时应同时查看覆盖比例。这些类别描述实例对应关系，不能判断通行关系或几何是否正确。背景还包含墙体、外部、被过滤的小区域等；仅凭两份标签图，无法确定像素被排除的具体原因。

## 放进自动复核流程

可明确指定哪些变化需要返回非零退出码：

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json \
  --fail-on merge disappeared
```

程序先写报告；出现指定类型时退出 1。不设置 `--fail-on` 时，成功比较退出 0。输入不合法或报告写入失败时退出 2。`review_gate` 记录指定与触发类型。有意合并也会触发，这表示需要复核，不能据此判定准确率。输入标签不被修改；输出路径若指向或链接到输入文件，会被拒绝。

## 复现一个墙像素的影响

从源码目录运行：

```bash
python tools/compare_demo.py --output runs/change-demo
planregions compare --before runs/change-demo/closed.npz \
  --after runs/change-demo/inner-gap.npz --output runs/change-demo/inner.json
planregions compare --before runs/change-demo/closed.npz \
  --after runs/change-demo/outer-gap.npz --output runs/change-demo/outer.json
```

示例在内存中生成数组，并保存本地标签文件，没有附加数据集或图片。20×30 的构造布局包含两间封闭区域、94 个墙像素。移除一个内墙像素，墙体 IoU 仍有 0.98936，两间区域却连成一间；移除一个外墙像素，IoU 相同，其中一间区域因外部排除而消失。

| 构造情况 | 区域数前 → 后 | 区域像素前 → 后 | 报告 |
| --- | --- | --- | --- |
| 内墙缺口 | 2 → 1 | 322 → 323 | 一个合并组，增加一个前景像素 |
| 外墙缺口 | 2 → 1 | 322 → 154 | 一个消失实例，168 像素流向背景 |

这是受控几何演示，作用是解释为什么还要检查区域结构，不用于估计真实识别准确率。

## 验证与使用边界

验收覆盖分裂、合并、多对多对应、孔洞、重新编号、uint64 最大编号、只读及非连续数组、全背景、非法输入与 CLI 复核退出码。独立的坐标集合及图遍历参照实现，在固定 seed 的 1,000 组随机小数组上结果一致。此前私有保存的三张严重失败图也通过了像素账目与 JSON 往返检查：旧／新标签共有 52／11 个实例，诊断得到五个合并组、五个消失实例、一个重组组和四个形状变化组。样本按失败程度预先挑选，不能估计普遍错误频率，也没有形成新的识别精度结论。

实现按像素对排序，时间约为 O(P log P)，结合并查集建立对应组；工作内存为 O(P+R+E)，其中 P 是像素数，R 是实际编号数，E 是实际重叠对数。它显式分配 P×2 索引数组，避免按最大编号或全部实例组合分配矩阵；大图仍需要与像素数成比例的内存。JSON 中编号以精确 Python 整数保存，JavaScript 使用者需用能保留大整数的解析方式。

有独立真值时，用[实例 F1/PQ](validation.md)判断结果正确性；用变化报告定位需要查看的区域。[研究路线](research-roadmap.zh-CN.md)进一步说明连续性与边界语义怎样验证。
