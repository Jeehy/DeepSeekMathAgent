# Tool Name: kg_pathfinder

## Description
基于 Neo4j (Hetionet) 的双模态知识图谱工具，用于疾病靶点的发现与验证。

### 核心特性
1. **验证模式 (validation)**：输入基因列表，验证其与疾病的关联机制（PPI、通路等）。返回证据强度评分及已知/新发现状态标注。
2. **发现模式 (discovery)**：输入疾病名称，从知识图谱中挖掘靶点。

### 排名策略
- **不剔除已知靶点**：保留所有候选基因（已知 + 潜在新发现）。
- **已知靶点优先排名**：为疾病已知关联基因（如 TP53、EGFR 等）添加排名权重，使其排在列表前列。
- **返回结果中明确标注**：`known_genes` (已知靶点) 和 `novel_genes` (潜在新靶点)。

### 输出说明
- `discovered_targets`: 推荐靶点列表（已按重要性排序，已知靶点靠前）。
- `known_genes`: 其中属于已知疾病关联基因的子集。
- `novel_genes`: 其中属于潜在新发现的子集。
- `kg_scores`: 每个靶点的知识图谱证据强度评分 (0-10分)。
- `evidence_details`: 每个靶点的详细证据描述。

**注意**：`discovery` 模式返回的 `discovered_targets` 可直接作为后续组学分析 (`omics_dea` 或 `omics_visualizer`) 的输入。

## Parameters
- mode (string, required): 运行模式，可选 "validation" 或 "discovery"。
- genes (array, optional): [Validation 专用] 需要验证的基因符号列表 (JSON 格式或逗号分隔)。
- disease (string, optional): [Discovery 必填 / Validation 选填] 疾病名称 (e.g. "Liver cancer", "breast cancer")。
- limit (integer, optional): Discovery 模式返回结果数量限制 (Default: 20)。
- prefix (string, optional): 输出前缀 (可选)。

## Command
python skills/kg_pathfinder/script.py --mode {mode} --genes '{genes}' --disease '{disease}' --limit {limit} --prefix '{prefix}'

## Example Usage

### Discovery 模式
```bash
python skills/kg_pathfinder/script.py --mode discovery --disease "Liver cancer" --limit 10
```

### Validation 模式
```bash
python skills/kg_pathfinder/script.py --mode validation --disease "Liver cancer" --genes '["TP53", "EGFR", "STAMBP"]'
```

## Output Example (Discovery)
```json
{
  "status": "success",
  "mode": "discovery",
  "disease": "Liver cancer",
  "discovered_targets": ["TP53", "CTNNB1", "EGFR", "STAMBP", "..."],
  "known_genes": ["TP53", "CTNNB1", "EGFR"],
  "novel_genes": ["STAMBP", "..."],
  "kg_scores": {"TP53": 9.5, "CTNNB1": 9.0, "STAMBP": 7.0},
  "evidence_details": {"TP53": "[已知靶点] 核心抑癌基因...", "STAMBP": "[潜在新靶点] 通过PPI与..."}
}
```