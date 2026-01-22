import argparse
import os
import sys
import json
import requests
from py2neo import Graph
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# === 配置区 ===

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    sys.stderr.write("[KG Error] DEEPSEEK_API_KEY not found in .env file\n")
    sys.exit(1)
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"

# Neo4j 配置 (Hetionet Public)
NEO4J_URI = "bolt://neo4j.het.io:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"

# === Prompts ===

# Discovery 模式 Prompt
KG_DISCOVERY_PROMPT = """
针对疾病 "{disease}" 分析以下候选靶点。
注意：列表中包含已知致病基因（标记为 [KNOWN]，通常证据极多）和潜在新基因（标记为 [NOVEL]），
已知基因已被优先排列在前，方便作为核心靶点参考。

候选靶点及证据：
{facts_text}

任务：
1. 筛选出最有价值的 Top {limit} 靶点（优先保留已知核心基因和证据链完整的强关联基因）。
2. 用中文给出筛选理由，说明每个基因是已知靶点还是潜在新靶点。
3. 为每个靶点的知识图谱证据强度评分 (0-10分)。

评分标准：
- 9-10分：核心已知基因或与多个已知基因直接互作、参与多条核心通路的强效靶点。
- 7-8分：有较强的网络支持，是潜在的关键调控因子。
- 5-6分：有一定的连接，但并非核心枢纽。
- 0-4分：证据较弱或连接稀疏。

请严格输出 JSON 格式：
{{
    "discovered_targets": ["基因A", "基因B", ...],
    "evidence_map": {{
        "基因A": "[已知靶点] 作为核心驱动基因，参与...",
        "基因B": "[潜在新靶点] 通过...通路与疾病关联"
    }},
    "kg_scores": {{
        "基因A": 9.5,
        "基因B": 7.0
    }}
}}
"""

# Validation 模式 Prompt
KG_VALIDATION_PROMPT = """
疾病：{disease}
目标基因列表：{gene_list}

根据知识图谱检索到的证据（已知靶点标记为 [KNOWN]，潜在新靶点标记为 [NOVEL]）：
{facts_text}

任务：
1. 分析每个基因与疾病的关联机制（中文），明确标注是已知靶点还是潜在新发现。
2. 给出证据强度评分 (0-10分)，已知靶点通常评分更高。

请严格输出 JSON 格式：
{{
    "analysis_results": {{
        "基因A": "[已知靶点] 该基因...",
        "基因B": "[潜在新靶点] ..."
    }},
    "kg_scores": {{
        "基因A": 8.0,
        "基因B": 2.0
    }}
}}
"""

def log(msg):
    """日志输出到 stderr，避免干扰 stdout 的 JSON"""
    sys.stderr.write(f"[KG Pathfinder] {msg}\n")

def call_llm(system_prompt, user_prompt):
    if not DEEPSEEK_API_KEY:
        log("Error: DEEPSEEK_API_KEY not found.")
        return None
    
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        log(f"LLM Error: {e}")
        return None


class KGPathfinder:
    # 已知基因排名权重 (让已知靶点排名更靠前)
    KNOWN_GENE_BONUS = 100
    
    def __init__(self):
        self.graph = None
        # 通用噪音基因黑名单 (Hub Genes - 连接度极高但特异性低的泛素类基因)
        self.BLACKLIST = {'UBC', 'UBB', 'RPS27A', 'UBA52'}
        self._connect()

    def _connect(self):
        try:
            self.graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        except Exception as e:
            log(f"Connection Failed: {e}")

    def _check_known_genes(self, disease, gene_list):
        """
        批量检查哪些基因是疾病的已知关联基因。
        返回已知基因的集合。
        """
        if not gene_list:
            return set()
        cypher = """
        MATCH (d:Disease)-[:ASSOCIATES_DaG]-(g:Gene)
        WHERE toLower(d.name) = toLower($disease) AND g.name IN $genes
        RETURN g.name as gene
        """
        res = self.graph.run(cypher, disease=disease, genes=gene_list).data()
        return {r['gene'] for r in res}

    def _query_ppi(self, disease, candidate_genes=None, limit=50):
        """
        查询 PPI 网络。
        """
        cypher = """
        MATCH (d:Disease)-[:ASSOCIATES_DaG]-(seed:Gene)-[:INTERACTS_GiG]-(candidate:Gene)
        WHERE toLower(d.name) = toLower($disease)
        """
        
        params = {"disease": disease, "limit": limit}

        if candidate_genes:
            cypher += " AND candidate.name IN $genes "
            params["genes"] = candidate_genes
            params["limit"] = 1000  
        
        # 按连接度降序排列
        cypher += """
        RETURN candidate.name AS gene, 
               count(DISTINCT seed) AS count, 
               collect(DISTINCT seed.name)[0..5] AS evidence
        ORDER BY count DESC LIMIT $limit
        """
        return self.graph.run(cypher, **params).data()

    def _query_pathway(self, disease, candidate_genes=None, limit=50):
        """查询通路网络"""
        cypher = """
        MATCH (d:Disease)-[:ASSOCIATES_DaG]-(seed:Gene)-[:PARTICIPATES_GpPW]->(p:Pathway)<-[:PARTICIPATES_GpPW]-(candidate:Gene)
        WHERE toLower(d.name) = toLower($disease)
        """
        
        params = {"disease": disease, "limit": limit}

        if candidate_genes:
            cypher += " AND candidate.name IN $genes "
            params["genes"] = candidate_genes
            params["limit"] = 1000

        cypher += """
        RETURN candidate.name AS gene, 
               count(DISTINCT p) AS count, 
               collect(DISTINCT p.name)[0..3] AS evidence
        ORDER BY count DESC LIMIT $limit
        """
        return self.graph.run(cypher, **params).data()

    def run_discovery(self, disease, limit=20):
        log(f"Mode: Discovery | Disease: {disease} | Limit: {limit}")
        
        # 1. 查询图谱 
        query_limit = max(50, limit * 3)
        ppi = self._query_ppi(disease, limit=query_limit)
        pw = self._query_pathway(disease, limit=query_limit)
        
        candidates = {}
        candidate_scores = {} # 用于记录总连接分值

        # 2. 整合证据并计算分数
        for r in ppi:
            gene = r['gene']
            if gene in self.BLACKLIST: continue
            
            fact = f"PPI: Interacts with {r['count']} disease genes (e.g., {','.join(r['evidence'])})."
            candidates.setdefault(gene, []).append(fact)
            
            # 累加连接数作为分数
            candidate_scores[gene] = candidate_scores.get(gene, 0) + r['count']
            
        for r in pw:
            gene = r['gene']
            if gene in self.BLACKLIST: continue
            
            fact = f"Pathway: In {r['count']} shared pathways (e.g., {','.join(r['evidence'])})."
            candidates.setdefault(gene, []).append(fact)
            
            # 累加连接数作为分数
            candidate_scores[gene] = candidate_scores.get(gene, 0) + r['count']
        
        if not candidates:
            return {"error": "No candidates found in KG"}
        
        # 3. 检查哪些是已知靶点
        all_genes = list(candidates.keys())
        known_genes = self._check_known_genes(disease, all_genes)
        log(f"Found {len(known_genes)} known genes out of {len(all_genes)} candidates")
        
        # 4. 为已知基因添加权重，使其排名更靠前
        for gene in known_genes:
            if gene in candidate_scores:
                candidate_scores[gene] += self.KNOWN_GENE_BONUS
            
        # 5. 排序：已知基因会排在前面
        top_genes = sorted(candidates.keys(), key=lambda g: candidate_scores.get(g, 0), reverse=True)[:query_limit]

        # 6. 生成 Prompt (标注已知/新发现状态)
        facts_lines = []
        for g in top_genes:
            status = "[KNOWN]" if g in known_genes else "[NOVEL]"
            facts_lines.append(f"- {g} {status}: {' '.join(candidates[g])}")
        facts_text = "\n".join(facts_lines)
        
        sys_prompt = "你是资深生物信息学家，请严格输出JSON格式。"
        user_prompt = KG_DISCOVERY_PROMPT.format(disease=disease, facts_text=facts_text, limit=limit)
        
        # 5. 调用 LLM
        llm_res = call_llm(sys_prompt, user_prompt)
        
        try:
            res_json = json.loads(llm_res)
            discovered = res_json.get("discovered_targets", [])
            return {
                "status": "success",
                "mode": "discovery",
                "disease": disease,
                "discovered_targets": discovered,
                "known_genes": [g for g in discovered if g in known_genes],  # 标注哪些是已知的
                "novel_genes": [g for g in discovered if g not in known_genes],  # 标注哪些是新发现的
                "kg_scores": res_json.get("kg_scores", {}),
                "evidence_details": res_json.get("evidence_map", {})
            }
        except:
            return {"error": "LLM output parsing failed", "raw": llm_res}

    def run_validation(self, disease, genes):
        log(f"Mode: Validation | Disease: {disease} | Genes: {genes}")
        
        if not genes:
            return {"error": "Gene list is empty"}
        
        # 1. 检查已知状态
        known_genes = self._check_known_genes(disease, genes)
        log(f"Known genes: {known_genes}")
            
        # 2. 查询特定基因
        ppi = self._query_ppi(disease, candidate_genes=genes)
        pw = self._query_pathway(disease, candidate_genes=genes)
        
        evidence_map = {g: [] for g in genes}
        
        for r in ppi: evidence_map[r['gene']].append(f"PPI: Interacts with {r['count']} disease genes.")
        for r in pw: evidence_map[r['gene']].append(f"Pathway: In {r['count']} pathways.")
        
        # 3. 生成文本 (带已知状态标注)
        facts_list = []
        for g, evs in evidence_map.items():
            status = "[KNOWN]" if g in known_genes else "[NOVEL]"
            ev_str = " ".join(evs) if evs else "No direct KG evidence."
            facts_list.append(f"- {g} {status}: {ev_str}")
            
        facts_text = "\n".join(facts_list)
        
        # 4. LLM 分析
        sys_prompt = "你是资深生物信息学家，请严格输出JSON格式。"
        user_prompt = KG_VALIDATION_PROMPT.format(disease=disease, gene_list=str(genes), facts_text=facts_text)
        
        llm_res = call_llm(sys_prompt, user_prompt)
        
        try:
            res_json = json.loads(llm_res)
            return {
                "status": "success",
                "mode": "validation",
                "analysis_results": res_json.get("analysis_results", {}),
                "kg_scores": res_json.get("kg_scores", {}),
                "known_status": {g: (g in known_genes) for g in genes}  # 返回每个基因的已知状态
            }
        except:
            return {"error": "LLM output parsing failed", "raw": llm_res}

# === 主程序入口 ===
def main():
    parser = argparse.ArgumentParser(description="KG Pathfinder Tool")
    parser.add_argument("--mode", required=True, choices=["discovery", "validation"], help="Mode")
    parser.add_argument("--genes", help="JSON string list of genes for validation")
    parser.add_argument("--disease", default="Liver Cancer", help="Disease name")
    parser.add_argument("--limit", type=int, default=15, help="Limit for discovery results")
    parser.add_argument("--prefix", default="", help="Output prefix (optional)")
    
    args = parser.parse_args()
    
    # 解析基因列表
    gene_list = []
    if args.genes:
        try:
            gene_list = json.loads(args.genes)
        except:
            # 兼容直接逗号分隔
            gene_list = [g.strip() for g in args.genes.split(",") if g.strip()]
    
    tool = KGPathfinder()
    
    if args.mode == "discovery":
        result = tool.run_discovery(args.disease, limit=args.limit)
    else:
        result = tool.run_validation(args.disease, gene_list)
        
    # 最终结果输出到 stdout (供上层 Agent 读取)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()