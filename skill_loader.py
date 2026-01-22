import os
import re
import json
import subprocess
import sys
import shlex

class SkillLoader:
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        self.tools_schema = [] 
        self.tool_configs = {} 

    def load_all(self):
        """扫描目录加载所有 SKILL.md"""
        if not os.path.exists(self.skills_dir):
            print(f"[Loader] Error: Directory {self.skills_dir} not found.", file=sys.stderr)
            return

        print(f"[Loader] Scanning skills in: {self.skills_dir}...", file=sys.stderr)
        for folder in os.listdir(self.skills_dir):
            folder_path = os.path.join(self.skills_dir, folder)
            md_path = os.path.join(folder_path, "SKILL.md")
            if os.path.isdir(folder_path) and os.path.exists(md_path):
                try:
                    self._parse_skill(folder, md_path)
                except Exception as e:
                    print(f"[Loader] Failed to load {folder}: {e}", file=sys.stderr)

    def _parse_skill(self, folder_name, md_path):
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
        print(f"[Loader] Loaded Skill: {folder_name}", file=sys.stderr)

    def execute_tool(self, name, args_dict):
        if name not in self.tool_configs:
            return json.dumps({"status": "error", "message": f"Tool {name} not found"})
            
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
        
        # 解析模板命令以获取脚本路径
        # 模板格式类似: python skills/xxx/script.py --arg1 '{arg1}' --arg2 '{arg2}'
        parts = template.split()
        if len(parts) < 2:
            return json.dumps({"status": "error", "message": "Invalid command template"})
        
        python_cmd = parts[0]  # "python"
        script_path = parts[1]  # "skills/xxx/script.py"
        
        # 构建命令列表
        cmd_list = [sys.executable, script_path]
        
        # 从模板中解析参数名映射
        # 例如: --group_a '{group_a_ids}' 映射 group_a_ids -> --group_a
        arg_mapping = {}
        i = 2
        while i < len(parts):
            if parts[i].startswith('--'):
                arg_name = parts[i]  # --group_a
                if i + 1 < len(parts):
                    # 提取占位符名称，如 '{group_a_ids}' -> group_a_ids
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
            
        print(f"[System Exec]: {' '.join(cmd_list)}", file=sys.stderr)
        
        try:
            # 使用列表形式执行命令，避免 shell 解析问题
            result = subprocess.run(
                cmd_list, 
                shell=False,  # 不使用 shell，直接执行
                capture_output=True, 
                text=True,
                encoding='utf-8', 
                errors='replace',
                cwd=os.path.dirname(os.path.abspath(__file__))  # 设置工作目录
            )
            
            if result.stderr:
                print(f"[Tool Log]: {result.stderr}", file=sys.stderr)

            output = result.stdout.strip()
            if not output and result.stderr:
                 return json.dumps({"status": "error", "message": "No output", "debug": result.stderr})
            
            if not output:
                 return json.dumps({"status": "error", "message": "Empty output from script"})

            return output

        except Exception as e:
            return json.dumps({"status": "error", "message": f"Execution Exception: {str(e)}"})