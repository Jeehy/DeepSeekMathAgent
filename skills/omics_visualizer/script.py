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
from datetime import datetime

# 设置 matplotlib 支持中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']  # 优先使用黑体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# === 协议辅助函数 ===
def log(msg):
    sys.stderr.write(f"[Visualizer Log] {msg}\n")

# === 配置 ===
DATA_FILE = "最终三表合一数据.csv"
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
    """复用标准加载逻辑"""
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

def get_expression_data(df, genes, group_a, group_b, group_a_name="Group A", group_b_name="Group B"):
    """提取绘图所需数据"""
    # 1. 转换基因名为列名 (支持用户输入 'TP53' 自动找 'RNA_TP53')
    target_cols = []
    if genes:
        all_cols = df.columns
        for g in genes:
            # 尝试直接匹配
            if g in all_cols: target_cols.append(g)
            # 尝试加 RNA_ 前缀
            elif f"RNA_{g}" in all_cols: target_cols.append(f"RNA_{g}")
            else: log(f"Warning: Gene {g} not found in data.")
    
    # PCA 模式下如果没有指定基因，使用所有 RNA 列（选方差最大的前500个）
    if not target_cols and not genes:
        rna_cols = [c for c in df.columns if c.startswith("RNA_")]
        # 简单取前 100 个做演示，实际应算方差
        target_cols = rna_cols[:100]

    if not target_cols:
        return None, "No valid genes found."

    # 2. 提取并标记分组 (使用自定义组名)
    df_a = df[df['Sample_id'].isin(group_a)].copy()
    df_a['Group'] = group_a_name
    
    df_b = df[df['Sample_id'].isin(group_b)].copy()
    df_b['Group'] = group_b_name
    
    merged = pd.concat([df_a, df_b])
    
    # 提取表达矩阵
    expr_data = merged[target_cols].apply(pd.to_numeric, errors='coerce')
    meta_data = merged[['Sample_id', 'Group']]
    
    return (expr_data, meta_data, target_cols), None

def plot_boxplot(expr, meta, genes, out_path, sample_type=""):
    """绘制箱线图
    
    Args:
        expr: 表达矩阵
        meta: 元数据
        genes: 基因列表
        out_path: 输出路径
        sample_type: 样本类型 (如 "病人样本", "类器官样本")
    """
    plt.figure(figsize=(max(6, len(genes)*2), 6))
    
    # 构造绘图数据 (Long Format)
    plot_df = pd.concat([expr, meta], axis=1)
    plot_df = plot_df.melt(id_vars=['Sample_id', 'Group'], value_vars=genes, var_name='Gene', value_name='Expression')
    
    # 去掉 RNA_ 前缀让图好看点
    plot_df['Gene'] = plot_df['Gene'].str.replace('RNA_', '')
    
    sns.boxplot(x='Gene', y='Expression', hue='Group', data=plot_df, palette="Set2")
    sns.stripplot(x='Gene', y='Expression', hue='Group', data=plot_df, dodge=True, color='black', alpha=0.3, size=3)
    
    # 添加样本类型到标题
    title = "基因表达量对比"
    if sample_type:
        title = f"{title} ({sample_type})"
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel("基因", fontsize=12)
    plt.ylabel("表达量", fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def plot_heatmap(expr, meta, genes, out_path, sample_type=""):
    """绘制热图
    
    Args:
        expr: 表达矩阵
        meta: 元数据
        genes: 基因列表
        out_path: 输出路径
        sample_type: 样本类型 (如 "病人样本", "类器官样本")
    """
    plt.figure(figsize=(8, 10))
    
    # 数据准备：行是基因，列是样本
    plot_data = expr.T
    
    # 简单的列注释颜色条 (实际 seaborn clustermap 支持更好)
    # 这里做个简单的 clustermap
    # 映射 Group 到颜色
    lut = dict(zip(meta['Group'].unique(), "rbg"))
    col_colors = meta['Group'].map(lut)
    
    g = sns.clustermap(plot_data, col_colors=col_colors, cmap="vlag", z_score=0, standard_scale=None)
    
    # 添加样本类型到标题
    title = "基因表达热图"
    if sample_type:
        title = f"{title} ({sample_type})"
    g.fig.suptitle(title, fontsize=14, fontweight='bold', y=0.98)
    
    # 保存
    g.savefig(out_path, dpi=150)
    plt.close()

def plot_pca(expr, meta, out_path, sample_type=""):
    """绘制 PCA
    
    Args:
        expr: 表达矩阵
        meta: 元数据
        out_path: 输出路径
        sample_type: 样本类型 (如 "病人样本", "类器官样本")
    """
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
    
    # 添加样本类型到标题
    var_explained = f"(解释方差: PC1={pca.explained_variance_ratio_[0]:.2%}, PC2={pca.explained_variance_ratio_[1]:.2%})"
    title = f"PCA主成分分析 {var_explained}"
    if sample_type:
        title = f"PCA主成分分析 ({sample_type}) {var_explained}"
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.2%})', fontsize=12)
    plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.2%})', fontsize=12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def main():
    # 设置标准输出编码为 UTF-8
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot_type", required=True)
    parser.add_argument("--genes", default="[]")
    parser.add_argument("--group_a", required=True)
    parser.add_argument("--group_b", required=True)
    parser.add_argument("--group_a_name", default="Group A", help="显示在图表中的 Group A 名称")
    parser.add_argument("--group_b_name", default="Group B", help="显示在图表中的 Group B 名称")
    parser.add_argument("--sample_type", default="", help="样本类型说明 (如 '病人样本', '类器官样本')")
    parser.add_argument("--prefix", default="viz")
    
    try:
        args = parser.parse_args()
        
        # 解析参数
        ids_a = json.loads(args.group_a)
        ids_b = json.loads(args.group_b)
        gene_list = json.loads(args.genes) if args.genes else []
        group_a_name = args.group_a_name if args.group_a_name else "Group A"
        group_b_name = args.group_b_name if args.group_b_name else "Group B"
        sample_type = args.sample_type if args.sample_type else ""
        
        # 1. 加载数据
        df = load_data()
        if df is None:
            print(json.dumps({"status": "error", "message": "Data load failed"}))
            return

        # 2. 准备绘图数据 (传入自定义组名)
        data_pkg, err = get_expression_data(df, gene_list, ids_a, ids_b, group_a_name, group_b_name)
        if err:
            print(json.dumps({"status": "error", "message": err}))
            return
            
        expr, meta, final_genes = data_pkg
        
        # 3. 绘图路由 (使用会话目录)
        session_dir = get_session_results_dir()
        safe_prefix = "".join([c for c in args.prefix if c.isalnum() or c in ('_','-')])
        out_path = os.path.join(session_dir, f"{safe_prefix}_{args.plot_type}.png")
        
        if args.plot_type == "boxplot":
            plot_boxplot(expr, meta, final_genes, out_path, sample_type)
        elif args.plot_type == "heatmap":
            plot_heatmap(expr, meta, final_genes, out_path, sample_type)
        elif args.plot_type == "pca":
            plot_pca(expr, meta, out_path, sample_type)
        else:
            print(json.dumps({"status": "error", "message": f"Unknown plot type: {args.plot_type}"}))
            return

        print(json.dumps({
            "status": "success",
            "data": {
                "plot_path": out_path,
                "plot_url": os.path.relpath(out_path, RESULTS_BASE_DIR).replace("\\", "/"),  # 返回相对路径用于API访问
                "plot_type": args.plot_type,
                "genes_plotted": [g.replace("RNA_", "") for g in final_genes],
                "sample_type": sample_type
            }
        }, ensure_ascii=False))

    except Exception as e:
        log(f"Error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()