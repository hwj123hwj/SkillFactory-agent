------

# 📄 PRD.md (产品需求文档)

## 1. 产品定义

**SkillFactory** 是一个自动化 AI 技能孵化器。它接受一个技术关键词或 URL，通过自主调研、多维验证和自我修复，产出经过生产环境验证的“技能胶囊”（Markdown 文件），直接供主 Agent（ Claude Code）使用。

## 2. 核心用户痛点

- **API 幻觉**：AI 无法掌握 2025/2026 年最新发布的框架（如 LlamaIndex 新版本）。
- **配置地狱**：官方文档缺失依赖说明或环境配置。
- **资产流失**：开发者反复调试的经验没有被结构化保存。

## 3. 功能需求 (MVP 范围)

- **[F1] 任务并发管理**：支持主调度器同时派发多个技能孵化任务。
- **[F2] 多维情报获取**：集成 Crawl4AI 爬取文档，并具备基础的 GitHub 仓库代码嗅探能力。
- **[F3] 实验员 Agent (Worker)**：基于 Claude SDK 的 ReAct 智能体，负责逻辑推理与工具调用。
- **[F4] Docker 沙盒验证**：自动安装依赖、运行代码并捕获错误日志。
- **[F5] 知识蒸馏与固化**：将验证成功的代码和坑点总结为 `.md` 技能胶囊。

------

# 🛠️ Technical_Design.md (技术设计文档)

## 1. 架构概览 (Master-Worker 模式)

- **Orchestrator (Main Node)**: 处理并发逻辑 (`asyncio`)，管理任务队列。
- **Worker Agent (Claude SDK)**: 核心决策单元，负责“读代码-写代码-改代码”。
- **Resource Layer**:
  - **Crawler**: Crawl4AI 接口。
  - **Sandbox**: Docker SDK 封装，负责隔离运行环境。
  - **Storage**: 本地 `.ai_skills/` 目录。

## 2. 核心工作流 (The Self-Healing Loop)

1. **Input**: `["LlamaIndex Entity Extraction", "FastAPI WebSocket Auth"]`
2. **Research**: Worker 调用 `browser_crawl` 获取原始 Markdown。
3. **Drafting**: Worker 生成 `demo.py` 和 `requirements.txt`。
4. **Testing**: 调用 `docker_run(image, code, libs)`。
5. **Reflecting**:
   - 若失败：Worker 获取 `stderr`，根据报错信息修正代码，返回步骤 3。
   - 若成功：进入步骤 6。
6. **Distilling**: Worker 总结最佳实践，写入 `.ai_skills/`。

## 3. 关键接口定义 (API Design)

### Docker Sandbox Tool

Python

```
def execute_in_sandbox(code: str, dependencies: list) -> dict:
    # 逻辑：
    # 1. 启动 python:3.10-slim 容器
    # 2. pip install dependencies
    # 3. python -c code
    # 4. 返回 { "status": "success/fail", "logs": "..." }
```

### Worker Prompt Template

> "你是一个资深实验员。你的目标是产出可 100% 运行的代码。
>
> 必须确保：
>
> 1. 所有的导入库都在 requirements 中。
> 2. 代码包含 assert 验证逻辑。
> 3. 验证失败时，请分析是版本问题还是逻辑问题，并查阅文档修正。"

------

# 🚀 MVP 阶段开发路线图 (Sprint Plan)

| **阶段**                | **任务描述**                                                 | **预期产出**                   |
| ----------------------- | ------------------------------------------------------------ | ------------------------------ |
| **Phase 1: 实验室建设** | 编写 `docker_executor.py`，确保能通过 Python 脚本在容器内跑通简单的 `pip install`。 | 可工作的 Docker SDK 封装。     |
| **Phase 2: 感官集成**   | 接入 Crawl4AI 的 API，实现“技术名 -> Markdown 文档”的转换。  | 文档抓取模块。                 |
| **Phase 3: 逻辑注入**   | 使用 Claude SDK 编写 Worker 的循环逻辑（ReAct Loop）。       | 能自主看文档并写代码的 Agent。 |
| **Phase 4: 并行工厂**   | 加入 `asyncio.gather`，实现同时孵化 3 个技能。               | **SkillFactory 1.0 完成。**    |

