# Tool Name: cohort_selector

## Description
全能样本分组工具。
用于根据关键词（药物名、基因名、临床特征）将样本分为两组。

### 🎯 药物敏感性分组（推荐用法）
数据集包含以下药物的敏感性数据：
- **Sorafenib** (索拉非尼) → 匹配 `Organoid_Sorafenib_Sensitive` (0=耐药, 1=敏感)
- **Lenvatinib** (仑伐替尼) → 匹配 `Organoid_Lenvatinib_Sensitive`
- **Regorafenib** (瑞戈非尼) → 匹配 `Organoid_Regorafenib_Sensitive`
- **Apatinib** (阿帕替尼) → 匹配 `Organoid_Apatinib_Sensitive`
- **Bevacizumab** (贝伐珠单抗) → 匹配 `Organoid_Bevacizumab_Sensitive`

### ⚠️ 注意事项
- 如果用户想研究药物靶点/耐药机制，应使用药物名作为 keyword
- 不要用 Pathology/肿瘤类型 分组来找药物靶点（会找到疾病差异而非药物响应差异）

## Parameters
- keyword (string, required): 分组依据的关键词 (e.g., Sorafenib, TP53, Lenvatinib).
- method (string, optional): 分组方法 ("auto", "median", "quartile"). Default: "auto".

## Command
python skills/cohort_selector/script.py --keyword {keyword} --method {method}