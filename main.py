import os, sys, json, requests
from skill_loader import SkillLoader

# ================= 配置区 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-ac20fb761a324d7888bda5e07178f8b9")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"
# =========================================

class DrKGCAgent:
    def __init__(self, skills_dir="skills"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        skills_path = os.path.join(base_dir, skills_dir)
        self.loader = SkillLoader(skills_path)
        self.loader.load_all()
        self.messages = [{"role": "system", "content": self._build_system_prompt()}]

    def _build_system_prompt(self):
        return """你是由 DeepSeek 驱动的 **DrKGC (Autonomous Bio-Researcher)**。
你不是一个流水线工人，你是一位**首席科学家 (PI)**。
你的核心能力是**自主编排 (Autonomous Orchestration)**：根据实时的分析结果，动态决定下一步做什么，以回答复杂的科学问题。

### 🎯 你的科学目标
用户通常希望寻找**“潜在靶点”**。这包含两层含义：
1.  **Known Targets (基准)**: 经典的致病基因 (如 TP53, CTNNB1)。*用途：验证数据质量，建立置信度。*
2.  **Novel Candidates (创新)**: **这才是重点！** 那些在组学数据中表现出强相关性，但在现有知识图谱中连接度不高，或尚未被广泛研究的基因。

### 🛠️ 你的武器库 (Toolbox)
* **数据层 (What is happening?)**: `cohort_selector`, `omics_dea`, `omics_visualizer`.
* **机制层 (Why it happens?)**: `enrichment_analysis` (将冷冰冰的基因列表转化为生物学故事).
* **知识层 (What do we know?)**: `kg_pathfinder`, `literature_search`.
* **逻辑层 (Is it true?)**: `causal_reasoner` (因果裁判).

### 🧠 自主编排思维链 (Decision Engine)

在每一步行动前，你必须进行深度的**态势感知**：

#### Phase 1: 战略规划 (Strategy)
* 当用户问“发现潜在靶点”时，不要只跑 KG！**只看 KG 永远找不到新靶点。**
* **正确的发现路径**:
    1.  先看数据 (`omics_dea`): 谁在耐药组里疯涨？这是最真实的信号。
    2.  再看机制 (`enrichment_analysis`): 这些疯涨的基因在干什么？(如: 都在修DNA? 都在搞代谢?)
    3.  最后看知识 (`kg_pathfinder` + `literature_search`): 
        - 如果是 Known Gene -> 标记为“验证”。
        - **如果是 Novel Gene (数据强但KG弱)** -> **这是宝藏！** 重点分析它的文献和因果性。

#### Phase 2: 动态调整 (Dynamic Adjustment)
* **场景 A**: `omics_dea` 找到了几百个差异基因，太多了。
    * *决策*: 立即调用 `enrichment_analysis`，通过通路来聚类，找到核心机制（如 "PI3K-Akt signaling"），然后只关注该通路下的基因。
* **场景 B**: `kg_pathfinder` 推荐了 EGFR，但 `omics_dea` 数据里 EGFR 没差异。
    * *决策*: 诚实报告。思考是否是下游基因（如 ERK/MAPK）在变？调用 `omics_visualizer` 检查下游基因。
* **场景 C**: 发现一个陌生基因 `XYZ` 极其显著且富集在关键通路。
    * *决策*: 它是潜在的新靶点！马上调用 `literature_search` 查它在其他癌症中的作用，并用 `causal_reasoner` 推演。

### ⚠️ 输出规范 (Critical Output Rules)
1.  **拒绝机械报幕**: 不要只说“我运行了工具，结果如下”。要说“**数据结果显示 X 基因显著上调，这提示...，为了验证这一点，我决定下一步...**”。
2.  **挖掘新意**: 报告中必须区分 **[经典靶点验证]** 和 **[潜在新靶点发现]**。
3.  **富集必做**: 拿到基因列表后，**必须**自动做富集分析，否则无法理解生物学意义。
"""

    def call_deepseek(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        # tool_choice="auto": 赋予你完全的自主权
        payload = {
            "model": MODEL_NAME,
            "messages": self.messages,
            "stream": False,
            "temperature": 0.0,
            "tools": self.loader.tools_schema, 
            "tool_choice": "auto" 
        }
        try:
            print("\n🤖 [Agent] DeepSeek is thinking...", file=sys.stderr)
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ API Error: {e}", file=sys.stderr)
            return None

    def run(self, user_query):
        print(f"\nUser: {user_query}")
        self.messages.append({"role": "user", "content": user_query})
        step_count = 0
        max_steps = 25 # 探索任务通常需要更多步骤

        while step_count < max_steps:
            step_count += 1
            response_data = self.call_deepseek()
            if not response_data: break
            
            msg = response_data['choices'][0]['message']
            content = msg.get('content')
            tool_calls = msg.get('tool_calls')

            if content: print(f"\n🧠 [Thought]: {content}")
            self.messages.append(msg)

            if tool_calls:
                print(f"🛠️  [Action]: DeepSeek decided to call {len(tool_calls)} tools...")
                for tc in tool_calls:
                    func_name = tc['function']['name']
                    args_str = tc['function']['arguments']
                    tool_id = tc['id']
                    try:
                        args = json.loads(args_str)
                        # 执行工具
                        print(f"   -> Executing: {func_name}(...)") 
                        result_str = self.loader.execute_tool(func_name, args)
                        
                        # 结果预览
                        preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                        print(f"   -> [Output]: {preview}")
                        
                        self.messages.append({"role": "tool", "tool_call_id": tool_id, "name": func_name, "content": result_str})
                    except Exception as e:
                        err = json.dumps({"status": "error", "message": str(e)})
                        self.messages.append({"role": "tool", "tool_call_id": tool_id, "name": func_name, "content": err})
                continue 
            else:
                print(f"\n🎉 [Done]: Analysis Completed!")
                break

if __name__ == "__main__":
    agent = DrKGCAgent()
    # 修复了这里的属性引用错误: skills -> tool_configs
    print(f"✅ Toolbox Ready: {list(agent.loader.tool_configs.keys())}")
    
    while True:
        try:
            query = input("\n请输入您的分析需求 (输入 'exit' 退出): ")
            if query.strip().lower() == 'exit': break
            if not query.strip(): continue
            agent.run(query)
        except KeyboardInterrupt: break