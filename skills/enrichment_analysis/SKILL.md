# Tool Name: enrichment_analysis

## Description
基于 GSEApy 的本地富集分析工具 (KEGG & GO)。
1. **输入清洗**：自动清洗基因名称（去除 RNA-, GENE- 前缀等）。
2. **多库分析**：默认支持 KEGG 和 GO_BP 分析。
3. **特征生成**：返回显著富集通路列表，以及每个基因命中的通路注释（System Features）。
4. **智能解读**：使用 LLM 对富集结果进行生物学意义解读。

## Parameters
- genes (array, required): 需要分析的基因列表 (JSON string, e.g., '["TP53", "EGFR"]').
- gmt_dir (string, optional): GMT 数据库文件所在目录 (Default: "D:/Bit/tools/data/databases").
- top_k (integer, optional): 返回最显著的通路数量 (Default: 20).
- interpret (boolean, optional): 是否调用 LLM 解读富集结果 (Default: false).

## Command
python skills/enrichment_analysis/script.py --genes '{genes}' --gmt_dir '{gmt_dir}' --top_k {top_k} --interpret {interpret}