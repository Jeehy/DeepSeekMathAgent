# DeepSeekMathAgent 环境配置说明

## 🔧 配置 API 密钥

本项目已将所有 DeepSeek API 密钥配置迁移到 `.env` 文件中。

### 设置步骤：

1. **复制示例文件**：
   ```bash
   cp .env.example .env
   ```

2. **编辑 `.env` 文件**：
   在项目根目录下找到 `.env` 文件，并设置你的 API 密钥：
   ```env
   DEEPSEEK_API_KEY=your_actual_api_key_here
   ```

3. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

### 📝 注意事项：

- ⚠️ **不要将 `.env` 文件提交到 Git**：该文件已添加到 `.gitignore` 中
- ✅ **使用 `.env.example`**：作为配置模板分享给其他开发者
- 🔒 **保护 API 密钥**：不要在代码中硬编码或公开 API 密钥

### 📁 已修改的文件：

以下文件已更新为从 `.env` 加载 API 密钥：
- `main.py`
- `skills/literature_search/script.py`
- `skills/kg_pathfinder/script.py`
- `skills/enrichment_analysis/script.py`
- `skills/causal_reasoner/script.py`

### 🚀 运行项目：

```bash
python main.py
```

如果 `.env` 文件配置正确，项目将自动加载 API 密钥。

### 🛠️ 故障排除：

如果遇到 `DEEPSEEK_API_KEY not found` 错误：
1. 确认 `.env` 文件存在于项目根目录
2. 确认 `.env` 文件中已设置 `DEEPSEEK_API_KEY=your_key`
3. 确认已安装 `python-dotenv`：`pip install python-dotenv`
