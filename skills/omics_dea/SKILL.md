# Tool Name: omics_dea

## Description
组学差异表达分析工具 (Differential Expression Analysis)。
用于计算两组样本之间的基因表达差异。
它会执行 T-test 统计检验，计算 Log2FC，并**自动生成火山图 (Volcano Plot)**。
**输入要求**：必须提供两组样本的 ID 列表（通常来自 `cohort_selector` 的输出）。

## Parameters
- group_a_ids (array, required): 实验组 (Group A) 的样本 ID 列表.
- group_b_ids (array, required): 对照组 (Group B) 的样本 ID 列表.
- top_n (integer, optional): 返回最显著基因的数量 (Default: 20).
- output_prefix (string, optional): 输出文件/图片的前缀 (e.g., "TP53_mut").

## Command
python skills/omics_dea/script.py --group_a '{group_a_ids}' --group_b '{group_b_ids}' --top_n {top_n} --prefix '{output_prefix}'