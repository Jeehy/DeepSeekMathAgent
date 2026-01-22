import argparse
import json
import os
import sys
import base64
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# === 配置 ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    sys.stderr.write("[Causal Error] DEEPSEEK_API_KEY not found in .env file\n")
    sys.exit(1)
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"

def log(msg):
    sys.stderr.write(f"[Causal Log] {msg}\n")

def parse_arg(arg_val):
    if not arg_val: return None
    try:
        if arg_val.startswith("B64:"):
            return json.loads(base64.b64decode(arg_val[4:]).decode('utf-8'))
        return json.loads(arg_val)
    except: return str(arg_val)

def call_llm(system_prompt, user_prompt):
    """调用 DeepSeek 执行推理"""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY not set"}
    
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
        "temperature": 0.1, 
        "max_tokens": 1024
    }
    
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def run_causal_inference(gene, disease, gene_info=""):
    # === 1. 构建 System Prompt (参考 ICGI) ===
    # 设定专家角色：分子生物学、功能基因组学、因果推断专家
    system_instruction = (
        f"You are an expert in the fields of molecular biology, functional genomics, cancer research, "
        f"and precision medicine, with deep insights into causal gene identification. "
        f"Moreover, you are an expert at causal inference. "
        f"You comprehend that only a very small number of genes are true causal genes for {disease}, "
        f"and these causal genes play key roles in the initiation and progression of {disease}. "
        f"You are also aware that correlation does not imply causation due to confounding factors. "
        f"Therefore, it is crucial to identify true causal genes for {disease}, not just related genes."
    )

    # === 2. 构建 User Prompt (8步思维链) ===
    # 如果没有提供 gene_info，让模型自己回忆
    gene_context = f"Here is additional information about {gene}:\n{gene_info}" if gene_info else f"Please recall your internal knowledge about the {gene} gene."

    prompt_template = f"""Determining causal genes will help researchers better understand the molecular mechanisms and signaling pathways involved in the initiation and progression of {disease}. This understanding is very important for developing new drugs and targeted therapies for this cancer type.

{gene_context}

Your task now is to infer whether a causal relationship exists between the {gene} gene and {disease}.
Causality is defined as follows: A causal relationship between the variables t and y exists if and only if, with all other factors being equal, a change in t leads to a corresponding change in y. In this relationship, t is the cause, and y is the effect.

To solve the problem, do the following strictly step-by-step:
1 - Analyze the biological functions of the {gene} gene.
2 - Analyze the molecular mechanisms and signaling pathways involved in the initiation and progression of {disease}.
3 - Evaluate the potential role of the {gene} gene in the initiation and progression of {disease}.
4 - Analyze whether there is a reasonable mechanism to explain how the {gene} gene plays a causal role in the initiation and progression of {disease}.
5 - Assess the clinical value of aberrant {gene} gene alterations as a diagnostic marker for {disease}.
6 - Assess the clinical value of targeting {gene} in therapeutic strategies for {disease}.
7 - Assess the prognostic value of {gene} in patients with {disease}, referencing clinical study outcomes.
8 - Comprehensively consider the key findings from all previous steps, the strength of evidence, and the biological plausibility of the proposed mechanism, to determine whether a causal relationship exists between the {gene} gene and {disease}.

If the causality can be fully established, the result should be expressed as <causality>; if not, the result should be expressed as <no causality>.

Ensure that your inference processes are accurate, logical, and responsible. Provide readable expert-level explanations for the final inference.

Output results strictly in JSON format:
{{
  "step_analysis": "Summary of steps 1-7...",
  "final_result": "<causality> or <no causality>",
  "explanation": "Detailed reasoning for the final decision..."
}}
""".strip()

    log(f"Running Causal Inference for {gene} -> {disease}...")
    result_text = call_llm(system_instruction, prompt_template)
    
    try:
        # 清理可能存在的 markdown 代码块标记
        clean_text = result_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        return {"status": "success", "data": data}
    except:
        return {"status": "success", "data": {"raw_response": result_text}}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gene", required=True)
    parser.add_argument("--disease", default="Liver Cancer")
    parser.add_argument("--gene_info", default="")
    
    try:
        args = parser.parse_args()
        gene = parse_arg(args.gene)
        disease = parse_arg(args.disease)
        info = parse_arg(args.gene_info)
        
        result = run_causal_inference(gene, disease, info)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        log(f"Critical Error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()