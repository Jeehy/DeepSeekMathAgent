import os, sys, json, requests
from skill_loader import SkillLoader
from dotenv import load_dotenv
from typing import Generator, Dict, Any, Optional
from datetime import datetime

# 加载 .env 文件
load_dotenv()

# ================= 配置区 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY not found. Please set it in .env file")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL_NAME = "deepseek-chat"
# =========================================

class DrKGCAgent:
    """
    DrKGC (Autonomous Bio-Researcher) Agent
    具备逻辑闭环能力的科研助手，基于"证据三角"进行分析
    """
    
    def __init__(self, skills_dir="skills"):
        """
        初始化 Agent
        
        Args:
            skills_dir: 技能目录路径
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        skills_path = os.path.join(base_dir, skills_dir)
        self.loader = SkillLoader(skills_path)
        self.loader.load_all()
        self.messages = []
        self.reset_conversation()

    def reset_conversation(self):
        """重置对话历史"""
        self.messages = [{"role": "system", "content": self._build_system_prompt()}]

    def _build_system_prompt(self):
        """构建系统提示词"""
        return """你是由 DeepSeek 驱动的 **DrKGC (Autonomous Bio-Researcher)**。
你不是一个流水线工人，你是一位**首席科学家 (PI)**。
你的核心能力是**自主编排 (Autonomous Orchestration)**：根据实时的分析结果，动态决定下一步做什么，以回答复杂的科学问题。

### 🎯 你的科学目标
用户通常希望寻找**"潜在靶点"**。这包含两层含义：
1.  **Known Targets (基准)**: 经典的致病基因 (如 TP53, CTNNB1)。*用途：验证数据质量，建立置信度。*
2.  **Novel Candidates (创新)**: **这才是重点！** 那些在组学数据中表现出强相关性，但在现有知识图谱中连接度不高，或尚未被广泛研究的基因。

### 🧬 核心分析哲学 (Analytical Philosophy)
在处理任何生物学问题时，你必须遵循以下**三原则**：
1.  **数据分层视角的严谨性 (Contextual Rigor)**：
    * 高度关注**样本量平衡性** (例如 Patient层级常出现的 70 vs 7)。
    * 对于不平衡数据集，当统计结果不显著时，必须主动提示"统计效能 (Statistical Power) 可能受限"，而不是直接否定差异。
2.  **视觉-统计一致性评估 (Visual-Statistical Concordance)**：
    * **拒绝盲目依赖 P-value**。当 P > 0.05 但箱线图显示明显组间差异时，这通常意味着**"生物学异质性 (Biological Heterogeneity)"**。
    * **判定逻辑**：若一组方差极小（高度均一），另一组方差极大（存在长尾/离群点），**必须**将此解读为**"潜在的亚群特异性反应 (Subpopulation-specific response)"**或**"耐药克隆演化"**，而非简单的"无差异"。
3.  **因果裁判权 (Causal Adjudication)**：
    * 利用 `causal_reasoner` 区分"伴随现象 (Passenger)"与"驱动事件 (Driver)"。

### 🛠️ 你的武器库 (Toolbox)
* **数据层 (What is happening?)**: `cohort_selector`, `omics_dea`, `omics_visualizer`.
* **机制层 (Why it happens?)**: `enrichment_analysis` (将冷冰冰的基因列表转化为生物学故事).
* **知识层 (What do we know?)**: `kg_pathfinder`, `literature_search`.
* **逻辑层 (Is it true?)**: `causal_reasoner` (因果裁判).

### 🧠 自主编排思维链 (Decision Engine)

在每一步行动前，你必须进行深度的**态势感知**：

#### Phase 1: 战略规划 (Strategy)
* 当用户问"发现潜在靶点"时，不要只跑 KG！**只看 KG 永远找不到新靶点。**
* **正确的发现路径**:
    1.  先看数据 (`omics_dea`): 谁在耐药组里疯涨？这是最真实的信号。
    2.  再看机制 (`enrichment_analysis`): 这些疯涨的基因在干什么？(如: 都在修DNA? 都在搞代谢?)
    3.  最后看知识 (`kg_pathfinder` + `literature_search`): 
        - 如果是 Known Gene -> 标记为"验证"。
        - **如果是 Novel Gene (数据强但KG弱)** -> **这是宝藏！** 重点分析它的文献和因果性。

#### Phase 2: 动态调整 (Dynamic Adjustment)
* **场景 A**: `omics_dea` 找到了几百个差异基因，太多了。
    * *决策*: 立即调用 `enrichment_analysis`，通过通路来聚类，找到核心机制（如 "PI3K-Akt signaling"），然后只关注该通路下的基因。
* **场景 B**: `kg_pathfinder` 推荐了 EGFR，但 `omics_dea` 数据里 EGFR 没差异。
    * *决策*: 诚实报告。思考是否是下游基因（如 ERK/MAPK）在变？调用 `omics_visualizer` 检查下游基因。
* **场景 C**: 发现一个陌生基因 `XYZ` 极其显著且富集在关键通路。
    * *决策*: 它是潜在的新靶点！马上调用 `literature_search` 查它在其他癌症中的作用，并用 `causal_reasoner` 推演。

###  数据集特性 (CRITICAL - Dataset Info)
**当前数据集**: 肝癌类器官药物敏感性数据 (81例样本)
- **药物敏感性数据有两个层级**:
  1. **Patient 层级** (病人临床反应): 
     - `Patient_Sorafenib`, `Patient_Lenvatinib`, `Patient_Regorafenib`, `Patient_Apatinib`
     - 表示病人对药物的实际临床反应
  2. **Organoid 层级** (类器官体外实验):
     - `Organoid_Sorafenib_Sensitive` (0=耐药, 1=敏感)
     - `Organoid_Lenvatinib_Sensitive`, `Organoid_Regorafenib_Sensitive` 等
     - 还有 IC50、AUC 等连续变量

### ⚠️ 分组策略 (Grouping Strategy)
**根据用户的自然语言描述选择正确的列名传递给工具**:
- 用户说"**病人**对xx药物" → 传 `Patient_药物名` (如 `--keyword Patient_Regorafenib`)，**同时在绘图时设置 `--sample_type "病人样本"`**
- 用户说"**类器官**对xx药物" → 传 `Organoid_药物名_Sensitive` (如 `--keyword Organoid_Regorafenib_Sensitive`)，**同时在绘图时设置 `--sample_type "类器官样本"`**
- 用户只说药物名没有指定 → **询问用户**是要病人层级还是类器官层级
- 如需限定肿瘤类型，可以先说明分析的是 HCC 还是 ICC 亚群
- **CRITICAL**: 在调用 `omics_visualizer` 时，必须根据分析的样本类型传递 `sample_type` 参数，这样图表标题会明确标注样本来源

### 👁️ 图像解读标准 (Visual Interpretation Standards)**
**禁止只展示图片**。你必须充当用户的眼睛，对图表进行微观描述：
* **中位数 (Median)**: 描述组间中心趋势的位移。
* **四分位距 (IQR)**: 描述箱体高度。箱体越长，代表**转录组异质性 (Transcriptional Heterogeneity)** 越高。
* **离群值 (Outliers)**: 识别是否存在高表达的极端样本，这通常暗示**耐药克隆**的存在。

### ⚠️ 严格遵守用户输入 (CRITICAL)
**绝对禁止修改用户输入的基因名或关键词！**
- 用户输入 "STAMP" → 必须搜索 "STAMP"，不能改成 STEAP1、STAM 或其他类似名称
- 用户输入 "ABC123" → 即使看起来像拼写错误，也必须原样使用
- 如果搜索无结果，直接告知用户"未找到相关信息"，而不是擅自更换搜索词
- 这是**硬性规定**，违反将导致严重的用户信任问题

### 📋 报告输出格式 (CRITICAL - Report Format)
**最终回复必须使用以下结构化格式，全部使用中文：**
* 分组命名时，必须映射为有意义的名称 (如 `group_a_name="敏感"`, `group_b_name="耐药"`)，**严禁**使用 "Group A"。
* 绘图时必须传递 `sample_type` 参数 (如 `sample_type="病人样本"` 或 `sample_type="类器官样本"`)，确保图表标题清晰标注样本来源。
```
## 🎯 验证报告：[基因名/主题]

### 一、因果推理分析
[基于 causal_reasoner 的分析结果]
- **判定结论**：[Causal/Non-Causal/Uncertain]
- **推理依据**：[详细说明生物学机制]

### 二、知识图谱验证
[基于 kg_pathfinder 的分析结果]
- **已知靶点状态**：[是/否/待验证]
- **关联通路**：[列出关键通路]
- **相互作用网络**：[PPI 信息]

### 三、文献证据支持
[基于 literature_search 的分析结果]
- **支持度**：[强/中/弱]
- **关键发现**：[总结文献要点]
<!-- LITERATURE_EVIDENCE -->

### 四、组学数据验证
[基于 omics_dea/omics_visualizer 的分析结果]
- **统计特征**：[Log2FC, p-value 等统计数据]
- **数据解读**：[详细描述箱线图。必须包含关键词："异质性", "分布偏态", "离群样本"。]
<!-- OMICS_PLOTS -->

### 五、综合结论
[整合所有证据的最终判断，全部使用中文]
- **靶点可信度**：⭐⭐⭐⭐⭐ (1-5星)
- **核心证据**：[最关键的支撑点]
- **研究建议**：[下一步研究方向]
```

**重要说明**：
1. 在"文献证据支持"章节末尾添加 `<!-- LITERATURE_EVIDENCE -->` 标记
2. 在"组学数据验证"章节末尾添加 `<!-- OMICS_PLOTS -->` 标记
3. 所有结论和总结必须使用**中文**撰写
4. 对数据的解读要具体说明图表展示的内容和意义

### ⚠️ 输出规范 (Critical Output Rules)
1.  **拒绝机械报幕**: 不要只说"我运行了工具，结果如下"。要说"**数据结果显示 X 基因显著上调，这提示...，为了验证这一点，我决定下一步...**"。
2.  **挖掘新意**: 报告中必须区分 **[经典靶点验证]** 和 **[潜在新靶点发现]**。
3.  **富集必做**: 拿到基因列表后，**必须**自动做富集分析，否则无法理解生物学意义。
4.  **因果为王**: 如果数据相关性很高（R>0.8），但 `causal_reasoner` 判定 "No Causality"，你必须提出警告。
5.  **数据诚实**: 既然知道数据有局限性，在汇报组学结果时请使用"在我们有限的数据集中..."或"初步数据表明..."这样的措辞。
6.  **回复语言**: 全部使用中文回复用户。
"""

    def call_deepseek(self) -> Optional[Dict]:
        """调用 DeepSeek API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": self.messages,
            "stream": False,
            "temperature": 0.0,
            "tools": self.loader.tools_schema if self.loader.tools_schema else None,
            "tool_choice": "auto" if self.loader.tools_schema else None
        }
        
        # 如果没有工具，移除相关字段
        if not self.loader.tools_schema:
            payload.pop("tools", None)
            payload.pop("tool_choice", None)
            
        try:
            print("\n🤖 [Agent] DeepSeek 正在思考...", file=sys.stderr)
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ API 错误: {e}", file=sys.stderr)
            return None

    def call_deepseek_stream(self) -> Generator[Dict, None, None]:
        """流式调用 DeepSeek API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": MODEL_NAME,
            "messages": self.messages,
            "stream": True,
            "temperature": 0.0,
            "tools": self.loader.tools_schema if self.loader.tools_schema else None,
            "tool_choice": "auto" if self.loader.tools_schema else None
        }
        
        if not self.loader.tools_schema:
            payload.pop("tools", None)
            payload.pop("tool_choice", None)
            
        try:
            response = requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data_str = line_text[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            yield json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"❌ 流式 API 错误: {e}", file=sys.stderr)
            yield {"error": str(e)}

    def run(self, user_query: str, max_steps: int = 25) -> str:
        """
        运行 Agent（同步模式）
        
        Args:
            user_query: 用户查询
            max_steps: 最大推理步数 (探索任务通常需要更多步骤)
            
        Returns:
            最终回复内容
        """
        print(f"\n👤 User: {user_query}")
        self.messages.append({"role": "user", "content": user_query})
        step_count = 0
        final_response = ""

        while step_count < max_steps:
            step_count += 1
            response_data = self.call_deepseek()
            if not response_data:
                break
            
            msg = response_data['choices'][0]['message']
            content = msg.get('content')
            tool_calls = msg.get('tool_calls')

            if content:
                print(f"\n🧠 [Thought]: {content}")
                final_response = content
                
            self.messages.append(msg)

            if tool_calls:
                print(f"🛠️  [Action]: 需要调用 {len(tool_calls)} 个工具...")
                for tc in tool_calls:
                    func_name = tc['function']['name']
                    args_str = tc['function']['arguments']
                    tool_id = tc['id']
                    try:
                        args = json.loads(args_str)
                        print(f"   📍 调用 {func_name}({args})")
                        result_str = self.loader.execute_tool(func_name, args)
                        preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
                        print(f"   ✅ 结果: {preview}")
                        self.messages.append({
                            "role": "tool", 
                            "tool_call_id": tool_id, 
                            "name": func_name, 
                            "content": result_str
                        })
                    except Exception as e:
                        err = json.dumps({"status": "error", "message": str(e)})
                        self.messages.append({
                            "role": "tool", 
                            "tool_call_id": tool_id, 
                            "name": func_name, 
                            "content": err
                        })
                continue
            else:
                print(f"\n🎉 [Done]: 分析完成!")
                break
                
        return final_response

    def run_stream(self, user_query: str, max_steps: int = 25) -> Generator[Dict[str, Any], None, None]:
        """
        运行 Agent（流式模式）
        
        Args:
            user_query: 用户查询
            max_steps: 最大推理步数 (探索任务通常需要更多步骤)
            
        Yields:
            流式事件字典
        """
        self.messages.append({"role": "user", "content": user_query})
        step_count = 0
        
        yield {
            "type": "start",
            "query": user_query,
            "timestamp": datetime.now().isoformat()
        }

        while step_count < max_steps:
            step_count += 1
            
            yield {
                "type": "thinking",
                "step": step_count,
                "timestamp": datetime.now().isoformat()
            }
            
            response_data = self.call_deepseek()
            if not response_data:
                yield {
                    "type": "error",
                    "message": "API 调用失败",
                    "timestamp": datetime.now().isoformat()
                }
                break
            
            msg = response_data['choices'][0]['message']
            content = msg.get('content')
            tool_calls = msg.get('tool_calls')
            
            self.messages.append(msg)

            if content:
                yield {
                    "type": "thought",
                    "content": content,
                    "step": step_count,
                    "timestamp": datetime.now().isoformat()
                }

            if tool_calls:
                for tc in tool_calls:
                    func_name = tc['function']['name']
                    args_str = tc['function']['arguments']
                    tool_id = tc['id']
                    
                    yield {
                        "type": "tool_call",
                        "tool": func_name,
                        "arguments": args_str,
                        "step": step_count,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    try:
                        args = json.loads(args_str)
                        result_str = self.loader.execute_tool(func_name, args)
                        
                        yield {
                            "type": "tool_result",
                            "tool": func_name,
                            "result": result_str,  # 返回完整结果，前端需要解析详细信息
                            "step": step_count,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": func_name,
                            "content": result_str
                        })
                    except Exception as e:
                        err = json.dumps({"status": "error", "message": str(e)})
                        yield {
                            "type": "tool_error",
                            "tool": func_name,
                            "error": str(e),
                            "step": step_count,
                            "timestamp": datetime.now().isoformat()
                        }
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": func_name,
                            "content": err
                        })
                continue
            else:
                yield {
                    "type": "complete",
                    "final_answer": content,
                    "total_steps": step_count,
                    "timestamp": datetime.now().isoformat()
                }
                break

    def get_available_tools(self) -> list:
        """获取可用工具列表"""
        return self.loader.get_tools_description()


if __name__ == "__main__":
    agent = DrKGCAgent()
    print(f"✅ 工具箱已就绪: {list(agent.loader.tool_configs.keys())}")
    
    while True:
        try:
            query = input("\n请输入您的分析需求 (输入 'exit' 退出): ")
            if query.strip().lower() == 'exit': break
            if not query.strip(): continue
            agent.run(query)
        except KeyboardInterrupt: break
