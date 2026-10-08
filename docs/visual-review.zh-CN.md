# 在浏览器里复核区域变化

[English](visual-review.md) · [打开生成示例](https://crown-sports.github.io/planregions/) · [比较契约](comparison.zh-CN.md)

模型升级或人工修改后，一个总分不能告诉你该看哪个房间。PlanRegions 0.3.0 可以在精确的 JSON 比较报告旁保存本地 HTML。点击变化组或预览中的区域，同步查看前后实例、重叠和进出排除空间的像素；还可以按变化类型筛选。

```bash
planregions compare --before runs/before/labels.npz \
  --after runs/after/labels.npz --output runs/review/changes.json \
  --html-output runs/review/changes.html --fail-on merge disappeared
```

直接用浏览器打开 `changes.html`，不需要服务器、神经模型、浏览器插件或 CDN，报告没有网络请求。输入仍须是同一原图像素网格上的整数标签，两份结果都可以是预测。

CLI 只计算一次比较，JSON 与 HTML 共用报告和复核条件。两份输出成功写入后，若出现指定变化就退出 1；输入、渲染或写入失败退出 2。写入失败可能留下其中一份文件，应确认命令成功完成再使用成对结果。输出不能覆盖输入，也不能互相覆盖；硬链接与符号链接同样检查。

## 预览能说明什么

两张画布用一致的变化组颜色，背景为灰色；选中时同步突出对应组。组列表和像素统计来自完整分辨率结果。哪怕一个像素的正重叠也会建立对应关系，单纯换编号不算变化。报告不能判断哪一版正确，也不能证明区域之间有门。

预览用最近邻采样，最大边为 1,024 像素。大图中的小区域或单像素缺口可能在预览中消失，逐像素复核应回到原始标签文件。HTML 用十进制字符串保留原实例编号，避免 JavaScript 丢失大整数精度；精确 JSON 的整数规则见[比较说明](comparison.zh-CN.md)。

HTML 包含你的标签缩略图和逐区域统计，应与私有结果一起保管；生成它不会自动上传或公开。在线公开示例只用程序生成的小数组，不加载数据集。

## Python 接口

```python
from pathlib import Path
from planregions import compare_regions, render_comparison_html

report = compare_regions(before_labels, after_labels)
html = render_comparison_html(before_labels, after_labels, report, max_side=1024)
Path("/private/review.html").write_text(html, encoding="utf-8")
```

传入对这两份输入计算出的报告。渲染器与比较算法分开，不重复计算诊断；它会检查基本 schema、图像尺寸和预览编号映射，无法证明另行提供的报告来源。

源码目录中的 `python tools/build_showcase.py` 重新生成公开几何演示。CI 用 `python tools/build_showcase.py --check` 确保演示与实际代码一致。
