#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
DeepSeekMathAgent 配置文件
"""
import os
from datetime import datetime

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"

# Skills 目录配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "skills")

# 数据目录配置  
DATA_DIR = os.path.join(BASE_DIR, "data")

# 结果输出目录 (基础目录)
RESULTS_DIR = os.path.join(BASE_DIR, "results")
RESULT_OUTPUT_DIR = RESULTS_DIR  # 兼容别名

# 当前会话结果目录 (每次分析创建新文件夹)
_current_session_dir = None

def get_session_results_dir(session_id=None):
    """
    获取当前会话的结果目录
    每次新分析会创建一个带时间戳的新文件夹
    
    Args:
        session_id: 可选的会话ID，如果不提供则使用时间戳
    
    Returns:
        当前会话的结果目录路径
    """
    global _current_session_dir
    if _current_session_dir is None or session_id:
        if session_id:
            folder_name = session_id
        else:
            folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        _current_session_dir = os.path.join(RESULTS_DIR, folder_name)
        os.makedirs(_current_session_dir, exist_ok=True)
    return _current_session_dir

def reset_session_dir():
    """重置会话目录，下次调用 get_session_results_dir 时会创建新目录"""
    global _current_session_dir
    _current_session_dir = None

# 确保目录存在
os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
