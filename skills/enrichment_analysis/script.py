import argparse
import os
import sys
import json
import re
import pandas as pd
import gseapy as gp
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# === 配置区 ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    sys.stderr.write("[Enrichment Error] DEEPSEEK_API_KEY not found in .env file\n")
    sys.exit(1)
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"

# 默认数据库目录 (可通参数覆盖)
DEFAULT_DB_DIR = "D:/Bit/tools/data/databases"

# === 提示词 ===
ENRICHMENT_INTERPRETATION_PROMPT = """
你是一个资深生物信息学家。基于以下富集分析结果，请总结该基因集合的主要生物学功能。

显著富集通路 (Top {top_k}):
{pathway_text}

任务：
1. 归纳这些基因主要参与的核心生物学过程（如“细胞周期”、“免疫反应”等）。
2. 指出与疾病（如癌症）最相关的关键通路。
3. 简要总结其潜在的机制意义。

请输出 JSON 格式：
{{
    "biological_summary": "...",
    "key_mechanisms": ["机制1", "机制2"],
    "disease_relevance": "..."
}}
"""

# === 辅助函数 ===
def log(msg):
    """日志输出到 stderr"""
    sys.stderr.write(f"[Enrichment] {msg}\n")

def call_llm(system_prompt, user_prompt):
    if not DEEPSEEK_API_KEY:
        log("Warning: API Key not found, skipping interpretation.")
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

# === 核心类 ===
class EnrichmentTool:
    def __init__(self, gmt_dir):
        self.gmt_dir = gmt_dir
        # 定义数据库文件映射
        self.gmt_files = {
            'KEGG': os.path.join(self.gmt_dir, "KEGG_2021_Human.gmt"),
            'GO_BP': os.path.join(self.gmt_dir, "GO_Biological_Process_2025.gmt")
        }

    def clean_gene_symbol(self, gene_str):
        """清洗基因名"""
        if not isinstance(gene_str, str): return ""
        s = gene_str.strip()
        # 1. 去除前缀 (RNA-, GENE-)
        s = re.sub(r'^(RNA|GENE)[-_]', '', s, flags=re.IGNORECASE)
        # 2. 去除括号内容
        if '(' in s:
            s = s.split('(')[0]
        return s.strip().upper()

    def run_analysis(self, raw_genes, top_k=20, interpret=False):
        # 1. 清洗基因
        gene_list = sorted(list(set([self.clean_gene_symbol(g) for g in raw_genes if g])))
        gene_list = [g for g in gene_list if g] # 去空
        
        log(f"Analyzing {len(gene_list)} genes...")
        if len(gene_list) < 3:
            return {"error": "Too few valid genes for enrichment (<3)."}

        # 2. 检查数据库文件
        valid_gmts = {}
        for name, path in self.gmt_files.items():
            if os.path.exists(path):
                valid_gmts[name] = path
            else:
                log(f"⚠️ Warning: Database not found: {path}")
        
        if not valid_gmts:
            return {"error": f"No valid GMT files found in {self.gmt_dir}"}

        # 3. 运行 GSEApy
        all_sig_paths = []
        
        for db_name, gmt_path in valid_gmts.items():
            try:
                enr = gp.enrichr(
                    gene_list=gene_list,
                    gene_sets=gmt_path,
                    background=None,
                    outdir=None, # 不输出文件
                    no_plot=True,
                    verbose=False
                )
                
                res = enr.results
                if not res.empty:
                    # 筛选显著通路 (P < 0.05)
                    sig = res[res['Adjusted P-value'] < 0.05].copy()
                    if not sig.empty:
                        sig['Source'] = db_name
                        all_sig_paths.append(sig)
            except Exception as e:
                log(f"Error processing {db_name}: {e}")

        if not all_sig_paths:
            return {
                "status": "success", 
                "message": "No significant pathways found.",
                "top_pathways": [],
                "gene_annotations": {}
            }

        combined_df = pd.concat(all_sig_paths)
        
        # 4. 构建输出数据
        # 4.1 Top Pathways
        top_df = combined_df.sort_values("Adjusted P-value").head(top_k)
        top_pathways = []
        for _, row in top_df.iterrows():
            top_pathways.append({
                "term": row["Term"],
                "source": row["Source"],
                "p_adj": float(row["Adjusted P-value"]),
                "genes": row["Genes"].split(";")
            })

        # 4.2 Gene Annotations (System Features)
        # 构建 Gene -> [Pathway1, Pathway2...] 映射
        gene_to_pathways = {g: [] for g in gene_list}
        gene_scores = {g: 0 for g in gene_list}

        for _, row in combined_df.iterrows():
            p_name = f"{row['Source']}:{row['Term']}"
            p_genes = [g.strip().upper() for g in str(row['Genes']).split(';')]
            
            for g in p_genes:
                if g in gene_to_pathways:
                    gene_to_pathways[g].append(p_name)
                    gene_scores[g] += 1

        # 5. LLM 解读
        interpretation = {}
        if interpret and top_pathways:
            pathway_text = "\n".join([f"- [{p['source']}] {p['term']} (p={p['p_adj']:.2e})" for p in top_pathways[:10]])
            sys_prompt = "你是资深生物信息学家，请严格输出JSON格式。"
            user_prompt = ENRICHMENT_INTERPRETATION_PROMPT.format(pathway_text=pathway_text, top_k=10)
            llm_res = call_llm(sys_prompt, user_prompt)
            if llm_res:
                try:
                    interpretation = json.loads(llm_res)
                except:
                    interpretation = {"raw_text": llm_res}

        return {
            "status": "success",
            "n_input_genes": len(gene_list),
            "n_significant_pathways": len(combined_df),
            "top_pathways": top_pathways,
            "gene_features": {
                "annotations": gene_to_pathways,
                "pathway_counts": gene_scores
            },
            "interpretation": interpretation
        }

# === 主程序入口 ===
def main():
    parser = argparse.ArgumentParser(description="Enrichment Analysis Tool")
    parser.add_argument("--genes", required=True, help="JSON list of gene symbols")
    parser.add_argument("--gmt_dir", default=DEFAULT_DB_DIR, help="Directory containing GMT files")
    parser.add_argument("--top_k", type=int, default=20, help="Number of top pathways to return")
    parser.add_argument("--interpret", type=str, default="false", help="Enable LLM interpretation (true/false)")

    args = parser.parse_args()

    # 解析参数
    try:
        gene_list = json.loads(args.genes)
        # 兼容逗号分隔字符串
        if isinstance(gene_list, str):
             gene_list = [x.strip() for x in gene_list.split(',')]
    except:
        # 如果 JSON 解析失败，尝试直接按逗号分割
        gene_list = [x.strip() for x in args.genes.split(',') if x.strip()]

    do_interpret = args.interpret.lower() == "true"

    tool = EnrichmentTool(gmt_dir=args.gmt_dir)
    result = tool.run_analysis(gene_list, top_k=args.top_k, interpret=do_interpret)

    # 输出 JSON 到 stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()