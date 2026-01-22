import os
import re
import json
import subprocess
import sys
from datetime import datetime

class SkillLoader:
    """技能加载器，负责从 SKILL.md 文件加载技能定义并执行"""
    
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        self.tools_schema = []  # OpenAI 格式的工具定义
        self.tool_configs = {}  # 工具配置信息
        self.session_id = None  # 当前会话ID

    def load_all(self):
        """扫描目录加载所有 SKILL.md"""
        if not os.path.exists(self.skills_dir):
            print(f"[SkillLoader] ⚠️ 目录不存在: {self.skills_dir}", file=sys.stderr)
            return

        print(f"[SkillLoader] 🔍 扫描技能目录: {self.skills_dir}...", file=sys.stderr)
        for folder in os.listdir(self.skills_dir):
            folder_path = os.path.join(self.skills_dir, folder)
            md_path = os.path.join(folder_path, "SKILL.md")
            if os.path.isdir(folder_path) and os.path.exists(md_path):
                try:
                    self._parse_skill(folder, md_path)
                except Exception as e:
                    print(f"[SkillLoader] ❌ 加载技能 {folder} 失败: {e}", file=sys.stderr)

    def _parse_skill(self, folder_name, md_path):
        """解析 SKILL.md 文件，提取工具定义"""
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        desc_match = re.search(r'## Description\s+(.*?)\s+##', content, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else "No description"

        cmd_match = re.search(r'## Command\s+`?(.*?)`?(\n|$)', content)
        command_template = cmd_match.group(1).strip() if cmd_match else ""

        params_props = {}
        required_params = []
        param_lines = re.findall(r'-\s+(\w+)\s+\((.*?)\):\s+(.*)', content)
        
        for p_name, p_meta, p_desc in param_lines:
            p_type = "string"
            if "array" in p_meta.lower() or "list" in p_meta.lower():
                p_type = "array"
            
            params_props[p_name] = {
                "type": p_type,
                "description": p_desc.strip()
            }
            if p_type == "array":
                params_props[p_name]["items"] = {"type": "string"}
                
            if "required" in p_meta.lower():
                required_params.append(p_name)

        tool_def = {
            "type": "function",
            "function": {
                "name": folder_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": params_props,
                    "required": required_params
                }
            }
        }
        
        self.tools_schema.append(tool_def)
        self.tool_configs[folder_name] = {
            "command_template": command_template,
            "cwd": os.path.join(self.skills_dir, folder_name)
        }
        print(f"[SkillLoader] ✅ 已加载技能: {folder_name}", file=sys.stderr)

    def set_session_id(self, session_id=None):
        """设置当前会话ID，用于区分不同分析任务的结果目录"""
        if session_id:
            self.session_id = session_id
        else:
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[SkillLoader] 📁 会话ID: {self.session_id}", file=sys.stderr)
        return self.session_id

    def execute_tool(self, name, args_dict):
        """执行指定工具"""
        if name not in self.tool_configs:
            return json.dumps({"status": "error", "message": f"工具 {name} 未找到"})
            
        config = self.tool_configs[name]
        template = config["command_template"]
        cwd = config.get("cwd", ".")
        
        # 构建参数列表而不是命令字符串
        # 从模板中提取基础命令部分
        # 收集所有参数
        args_list = []
        for key, val in args_dict.items():
            if isinstance(val, (list, dict)):
                # 对于数组/字典参数，转为 JSON 字符串
                args_list.append((key, json.dumps(val, ensure_ascii=False)))
            else:
                args_list.append((key, str(val)))
        
        # 解析模板命令
        parts = template.split()
        if len(parts) < 2:
            return json.dumps({"status": "error", "message": "无效的命令模板"})
        
        script_path = parts[1]
        
        # 构建命令列表
        cmd_list = [sys.executable, script_path]
        
        # 从模板中解析参数名映射
        arg_mapping = {}
        i = 2
        while i < len(parts):
            if parts[i].startswith('--'):
                arg_name = parts[i]
                if i + 1 < len(parts):
                    placeholder = parts[i + 1].strip("'\"")
                    match = re.match(r'\{(\w+)\}', placeholder)
                    if match:
                        param_name = match.group(1)
                        arg_mapping[param_name] = arg_name
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        
        # 添加参数到命令列表
        for key, val in args_list:
            arg_flag = arg_mapping.get(key, f"--{key}")
            cmd_list.append(arg_flag)
            cmd_list.append(val)
            
        print(f"[SkillLoader] 🔧 执行: {' '.join(cmd_list)}", file=sys.stderr)
        
        try:
            # Windows 环境设置环境变量确保 Python 子进程使用 UTF-8
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            # 传递会话ID到子进程，用于结果目录管理
            # 如果没有设置会话ID，自动创建一个
            if not self.session_id:
                self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            env['AITARGET_SESSION_ID'] = self.session_id
            print(f"[SkillLoader] 📤 传递会话ID: {self.session_id}", file=sys.stderr)
            
            result = subprocess.run(
                cmd_list, 
                shell=False,
                capture_output=True, 
                text=True,
                encoding='utf-8', 
                errors='replace',
                cwd=os.path.dirname(os.path.abspath(__file__)),
                env=env
            )
            
            if result.stderr:
                print(f"[SkillLoader] 📝 工具日志: {result.stderr}", file=sys.stderr)

            output = result.stdout.strip()
            if not output and result.stderr:
                return json.dumps({"status": "error", "message": "无输出", "debug": result.stderr})
            
            if not output:
                return json.dumps({"status": "error", "message": "脚本输出为空"})

            return output

        except Exception as e:
            return json.dumps({"status": "error", "message": f"执行异常: {str(e)}"})

    def get_tools_description(self):
        """获取所有工具的简要描述"""
        descriptions = []
        for tool in self.tools_schema:
            func = tool.get("function", {})
            descriptions.append({
                "name": func.get("name"),
                "description": func.get("description", "")[:100] + "..."
            })
        return descriptions