import argparse
import json
import os
import sys
import base64
import time
import re
import numpy as np
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 尝试导入依赖
try:
    from pymongo import MongoClient
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    sys.stderr.write(f"[Lit Error] Missing dependencies: {e}\n")
    sys.exit(1)

# === 配置区 ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    sys.stderr.write("[Lit Error] DEEPSEEK_API_KEY not found in .env file\n")
    sys.exit(1)
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"
LITERATURE_VALIDATION_ANALYSIS = """
Target Gene: {gene}
Disease: {disease}

Based on the provided literature abstracts below, please analyze the validity of {gene} as a therapeutic target or biomarker for {disease}.

Literature Context:
{context_str}

Please respond in JSON format with the following keys:
- "support_level": "Strong", "Moderate", "Weak", or "No Evidence"
- "conclusion": A concise summary of the findings (max 100 words).
- "key_mechanisms": List of biological mechanisms mentioned (e.g., "Apoptosis", "Drug Resistance").
- "citations": List of references supporting the conclusion (e.g., ["Smith et al., 2023"]).
"""

LITERATURE_DISCOVERY_ANALYSIS = """
Target Gene: {gene}
Context: Liver Cancer / Pan-Cancer
Search Mode: Discovery

Based on the provided literature abstracts, explore the potential role of {gene} in cancer, focusing on novel mechanisms, drug resistance, or potential as a therapeutic target.

Literature Context:
{context_str}

Please respond in JSON format with the following keys:
- "potential_role": Description of the gene's potential role.
- "novelty_score": "High", "Medium", or "Low" based on the literature.
- "associated_drugs": List of drugs mentioned in context with this gene.
- "conclusion": A summary of why this gene might be a good target.
"""

# === 辅助函数 ===
def log(msg):
    sys.stderr.write(f"[Lit Log] {msg}\n")

def parse_arg(arg_val):
    if not arg_val: return None
    try:
        if arg_val.startswith("B64:"):
            return json.loads(base64.b64decode(arg_val[4:]).decode('utf-8'))
        return json.loads(arg_val)
    except: return str(arg_val)

def call_llm_internal(system_prompt, user_prompt):
    """脚本内部调用 LLM 进行总结"""
    if not DEEPSEEK_API_KEY:
        return json.dumps({"error": "DEEPSEEK_API_KEY not set in environment"})
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
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
        log(f"LLM Call Error: {e}")
        return json.dumps({"error": str(e)})


class LocalRetriever:
    def __init__(self, host="localhost", port=27017, db="bio", coll="DMLLM_EMBEDDING"):
        self.host = host
        self.port = port
        self.db_name = db
        self.coll_name = coll
        self.client = None
        self.collection = None
        self.model = None
        self.index = None
        self.doc_ids = []

    def connect(self):
        if self.client: return
        try:
            self.client = MongoClient(host=self.host, port=self.port, serverSelectionTimeoutMS=2000)
            self.collection = self.client[self.db_name][self.coll_name]
        except Exception as e:
            log(f"DB Connection failed: {e}")
            raise e

        if not self.model:
            log("Loading Embedding Model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            
        if not self.index and self.collection is not None:
            log("Building FAISS index...")
            cursor = self.collection.find({"vector": {"$exists": True}}, {"vector": 1, "_id": 1})
            vectors = []
            self.doc_ids = []
            for doc in cursor:
                vec = doc.get('vector')
                if vec and len(vec) == 384:
                    vectors.append(vec)
                    self.doc_ids.append(doc['_id'])
            
            if vectors:
                vectors_np = np.array(vectors).astype('float32')
                faiss.normalize_L2(vectors_np)
                self.index = faiss.IndexFlatIP(384)
                self.index.add(vectors_np)

    def calculate_keyword_score(self, query, text):
        if not query or not text: return 0.0
        q_terms = set(re.findall(r'\w+', query.lower()))
        t_terms = set(re.findall(r'\w+', text.lower()))
        if not q_terms: return 0.0
        return len(q_terms.intersection(t_terms)) / len(q_terms)

    def search(self, query, top_k=5):
        self.connect()
        if not self.index or not self.model: return []
        
        q_vec = self.model.encode([query])
        q_vec = np.array(q_vec).astype('float32')
        faiss.normalize_L2(q_vec)
        
        D, I = self.index.search(q_vec, top_k * 3)
        
        hit_ids = []
        vec_scores = {}
        for rank, idx in enumerate(I[0]):
            if idx == -1: continue
            mid = self.doc_ids[idx]
            hit_ids.append(mid)
            vec_scores[mid] = float(D[0][rank])
            
        if not hit_ids: return []

        cursor = self.collection.find(
            {"_id": {"$in": hit_ids}},
            {"text": 1, "paper_title": 1, "metadata": 1, "pmid": 1}
        )
        
        results = []
        for doc in cursor:
            mid = doc['_id']
            text = doc.get('text', '')
            score = (0.7 * vec_scores.get(mid, 0.0)) + (0.3 * self.calculate_keyword_score(query, text))
            
            meta = doc.get('metadata', {})
            year = str(meta.get('year', ''))
            if year in ['2023', '2024', '2025', '2026']: score *= 1.1
            
            results.append({
                "title": doc.get('paper_title', 'Unknown'),
                "abstract": text,
                "pmid": doc.get('pmid', ''),
                "year": year,
                "citation": f"{meta.get('author', 'Unknown')} et al., {meta.get('journal', 'Journal')}",
                "score": score,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{doc.get('pmid', '')}/"
            })
            
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]


class LiteratureAnalyzer:
    def __init__(self):
        self.retriever = LocalRetriever()

    def generate_queries(self, gene, disease, mode):
        queries = []
        if mode == "discovery":
            queries.append(("Mechanism", f"{gene} AND (Signaling Pathways OR Mechanism)"))
            queries.append(("Pan-Cancer", f"{gene} AND (Cancer OR Tumor) AND Review"))
            queries.append(("Drug_Target", f"{gene} AND (Inhibitor OR Resistance)"))
        else: # Validation
            queries.append(("Direct_Link", f"{gene} AND {disease}"))
            queries.append(("Prognosis", f"{gene} AND Prognosis AND {disease}"))
            queries.append(("Resistance", f"{gene} AND ({disease} OR HCC) AND Resistance"))
        return queries

    def verify_target(self, gene, disease, mode):
        # 1. 检索
        queries = self.generate_queries(gene, disease, mode)
        all_results = []
        seen_pmids = set()
        
        log(f"Retrieving for {gene} ({mode})...")
        for aspect, q_str in queries:
            hits = self.retriever.search(q_str, top_k=3)
            for h in hits:
                if h['pmid'] and h['pmid'] not in seen_pmids:
                    h['aspect'] = aspect
                    all_results.append(h)
                    seen_pmids.add(h['pmid'])
        
        # 按相关性排序取 Top 5
        all_results.sort(key=lambda x: x['score'], reverse=True)
        top_docs = all_results[:5]

        if not top_docs:
            return {"status": "success", "analysis": {"conclusion": "No evidence found."}, "raw_evidence": []}

        # 2. 构建 Context
        context_str = "\n".join([
            f"[{i+1}] Title: {d['title']}\n    Aspect: {d.get('aspect')}\n    Abstract: {d['abstract'][:500]}..." 
            for i, d in enumerate(top_docs)
        ])

        # 3. 调用 LLM 总结
        log("Analyzing with LLM...")
        sys_prompt = "你是资深生物医学文献分析师，请严格输出JSON格式。"
        if mode == "discovery":
            user_prompt = LITERATURE_DISCOVERY_ANALYSIS.format(gene=gene, context_str=context_str)
        else:
            user_prompt = LITERATURE_VALIDATION_ANALYSIS.format(gene=gene, disease=disease, context_str=context_str)
            
        llm_res_str = call_llm_internal(sys_prompt, user_prompt)
        
        try:
            analysis_json = json.loads(llm_res_str)
        except:
            analysis_json = {"conclusion": llm_res_str, "error": "JSON parse failed"}

        # 4. 组装结果 (Analysis + Raw Evidence)
        return {
            "status": "success",
            "analysis": analysis_json, # 模型总结的结论
            "raw_evidence": top_docs   # 原始文献，供 Agent 查阅
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gene", required=True)
    parser.add_argument("--disease", default="Liver Cancer")
    parser.add_argument("--mode", default="validation")
    parser.add_argument("--max_results", type=int, default=3)
    parser.add_argument("--email", default="") 
    
    try:
        args = parser.parse_args()
        gene = parse_arg(args.gene)
        disease = parse_arg(args.disease)
        mode = parse_arg(args.mode)
        
        tool = LiteratureAnalyzer()
        result = tool.verify_target(gene, disease, mode)
        
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        log(f"Critical Error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()