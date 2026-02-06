# 🚀 SkillFactory Agent - 快速开始指南

## 5 分钟快速上手

### 步骤 1：安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 步骤 2：配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
# Windows: notepad .env
# Linux/Mac: nano .env
```

**必需配置**：
```bash
# Claude API Key（必需）
CLAUDE_API_KEY=sk-ant-xxxxx

# 并发配置（4C4G 服务器推荐）
MAX_CONCURRENT_WORKERS=1
WORKER_TIMEOUT=900
```

**可选配置**：
```bash
# Context7 MCP（可选，用于快速查询文档）
CONTEXT7_API_KEY=your-context7-key

# Docker 配置（可选，默认值已优化）
DOCKER_IMAGE=python:3.10-slim
DOCKER_MEMORY_LIMIT=800m
DOCKER_CPU_LIMIT=1.0
```

### 步骤 3：测试 Docker（可选但推荐）

```bash
# 测试 Docker 是否可用
python test_docker.py
```

**预期输出**：
```
Docker available: True
Test passed: 2 + 2 = 4
```

**如果 Docker 不可用**：
- 安装 Docker：https://docs.docker.com/get-docker/
- 启动 Docker 服务：`sudo systemctl start docker`
- 或跳过此步骤（代码验证将被跳过）

### 步骤 4：配置第一个技能任务

编辑 `data/skills_todo.json`：

```json
{
  "skills": [
    {
      "name": "skill-test-simple",
      "keyword": "Python requests library basic usage",
      "description": "Learn how to use Python requests library for HTTP requests",
      "research_strategy": "context7_first",
      "references": ["https://requests.readthedocs.io/"]
    }
  ]
}
```

**字段说明**：
- `name`: 技能名称（唯一标识符）
- `keyword`: 研究关键词（用于搜索文档）
- `description`: 技能描述
- `research_strategy`: 研究策略
  - `context7_first`: Context7 优先（快速，推荐）
  - `local_first`: 本地爬取优先（详尽）
  - `hybrid`: 混合模式（最全面）
- `references`: 参考文档 URL（可选）

### 步骤 5：运行孵化器

```bash
# 使用 uv
uv run python run_agent.py

# 或直接运行
python run_agent.py
```

**预期输出**：
```
2026-02-05 10:00:00 | INFO | SkillFactory Agent starting...
2026-02-05 10:00:01 | INFO | 待执行技能数量: 1
2026-02-05 10:00:02 | INFO | Worker start: skill-test-simple
2026-02-05 10:00:05 | INFO | Round start (skill-test-simple): Research
2026-02-05 10:02:30 | INFO | Round end (skill-test-simple)
2026-02-05 10:02:31 | INFO | Round start (skill-test-simple): Drafting
2026-02-05 10:05:00 | INFO | Round end (skill-test-simple)
2026-02-05 10:05:01 | INFO | Test attempt 1/3
2026-02-05 10:06:00 | INFO | Code validation successful!
2026-02-05 10:06:01 | INFO | Round start (skill-test-simple): Distill
2026-02-05 10:08:00 | INFO | Round end (skill-test-simple)
2026-02-05 10:08:01 | INFO | Worker end: skill-test-simple (success)
2026-02-05 10:08:02 | INFO | Summary: success=1 | partial=0 | failed=0 | timeout=0
```

### 步骤 6：查看结果

生成的技能保存在 `~/.ai_skills/` 目录：

```bash
# 查看生成的技能
ls ~/.ai_skills/skill-test-simple/

# 输出：
# SKILL.md                    # 技能文档
# scripts/
#   ├── demo.py               # 演示代码
#   └── requirements.txt      # 依赖清单
# references/
#   └── research.md           # 研究总结（可选）
```

**查看技能文档**：
```bash
cat ~/.ai_skills/skill-test-simple/SKILL.md
```

**运行演示代码**：
```bash
cd ~/.ai_skills/skill-test-simple/scripts/
pip install -r requirements.txt
python demo.py
```

---

## 🎯 下一步

### 1. 批量孵化多个技能

编辑 `data/skills_todo.json`，添加多个技能：

```json
{
  "skills": [
    {
      "name": "skill-fastapi-websocket",
      "keyword": "FastAPI WebSocket authentication",
      "description": "Secure WebSocket connections in FastAPI",
      "research_strategy": "local_first",
      "references": ["https://fastapi.tiangolo.com/"]
    },
    {
      "name": "skill-pydantic-validation",
      "keyword": "Pydantic data validation",
      "description": "Data validation using Pydantic",
      "research_strategy": "context7_first",
      "references": []
    }
  ]
}
```

**注意**：
- 4C4G 服务器建议 `MAX_CONCURRENT_WORKERS=1`（串行执行）
- 8C8G+ 服务器可以设置 `MAX_CONCURRENT_WORKERS=2-3`（并行执行）

### 2. 使用生成的技能

生成的技能可以直接在 Claude Code 中使用：

```bash
# 复制到 Claude Code 的 Skills 目录
cp -r ~/.ai_skills/skill-test-simple ~/.claude/skills/

# 或创建符号链接
ln -s ~/.ai_skills/skill-test-simple ~/.claude/skills/
```

### 3. 查看日志和结果

```bash
# 查看执行日志
tail -f logs/agent.log

# 查看结果报告
cat data/results_log.json
```

---

## 🐛 常见问题

### Q1: Docker 不可用怎么办？

**A**: 代码验证会被跳过，但其他功能正常工作。建议安装 Docker 以获得完整功能。

### Q2: 内存不足（OOM）怎么办？

**A**: 降低并发数：
```bash
# .env 文件
MAX_CONCURRENT_WORKERS=1
```

### Q3: Context7 API Key 在哪里获取？

**A**: 访问 https://context7.com/ 注册并获取 API Key。如果没有，可以使用 `local_first` 策略。

### Q4: 技能孵化失败怎么办？

**A**: 查看日志：
```bash
tail -100 logs/agent.log
```

常见原因：
- API Key 无效
- 网络连接问题
- Docker 不可用
- 依赖安装失败

### Q5: 如何调试？

**A**: 启用 DEBUG 日志：
```bash
# .env 文件
LOG_LEVEL=DEBUG
```

---

## 📚 更多文档

- [README.md](../README.md) - 完整文档和配置说明
- [PRD.md](PRD.md) - 产品需求和实现状态
- [Agent SDK 参考 - Python.md](Agent%20SDK%20参考%20-%20Python.md) - Claude Agent SDK 参考
- [DOCS.md](DOCS.md) - 完整文档索引

---

**祝你使用愉快！** 🎉

如有问题，请查看日志或提交 Issue。
