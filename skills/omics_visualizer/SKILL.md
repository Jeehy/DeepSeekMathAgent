# Tool Name: omics_visualizer

## Description
通用组学数据可视化工具。
用于绘制基因表达量的箱线图(Boxplot)、热图(Heatmap)或样本分布的PCA图。
通常在 `cohort_selector` 或 `omics_dea` 之后调用，用于展示特定基因的细节。

## Parameters
- plot_type (string, required): 图表类型。可选值: "boxplot" (单/多基因对比), "heatmap" (多基因模式), "pca" (样本聚类).
- genes (array, optional): 需要绘图的基因符号列表 (e.g., ["TP53", "EGFR"]). 对 PCA 可不填.
- group_a_ids (array, required): Group A 样本ID列表.
- group_b_ids (array, required): Group B 样本ID列表.
- output_prefix (string, optional): 文件名前缀.

## Command
python skills/omics_visualizer/script.py --plot_type '{plot_type}' --genes '{genes}' --group_a '{group_a_ids}' --group_b '{group_b_ids}' --prefix '{output_prefix}'