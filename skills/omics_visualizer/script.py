import argparse
import pandas as pd
import numpy as np
import json
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# === 协议辅助函数 ===
def log(msg):
    sys.stderr.write(f"[Visualizer Log] {msg}\n")

DATA_FILE = "最终三表合一数据.csv"
RESULTS_DIR = "results"

def load_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(base_dir)))
    
    paths = [
        DATA_FILE,
        os.path.join("data", DATA_FILE),
        os.path.join(base_dir, "..", "..", DATA_FILE)
    ]
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']
    
    for p in paths:
        if os.path.exists(p):
            for enc in encodings:
                try:
                    df = pd.read_csv(p, encoding=enc)
                    return df
                except: continue
    return None

def get_expression_data(df, genes, group_a, group_b):
    """提取绘图所需数据"""
    # 1. 转换基因名为列名
    target_cols = []
    if genes:
        all_cols = df.columns
        for g in genes:
            if g in all_cols: target_cols.append(g)
            elif f"RNA_{g}" in all_cols: target_cols.append(f"RNA_{g}")
            else: log(f"Warning: Gene {g} not found in data.")
    
    if not target_cols and not genes:
        rna_cols = [c for c in df.columns if c.startswith("RNA_")]
        target_cols = rna_cols[:100]

    if not target_cols:
        return None, "No valid genes found."

    # 2. 提取并标记分组
    df_a = df[df['Sample_id'].isin(group_a)].copy()
    df_a['Group'] = 'Group A'
    
    df_b = df[df['Sample_id'].isin(group_b)].copy()
    df_b['Group'] = 'Group B'
    
    merged = pd.concat([df_a, df_b])
    
    # 提取表达矩阵
    expr_data = merged[target_cols].apply(pd.to_numeric, errors='coerce')
    meta_data = merged[['Sample_id', 'Group']]
    
    return (expr_data, meta_data, target_cols), None

def plot_boxplot(expr, meta, genes, out_path):
    """绘制箱线图"""
    plt.figure(figsize=(max(6, len(genes)*2), 6))
    
    # 构造绘图数据 (Long Format)
    plot_df = pd.concat([expr, meta], axis=1)
    plot_df = plot_df.melt(id_vars=['Sample_id', 'Group'], value_vars=genes, var_name='Gene', value_name='Expression')
    
    # 去掉 RNA_ 前缀让图好看点
    plot_df['Gene'] = plot_df['Gene'].str.replace('RNA_', '')
    
    sns.boxplot(x='Gene', y='Expression', hue='Group', data=plot_df, palette="Set2")
    sns.stripplot(x='Gene', y='Expression', hue='Group', data=plot_df, dodge=True, color='black', alpha=0.3, size=3)
    
    plt.title("Gene Expression Comparison")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_heatmap(expr, meta, genes, out_path):
    """绘制热图"""
    plt.figure(figsize=(8, 10))
    
    # 数据准备：行是基因，列是样本
    plot_data = expr.T
    
    # 简单的列注释颜色条 (实际 seaborn clustermap 支持更好)
    # 这里做个简单的 clustermap
    # 映射 Group 到颜色
    lut = dict(zip(meta['Group'].unique(), "rbg"))
    col_colors = meta['Group'].map(lut)
    
    g = sns.clustermap(plot_data, col_colors=col_colors, cmap="vlag", z_score=0, standard_scale=None)
    
    # 保存
    g.savefig(out_path, dpi=150)
    plt.close()

def plot_pca(expr, meta, out_path):
    """绘制 PCA"""
    # 填充缺失值
    X = expr.fillna(0)
    # 标准化
    X_scaled = StandardScaler().fit_transform(X)
    
    pca = PCA(n_components=2)
    coords = pca.fit_transform(X_scaled)
    
    pca_df = pd.DataFrame(coords, columns=['PC1', 'PC2'])
    pca_df['Group'] = meta['Group'].values
    
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x='PC1', y='PC2', hue='Group', data=pca_df, s=100, alpha=0.8, palette="Set1")
    
    plt.title(f"PCA Plot (Explained Var: {pca.explained_variance_ratio_[0]:.2f}, {pca.explained_variance_ratio_[1]:.2f})")
    plt.savefig(out_path, dpi=150)
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot_type", required=True)
    parser.add_argument("--genes", default="[]")
    parser.add_argument("--group_a", required=True)
    parser.add_argument("--group_b", required=True)
    parser.add_argument("--prefix", default="viz")
    
    try:
        args = parser.parse_args()
        
        # 解析参数
        ids_a = json.loads(args.group_a)
        ids_b = json.loads(args.group_b)
        gene_list = json.loads(args.genes) if args.genes else []
        
        # 1. 加载数据
        df = load_data()
        if df is None:
            print(json.dumps({"status": "error", "message": "Data load failed"}))
            return

        # 2. 准备绘图数据
        data_pkg, err = get_expression_data(df, gene_list, ids_a, ids_b)
        if err:
            print(json.dumps({"status": "error", "message": err}))
            return
            
        expr, meta, final_genes = data_pkg
        
        # 3. 绘图路由
        os.makedirs(RESULTS_DIR, exist_ok=True)
        safe_prefix = "".join([c for c in args.prefix if c.isalnum() or c in ('_','-')])
        out_path = os.path.join(RESULTS_DIR, f"{safe_prefix}_{args.plot_type}.png")
        
        if args.plot_type == "boxplot":
            plot_boxplot(expr, meta, final_genes, out_path)
        elif args.plot_type == "heatmap":
            plot_heatmap(expr, meta, final_genes, out_path)
        elif args.plot_type == "pca":
            plot_pca(expr, meta, out_path)
        else:
            print(json.dumps({"status": "error", "message": f"Unknown plot type: {args.plot_type}"}))
            return

        print(json.dumps({
            "status": "success",
            "data": {
                "plot_path": out_path,
                "plot_type": args.plot_type,
                "genes_plotted": [g.replace("RNA_", "") for g in final_genes]
            }
        }, ensure_ascii=False))

    except Exception as e:
        log(f"Error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()