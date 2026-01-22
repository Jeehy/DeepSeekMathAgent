# Tool Name: causal_reasoner

## Description
生物学因果推理工具 (Logic-based Causal Inference)。
借鉴 ICGI 框架，利用大模型内部的生物学知识，通过 **8步思维链 (Chain of Thought)** 推演特定基因与疾病之间是否存在因果关系。
**核心价值**：不依赖本地数据，仅基于生物学机理进行逻辑验证。适用于本地数据样本量不足或需要理论背书的场景。

## Parameters
- gene (string, required): 目标基因名称 (e.g., "TP53").
- disease (string, optional): 疾病名称 (Default: "Liver Cancer").
- gene_info (string, optional): 基因的补充描述 (如全名、功能)，如果不填则由模型自行回忆。

## Command
python skills/causal_reasoner/script.py --gene '{gene}' --disease '{disease}' --gene_info '{gene_info}'