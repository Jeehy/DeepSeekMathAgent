# Tool Name: literature_search

## Description
**本地**文献检索工具 (Local DB)。
从本地 MongoDB (`DMLLM_EMBEDDING`) 中检索经过向量化的文献数据。
支持两种模式：
1. **验证模式 (validation)**：查找基因与特定疾病的直接证据。
2. **发现模式 (discovery)**：查找基因的泛癌种机制及药物靶点。
**注意**：此工具不连接外网，仅检索本地知识库。

## Parameters
- gene (string, required): 目标基因.
- disease (string, optional): 疾病名称.
- mode (string, optional): "validation" 或 "discovery".
- max_results (integer, optional): 每个维度最大条数.

## Command
python skills/literature_search/script.py --gene '{gene}' --disease '{disease}' --mode '{mode}' --max_results {max_results}