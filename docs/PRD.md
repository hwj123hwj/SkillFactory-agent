------

# 📄 PRD.md (产品需求文档)

**最后更新**: 2026-02-05  
**版本**: v2.0 (已实现 MVP)

## 1. 产品定义

**SkillFactory** 是一个自动化 AI 技能孵化器。它接受一个技术关键词或 URL，通过自主调研、知识蒸馏和代码生成，产出经过验证的"技能胶囊"（Skill 包），直接供 Claude Code 使用。

### 核心特性

- ✅ **自动化文档爬取**：使用 skill-browser-crawl 深度爬取官方文档
- ✅ **智能知识蒸馏**：从海量文档中提取核心概念、API 和最佳实践
- ✅ **代码自动生成**：生成可运行的演示代码和依赖清单
- ✅ **并发任务处理**：支持同时孵化多个技能
- ✅ **多策略研究**：支持 Context7 优先、本地优先、混合策略

## 2. 核心用户痛点

- **API 幻觉**：AI 无法掌握 2025/2026 年最新发布的框架（如 LlamaIndex 新版本）。
- **配置地狱**：官方文档缺失依赖说明或环境配置。
- **资产流失**：开发者反复调试的经验没有被结构化保存。

## 3. 功能需求 (MVP 范围)

### 已实现功能 ✅

- **[F1] 任务并发管理**：✅ 支持主调度器同时派发多个技能孵化任务（基于 asyncio）
  - 可配置并发数（`MAX_CONCURRENT_WORKERS`）
  - 推荐 4C4G 服务器设置为 1（串行执行）
  - 推荐 8C8G+ 服务器设置为 2-3（并行执行）
- **[F2] 多维情报获取**：✅ 集成 skill-browser-crawl 爬取文档，支持 Context7 MCP 查询
- **[F3] 实验员 Agent (Worker)**：✅ 基于 Claude Agent SDK 的智能体，负责逻辑推理与工具调用
- **[F4] Docker 沙盒验证**：✅ 自动在 Docker 容器中运行代码并捕获错误
  - 支持自动重试（最多 3 次）
  - 资源限制（内存、CPU）
  - 超时保护
- **[F5] 知识蒸馏与固化**：✅ 将研究结果总结为 SKILL.md 技能胶囊

### 待实现功能 🚧

- **[F6] 自我修复增强**：⏳ 更智能的错误分析和代码修复（当前已有基础实现）

------

# 🛠️ Technical_Design.md (技术设计文档)

## 1. 架构概览 (Master-Worker 模式)

```
SkillFactory Agent
├── Orchestrator (主调度器)
│   ├── 加载任务队列 (skills_todo.json)
│   ├── 并发管理 (asyncio.gather)
│   └── 结果收集与报告
│
├── Worker Agent (单个技能孵化)
│   ├── Round 1: Research (skill-browser-crawl + Context7)
│   ├── Round 2: Drafting (生成 demo.py + requirements.txt)
│   └── Round 3: Distill (生成 SKILL.md)
│
└── Resource Layer
    ├── skill-browser-crawl (网页爬取 Skill)
    ├── Context7 MCP (文档查询)
    └── Storage (~/.ai_skills/)
```

### 核心组件

- **Orchestrator (src/orchestrator.py)**: 
  - 处理并发逻辑 (`asyncio`)
  - 管理任务队列
  - 错误隔离和超时控制
  
- **Worker Agent (src/worker.py)**: 
  - 基于 Claude Agent SDK
  - 多轮对话管理
  - 工具调用（Skill、Read、Write、Bash）
  
- **Resource Layer**:
  - **skill-browser-crawl**: 深度爬取官方文档（.claude/skills/）
  - **Context7 MCP**: 快速查询文档库
  - **Storage**: 本地 `~/.ai_skills/` 目录

## 2. 核心工作流

### 并发模式说明

**串行模式**（`MAX_CONCURRENT_WORKERS=1`，推荐 4C4G 服务器）：
```
Task 1 → Research → Drafting → Distill → 完成
                                          ↓
Task 2 → Research → Drafting → Distill → 完成
                                          ↓
Task 3 → Research → Drafting → Distill → 完成
```

**并行模式**（`MAX_CONCURRENT_WORKERS=2-3`，推荐 8C8G+ 服务器）：
```
Task 1 → Research → Drafting → Distill → 完成
Task 2 → Research → Drafting → Distill → 完成  (同时进行)
Task 3 → Research → Drafting → Distill → 完成  (同时进行)
```

### 当前实现的工作流 ✅

1. **Input**: 从 `data/skills_todo.json` 加载任务
   ```json
   {
     "name": "skill-llamaindex-custom-llm-entity-extraction",
     "keyword": "LlamaIndex structured entity extraction",
     "research_strategy": "local_first",
     "references": ["https://docs.llamaindex.org.cn/en/stable/"]
   }
   ```

2. **Research**: Worker 调用 skill-browser-crawl 爬取文档
   - 深度爬取官方文档（递归爬取）
   - 保存为 Markdown 格式
   - 可选：使用 Context7 MCP 补充信息

3. **Drafting**: Worker 生成代码
   - 生成 `demo.py`（100-150 行演示代码）
   - 生成 `requirements.txt`（核心依赖）
   - 包含 assert 验证语句

4. **Distilling**: Worker 总结知识
   - 生成 `SKILL.md`（技能文档）
   - 生成 `references/research.md`（研究总结）
   - 保存到 `~/.ai_skills/{skill_name}/`

### 未来工作流 (待实现) 🚧

5. **Testing**: 调用 Docker 沙盒验证
   - 启动 python:3.10-slim 容器
   - pip install dependencies
   - 运行 demo.py
   - 捕获错误日志

6. **Reflecting**: 自我修复循环
   - 若失败：分析错误，修正代码
   - 若成功：进入 Distilling

## 3. 研究策略

### 支持的策略

1. **context7_first** (Context7 优先)
   - 先使用 Context7 MCP 快速查询
   - 若信息不足，补充 skill-browser-crawl

2. **local_first** (本地爬取优先) ✅ 当前测试
   - 使用 skill-browser-crawl 深度爬取
   - 可选：使用 Context7 MCP 补充

3. **hybrid** (混合策略)
   - 并行使用两种方式
   - 综合两个来源的信息

## 4. 关键技术实现

### Worker Agent 配置

```python
ClaudeAgentOptions(
    mcp_servers={
        "context7": {
            "type": "http",
            "url": Config.CONTEXT7_API_URL,
            "headers": {"CONTEXT7_API_KEY": Config.CONTEXT7_API_KEY},
        }
    },
    allowed_tools=[
        "mcp__context7__query-docs",
        "mcp__context7__resolve-library-id",
        "Skill",  # 启用 Skill 工具
        "Read", "Write", "Edit", "Bash"
    ],
    disallowed_tools=[
        "WebSearch", "WebFetch", "webReader"  # 禁止网页工具
    ],
    cwd=str(Config.ROOT_DIR),  # 项目根目录
    setting_sources=["project", "user"],  # 加载 Skills
)
```

### Skill 加载机制

- **项目 Skills**: `.claude/skills/` (版本控制)
- **用户 Skills**: `~/.claude/skills/` (个人技能)
- **自动发现**: 通过 `setting_sources` 配置
- **YAML Frontmatter**: 必须包含 `name` 和 `description`

------

# 🚀 MVP 阶段开发路线图 (Sprint Plan)

| **阶段**                | **状态** | **任务描述**                                                 | **预期产出**                   |
| ----------------------- | -------- | ------------------------------------------------------------ | ------------------------------ |
| **Phase 1: 基础设施**   | ✅ 完成  | 配置管理、数据结构、项目初始化                               | config.py, models.py           |
| **Phase 2: 感官集成**   | ✅ 完成  | 集成 skill-browser-crawl 和 Context7 MCP                     | 文档抓取能力                   |
| **Phase 3: 逻辑注入**   | ✅ 完成  | 使用 Claude Agent SDK 编写 Worker 的多轮对话逻辑             | 能自主看文档并写代码的 Agent   |
| **Phase 4: 并行工厂**   | ✅ 完成  | 加入 `asyncio.gather`，实现同时孵化多个技能                  | 并发管理和错误隔离             |
| **Phase 5: 沙盒验证**   | ✅ 完成  | 编写 Docker 沙盒执行和自我修复循环                           | **SkillFactory MVP 完成** 🎉   |

------

# 📊 当前实现状态

## 已完成的核心功能 ✅

1. **配置管理** (src/config.py)
   - 环境变量支持
   - 多路径配置（ROOT_DIR, SKILLS_DIR, DATA_DIR, LOGS_DIR）
   - Claude SDK 和 Context7 MCP 配置

2. **数据模型** (src/models.py)
   - SkillSpec: 技能任务规范
   - SkillResult: 技能孵化结果
   - 支持多种研究策略

3. **主调度器** (src/orchestrator.py)
   - 并发任务管理（asyncio.gather）
   - 超时控制和错误隔离
   - 结果收集和报告生成

4. **Worker Agent** (src/worker.py)
   - 基于 Claude Agent SDK
   - 多轮对话管理（Research → Drafting → Distill）
   - Skill 工具集成
   - 详细的日志输出

5. **Skill 集成** (.claude/skills/)
   - skill-browser-crawl: 网页爬取 Skill
   - 正确的 YAML frontmatter
   - 自动发现和加载

## 测试验证 ✅

- ✅ Skill 正确加载（从 .claude/skills/）
- ✅ skill-browser-crawl 被成功调用
- ✅ 文档爬取和知识蒸馏工作正常
- ✅ 代码生成（demo.py + requirements.txt）
- ✅ SKILL.md 文档生成
- ✅ 并发任务处理

## 待实现功能 🚧

1. **Docker 沙盒验证**
   - src/utils/docker.py
   - 代码执行和错误捕获
   - 自我修复循环

2. **增强功能**
   - 更智能的知识蒸馏
   - 代码质量检查
   - 自动化测试生成

------

# 🎯 使用示例

## 1. 配置任务

编辑 `data/skills_todo.json`:

```json
{
  "skills": [
    {
      "name": "skill-llamaindex-custom-llm-entity-extraction",
      "keyword": "LlamaIndex structured entity extraction with custom OpenAI-style LLM",
      "description": "Extract structured entities using LlamaIndex with custom model API",
      "research_strategy": "local_first",
      "references": ["https://docs.llamaindex.org.cn/en/stable/"]
    }
  ]
}
```

## 2. 运行孵化器

```bash
uv run python run_agent.py
```

## 3. 查看结果

- **生成的 Skill**: `~/.ai_skills/skill-llamaindex-custom-llm-entity-extraction/`
  - `SKILL.md` - 技能文档
  - `scripts/demo.py` - 演示代码
  - `scripts/requirements.txt` - 依赖清单
  - `references/research.md` - 研究总结

- **执行日志**: `logs/agent.log`
- **结果报告**: `data/results_log.json`

------

# 📝 技术栈

- **Python 3.10+**
- **Claude Agent SDK** - AI Agent 框架
- **Context7 MCP** - 文档查询服务
- **skill-browser-crawl** - 网页爬取 Skill
- **asyncio** - 并发管理
- **uv** - Python 包管理器

------

**文档版本**: v2.0  
**最后更新**: 2026-02-05
