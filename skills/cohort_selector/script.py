import argparse
import pandas as pd
import json
import os
import sys

def log(msg):
    sys.stderr.write(f"[Selector Log] {msg}\n")

FILENAME = "cleaned_data.csv"
SUB_DIR = "data"

def load_data():
    """加载 UTF-8 清洗数据"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    p = os.path.join(project_root, SUB_DIR, FILENAME)
    
    if os.path.exists(p):
        try:
            return pd.read_csv(p, encoding='utf-8')
        except Exception as e:
            log(f"Error reading {p}: {e}")
            return None
    return None

def find_best_column(df, keyword):
    """简化的搜索逻辑 (针对清洗后的表头)"""
    keyword = keyword.strip().strip("'").strip('"')
    kw_lower = keyword.lower()
    all_cols = df.columns.tolist()
    
    # 1. 构造标准前缀 (GENE_, RNA_, Organoid_)
    # 用户输入 "TP53" -> 找 "GENE_TP53"
    gene_col = f"GENE_{keyword.upper()}"
    if gene_col in all_cols: return gene_col, "prefix_gene"
    
    rna_col = f"RNA_{keyword.upper()}"
    if rna_col in all_cols: return rna_col, "prefix_rna"
    
    # 2. 药敏模糊匹配
    # Organoid_Sorafenib_Sensitive (下划线连接)
    drug_pattern = f"Organoid_{kw_lower}_Sensitive".lower()
    for col in all_cols:
        if col.lower() == drug_pattern:
            return col, "prefix_drug_sensitive"

    # 3. 常规模糊搜索
    candidates = [col for col in all_cols if kw_lower in col.lower()]
    if candidates:
        sens = [c for c in candidates if "Sensitive" in c]
        if sens: return sens[0], "fuzzy_sensitive"
        
        candidates.sort(key=len)
        return candidates[0], "fuzzy_shortest"
        
    return None, None

def split_cohort(df, col, method="auto"):
    valid_df = df.dropna(subset=[col])
    values = valid_df[col]
    unique_vals = values.unique()
    
    group_a_ids, group_b_ids = [], []
    name_a, name_b, method_info = "", "", ""

    is_binary_num = set(unique_vals).issubset({0, 1, 0.0, 1.0})
    
    if is_binary_num and len(unique_vals) <= 2:
        num_vals = pd.to_numeric(values, errors='coerce')
        group_a_ids = valid_df[num_vals == 1]['Sample_id'].tolist()
        group_b_ids = valid_df[num_vals == 0]['Sample_id'].tolist()
        name_a, name_b = f"{col}_Pos(1)", f"{col}_Neg(0)"
        method_info = "Binary(0/1)"
    elif any(str(x).lower() == "yes" for x in unique_vals) and any(str(x).lower() == "no" for x in unique_vals):
        mask_yes = valid_df[col].astype(str).str.lower() == "yes"
        group_a_ids = valid_df[mask_yes]['Sample_id'].tolist()
        group_b_ids = valid_df[~mask_yes]['Sample_id'].tolist()
        name_a, name_b = "Sensitive(Yes)", "Resistant(No)"
        method_info = "Categorical(Yes/No)"
    elif pd.to_numeric(values, errors='coerce').notna().all() and len(unique_vals) > 5:
        num_vals = pd.to_numeric(values)
        median = num_vals.median() if method != "quartile" else 0
        if method == "quartile":
            q75, q25 = num_vals.quantile(0.75), num_vals.quantile(0.25)
            group_a_ids = valid_df[num_vals >= q75]['Sample_id'].tolist()
            group_b_ids = valid_df[num_vals <= q25]['Sample_id'].tolist()
            name_a, name_b = f"High(Top25% >{q75:.2f})", f"Low(Bot25% <{q25:.2f})"
            method_info = "Numerical(Quartile)"
        else:
            group_a_ids = valid_df[num_vals >= median]['Sample_id'].tolist()
            group_b_ids = valid_df[num_vals < median]['Sample_id'].tolist()
            name_a, name_b = f"High(>={median:.2f})", f"Low(<{median:.2f})"
            method_info = "Numerical(Median)"
    else:
        top2 = values.value_counts().head(2).index.tolist()
        if len(top2) == 2:
            group_a_ids = valid_df[values == top2[0]]['Sample_id'].tolist()
            group_b_ids = valid_df[values == top2[1]]['Sample_id'].tolist()
            name_a, name_b = str(top2[0]), str(top2[1])
            method_info = "Top2Categories"
        else:
            return None, f"Cannot split column '{col}'"

    return {
        "Group_A": {"name": name_a, "count": len(group_a_ids), "samples": group_a_ids},
        "Group_B": {"name": name_b, "count": len(group_b_ids), "samples": group_b_ids},
        "info": method_info
    }, None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--method", default="auto")
    try:
        args = parser.parse_args()
        df = load_data()
        if df is None:
            print(json.dumps({"status": "error", "message": "Data load failed (check cleaned_data.csv)"}))
            return
        col, match_type = find_best_column(df, args.keyword)
        if not col:
            print(json.dumps({"status": "error", "message": f"Column not found: {args.keyword}"}))
            return
        log(f"Matched '{col}' ({match_type})")
        result, err = split_cohort(df, col, args.method)
        if err:
            print(json.dumps({"status": "error", "message": err}))
            return
        output = {
            "status": "success",
            "data": {
                "target_column": col,
                "split_method": result['info'],
                "cohorts": {"group_a": result['Group_A'], "group_b": result['Group_B']}
            }
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        log(f"Error: {e}")
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()