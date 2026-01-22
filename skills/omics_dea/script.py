import argparse
import pandas as pd
import numpy as np
import json
import os
import sys
import base64
from scipy import stats
import matplotlib.pyplot as plt
from datetime import datetime

def log(msg):
    sys.stderr.write(f"[DEA Log] {msg}\n")

def parse_arg(arg_val):
    if not arg_val: return []
    try:
        if arg_val.startswith("B64:"):
            return json.loads(base64.b64decode(arg_val[4:]).decode('utf-8'))
        # 尝试直接解析
        return json.loads(arg_val)
    except json.JSONDecodeError as e:
        log(f"JSON parse failed for: {repr(arg_val)}, error: {e}")
        return []

# === 业务配置 ===
FILENAME = "cleaned_data.csv"
SUB_DIR = "data"
# 使用绝对路径存储结果
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # DeepSeekMathAgent
RESULTS_BASE_DIR = os.path.join(PROJECT_ROOT, "results")
os.makedirs(RESULTS_BASE_DIR, exist_ok=True)

def get_session_results_dir(session_id=None):
    """获取当前会话的结果目录"""
    if session_id:
        folder_name = session_id
    else:
        # 从环境变量获取会话ID
        folder_name = os.environ.get("AITARGET_SESSION_ID")
        if folder_name:
            log(f"使用环境变量会话ID: {folder_name}")
        else:
            # 如果没有环境变量，使用时间戳
            folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")
            log(f"未找到会话ID环境变量，使用时间戳: {folder_name}")
    session_dir = os.path.join(RESULTS_BASE_DIR, folder_name)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir

def load_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 项目根目录是 skills 的上一级 (DeepSeekMathAgent)
    project_root = os.path.dirname(os.path.dirname(script_dir))
    paths = [
        os.path.join(project_root, SUB_DIR, FILENAME),
        os.path.join(script_dir, "..", "..", SUB_DIR, FILENAME),
        os.path.join(SUB_DIR, FILENAME),
        FILENAME
    ]
    
    for p in paths:
        if os.path.exists(p):
            log(f"Loading data from: {p}")
            return pd.read_csv(p, encoding='utf-8')
    
    log(f"Data file not found. Tried paths: {paths}")
    return None

def perform_dea(df, ids_a, ids_b):
    # 智能识别 RNA_ 开头的列
    rna_cols = [c for c in df.columns if c.startswith("RNA_")]
    if not rna_cols: return None, "No 'RNA_' columns found"

    df['Sample_id'] = df['Sample_id'].astype(str)
    a_str, b_str = [str(x) for x in ids_a], [str(x) for x in ids_b]
    
    df_a = df[df['Sample_id'].isin(a_str)]
    df_b = df[df['Sample_id'].isin(b_str)]
    
    if df_a.empty or df_b.empty: return None, "Sample IDs not found"

    mat_a = df_a[rna_cols].apply(pd.to_numeric, errors='coerce')
    mat_b = df_b[rna_cols].apply(pd.to_numeric, errors='coerce')

    with np.errstate(divide='ignore', invalid='ignore'):
        _, p_values = stats.ttest_ind(mat_a, mat_b, axis=0, nan_policy='omit')
    
    mean_a, mean_b = mat_a.mean(axis=0), mat_b.mean(axis=0)
    log2fc = np.log2((mean_a + 1e-9) / (mean_b + 1e-9))

    res_df = pd.DataFrame({"Gene": rna_cols, "Log2FC": log2fc, "P_Value": p_values})
    return res_df.dropna().sort_values("P_Value"), None

def plot_volcano(res_df, output_path):
    plt.figure(figsize=(8, 6))
    plot_df = res_df.copy()
    plot_df['logP'] = -np.log10(plot_df['P_Value'] + 1e-300)
    
    conditions = [
        (plot_df['P_Value'] < 0.05) & (plot_df['Log2FC'] > 1),
        (plot_df['P_Value'] < 0.05) & (plot_df['Log2FC'] < -1)
    ]
    plot_df['color'] = np.select(conditions, ['red', 'blue'], default='grey')
    
    plt.scatter(plot_df['Log2FC'], plot_df['logP'], c=plot_df['color'], s=10, alpha=0.6)
    
    # 标注 Top 5
    for _, row in plot_df.head(5).iterrows():
        plt.text(row['Log2FC'], row['logP'], row['Gene'].replace("RNA_", ""), fontsize=8)

    plt.title("Volcano Plot")
    plt.xlabel("Log2FC"); plt.ylabel("-Log10 P")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()

def main():
    # 设置标准输出编码为 UTF-8
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--group_a", required=True)
    parser.add_argument("--group_b", required=True)
    parser.add_argument("--top_n", type=int, default=20)
    parser.add_argument("--prefix", default="dea")
    try:
        args = parser.parse_args()
        ids_a, ids_b = parse_arg(args.group_a), parse_arg(args.group_b)
        
        df = load_data()
        if df is None:
            print(json.dumps({"status": "error", "message": "Data load failed"}))
            return

        res_df, err = perform_dea(df, ids_a, ids_b)
        if err:
            print(json.dumps({"status": "error", "message": err}))
            return

        safe_prefix = "".join([c for c in args.prefix if c.isalnum() or c in ('_','-')])
        session_dir = get_session_results_dir()
        plot_path = os.path.join(session_dir, f"{safe_prefix}_volcano.png")
        plot_volcano(res_df, plot_path)

        sig_df = res_df[res_df['P_Value'] < 0.05]
        top_genes = sig_df.head(args.top_n)['Gene'].tolist()
        
        summary = {
            "total_screened": len(res_df),
            "significant_genes": len(sig_df),
            "top_up": sig_df[sig_df['Log2FC'] > 0].head(5)['Gene'].tolist(),
            "top_down": sig_df[sig_df['Log2FC'] < 0].head(5)['Gene'].tolist()
        }

        print(json.dumps({
            "status": "success",
            "data": {
                "top_genes": top_genes, 
                "summary": summary, 
                "plot_path": plot_path,
                "plot_url": os.path.relpath(plot_path, RESULTS_BASE_DIR).replace("\\", "/")  # 返回相对路径用于API访问
            }
        }, ensure_ascii=False))

    except Exception as e:
        log(f"Error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()