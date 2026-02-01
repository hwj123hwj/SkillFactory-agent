# 🎯 SkillFactory Agent - 实现设计文档 (v2.0)

**时间**：2026-02-01  
**版本**：v2.0（修正架构理解）  
**目标**：基于 Claude Agent SDK + Skill + Context7 MCP，自动孵化可运行的技能(Skills)

---

## 1. 架构全景图

```
┌─────────────────────────────────────────────────────────────┐
│                    SkillFactory Agent                        │
│          (独立Docker容器内运行，无需中断)                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Main Orchestrator (concurrent)               │   │
│  │  - 读取 skills_todo.json (技能孵化任务清单)          │   │
│  │  - 并发执行 Worker Agent (最多3个并行)               │   │
│  │  - asyncio.Semaphore 限流 + 超时控制                │   │
│  │  - 收集结果，生成报告                                │   │
│  └─────────────────────────────────────────────────────┘   │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │      Worker Agent (ClaudeSDKClient)                 │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────┐    │   │
│  │  │   Round 1: Research                        │    │   │
│  │  │  - 可选 skill-browser-crawl 爬取文档       │    │   │
│  │  │  - 优先：Context7 MCP 查询外部文档        │    │   │
│  │  │  - 在本地建立文档库                        │    │   │
│  │  └────────────────────────────────────────────┘    │   │
│  │           ↓                                         │   │
│  │  ┌────────────────────────────────────────────┐    │   │
│  │  │   Round 2: Drafting                        │    │   │
│  │  │  - 基于本地文档，生成 demo.py + requirements│   │   │
│  │  │  - 使用 Claude Code Write 工具             │    │   │
│  │  └────────────────────────────────────────────┘    │   │
│  │           ↓                                         │   │
│  │  ┌────────────────────────────────────────────┐    │   │
│  │  │   Round 3-N: Test & Fix Loop               │    │   │
│  │  │  - docker run python:3.10-slim demo.py    │    │   │
│  │  │  - 若失败：分析错误，修复代码，重试        │    │   │
│  │  │  - 最多重试 3 次，后续手动审查              │    │   │
│  │  └────────────────────────────────────────────┘    │   │
│  │           ↓                                         │   │
│  │  ┌────────────────────────────────────────────┐    │   │
│  │  │   Round N+1: Distill & Package             │    │   │
│  │  │  - 生成 SKILL.md + scripts/ + references/  │    │   │
│  │  │  - 调用 skill-creator 打包为 .skill       │    │   │
│  │  └────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │      外部资源接口                                    │   │
│  │  ┌──────────────────┐  ┌──────────────────────┐    │   │
│  │  │ skill-browser-  │  │  Context 7 MCP      │    │   │
│  │  │ crawl           │  │  (query-docs,       │    │   │
│  │  │ (独立Skill)     │  │   resolve-library)  │    │   │
│  │  └──────────────────┘  └──────────────────────┘    │   │
│  │                                                     │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │  Claude Code 原生工具                        │  │   │
│  │  │  (Read, Write, Edit, Bash, ...)             │  │   │
│  │  └──────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │      存储与输出                                      │   │
│  │  ~/.ai_skills/                                     │   │
│  │  ├── docs/  (爬取的文档)                            │   │
│  │  ├── skill-001-llamaindex-extraction/              │   │
│  │  ├── skill-001-llamaindex-extraction.skill         │   │
│  │  ...                                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心设计原则

### 2.1 **无中断自驱动 (No Interruption, Always Self-Driving)**

Agent 一旦启动，就持续跑完全部任务队列，不依赖外部确认

```python
import asyncio
from .config import Config

class SkillFactoryOrchestrator:
    def __init__(self, max_concurrent: Optional[int] = None):
        # 优先使用传入参数，否则从 Config 读取
        self.max_concurrent = max_concurrent or Config.MAX_CONCURRENT_WORKERS
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

    async def run(self):
        todos = load_skills_todo()

        # 并发执行所有任务（带限流和超时控制）
        tasks = [
            self.spawn_worker_with_timeout(skill, timeout=Config.WORKER_TIMEOUT)
            for skill in todos
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果（一个失败不影响其他）
        for skill_spec, result in zip(todos, results):
            if isinstance(result, Exception):
                self.log_error(skill_spec, result)
            else:
                self.save_result(result)

        self.generate_summary_report()

    async def spawn_worker_with_timeout(self, skill_spec: SkillSpec, timeout: int):
        """启动单个 Worker（带并发控制和超时）"""
        async with self.semaphore:  # 限制并发数
            try:
                return await asyncio.wait_for(
                    self._run_worker(skill_spec),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                return SkillResult(skill_spec.name, "timeout")
            except Exception as e:
                return SkillResult(skill_spec.name, "error", str(e))
```

### 2.2 **独立 Skill：skill-browser-crawl**

这是一个 **Claude Skill**（你自己需要编写），不是 MCP 工具。它的功能：

- **输入**：技术关键词、URL 列表
- **处理**：使用 Crawl4AI 爬取官方文档
- **输出**：Markdown 格式的文档保存到本地 `~/.ai_skills/docs/`

示例目录结构：
```
.agents/skills/skill-browser-crawl/
├── SKILL.md                    # Skill 定义
├── scripts/
│   ├── crawl.py               # Crawl4AI 脚本
│   └── requirements.txt
├── references/
│   └── crawl4ai_guide.md
└── assets/
    └── crawl_config.json
```

Worker Agent 会调用这个 Skill：
```
"基于关键词 LlamaIndex v0.10，使用 skill-browser-crawl 爬取官方文档"
→ Claude 调用该 Skill
→ 文档保存到本地
→ Claude 后续基于本地文档选取相关片段
```

### 2.3 **MCP 工具：Context 7（由用户配置）**

已在 VSCode mcp.json 中配置，提供两个工具：
- `query-docs`: 查询官方文档库
- `resolve-library-id`: 解析库的标准 ID

**调研策略**（可配置，见 skills_todo.json）：
- **Context 7 优先**（推荐）：先调用 Context 7 query-docs，若上下文充分（≥20k tokens）则直接进入 Drafting，无需本地爬取
- **本地爬取优先**：使用 skill-browser-crawl 获取官方文档，进行知识蒸馏，可选补充 Context 7
- **混合模式**：同时触发 Context 7 + skill-browser-crawl，综合两份信息

Worker Agent 根据 `research_strategy` 字段动态调整执行流程。

### 2.4 **Skill 是最终产出，必须符合 Claude Skill 规范**

参考 `.agents/skills/skill-creator/SKILL.md`：

- **SKILL.md**: YAML frontmatter (name, description) + Markdown body
- **scripts/**: 可复用的代码脚本
- **references/**: 文档参考资料
- **assets/**: 模板、图片等非代码资源

---

## 3. Worker Agent 的自愈循环 (Self-Healing Loop)

### 阶段 1：研究 + 知识蒸馏 (Research & Distillation)

**策略选择**（基于 skills_todo.json 中的 `research_strategy` 字段）：

#### 策略 A：Context 7 优先（推荐，成本最低）

```
Worker Prompt (第1轮):
  "获取关键词 'LlamaIndex v0.10 Entity Extraction' 的最新文档。
   
   步骤 1：使用 Context 7 MCP（优先）
   - 调用 query-docs(keyword='{keyword}')
   - 调用 resolve-library-id(keyword='{keyword}')
   
   步骤 2：知识蒸馏（关键！）
   若获得的上下文 >= 20000 tokens，则执行蒸馏：
   - 识别核心概念（3-5个，简洁定义）
   - 筛选 API/函数/类（10-20 个关键项）
   - 提取使用示例（3-5 个代表性例子）
   - 列出常见错误和最佳实践
   - 【舍弃】与关键词无关的章节、过时内容、冗长理论
   - 最终控制在 5000-10000 token 以内
   
   步骤 3：若上下文不足 (< 20000 tokens)
   - 回源：使用 skill-browser-crawl 爬取官方文档补充
   - 重复蒸馏流程"

Action:
  - Claude 调用 mcp__context7__query-docs(...)
  - 评估返回的文档大小
  - [若充分] 进行知识蒸馏 → Drafting
  - [若不足] 调用 skill-browser-crawl → 蒸馏 → Drafting
```

#### 策略 B：本地爬取优先（更详尽，成本更高）

```
Worker Prompt (第1轮):
  "获取关键词 'LlamaIndex v0.10 Entity Extraction' 的详细文档。
   
   步骤 1：本地爬取
   - 使用 skill-browser-crawl 爬取官方文档、GitHub repo
   
   步骤 2：知识蒸馏（同策略 A）
   - 识别核心概念、筛选 API、提取示例
   - 最终控制在 5000-10000 token 以内
   
   步骤 3：可选补充
   - 使用 Context 7 MCP query-docs 补充外部信息"

Action:
  - 调用 skill-browser-crawl
  - 本地蒸馏文档
  - [可选] 补充 Context 7 信息
```

#### 策略 C：混合模式（最全面）

```
Worker Prompt (第1轮):
  "并行获取两个来源的文档，进行综合蒸馏。
   
   步骤 1a：Context 7 MCP（并行）
   - query-docs(keyword='{keyword}')
   
   步骤 1b：本地爬取（并行）
   - 使用 skill-browser-crawl 爬取官方文档
   
   步骤 2：综合知识蒸馏
   - 合并两个来源，去重
   - 识别核心概念、筛选 API、提取示例
   - 最终控制在 8000-15000 token 以内（允许更多内容）"

Action:
  - 并行调用 Context 7 + skill-browser-crawl
  - 综合蒸馏两份文档
```

### 阶段 2：草稿 (Drafting)

```
Worker Prompt (第2轮，Claude 记住研究结果):
  "基于刚才整理的文档，生成一个可运行的 demo.py。
   
   要求：
   - 所有依赖列在 requirements.txt 中
   - 代码包含 assert 验证逻辑
   - 演示核心概念"

Action:
  - Claude 用 Write 工具创建 ~/.ai_skills/{skill_name}/scripts/demo.py
  - Claude 用 Write 工具创建 ~/.ai_skills/{skill_name}/scripts/requirements.txt
```

### 阶段 3-N：测试与修复 (Test & Fix Loop)

```
Worker Prompt (第3轮):
  "执行 demo.py，确保能在干净的环境中运行。
   使用 Bash 工具执行: docker run --rm -v ~/.ai_skills/{skill_name}/scripts:/app python:3.10-slim bash -c '...'"

Action:
  - Claude 用 Bash 工具调用 docker run
  - 返回 {exit_code, stdout, stderr}

Outcome:
  ✅ 成功 → 进入阶段 N+1: Distill
  ❌ 失败 → 阶段 3.1: Analyze

阶段 3.1：失败分析与修复
Worker Prompt:
  "代码执行失败，报错如下：
   [stderr 内容]
   
   分析错误原因（版本问题/逻辑错误/依赖缺失），修复代码。
   重新提交 Bash docker run。"

Action:
  - Claude 分析错误
  - 用 Edit 工具修改 demo.py / requirements.txt
  - 再次用 Bash 执行 docker run
  
重试策略:
  - 最多重试 3 次
  - 第 4 次失败 → 记录为"待人工审查"
  - 不返回，继续下一个技能
```

### 阶段 N+1：蒸馏与打包 (Distill & Package)

```
Worker Prompt (最后一轮):
  "代码已验证可运行。现在总结一个完整的 Skill，包括：
   
   1. SKILL.md (按照 skill-creator 规范)
   2. scripts/demo.py
   3. scripts/requirements.txt
   4. references/api_docs.md (可选)
   5. assets/ (可选)
   
   使用 Write 工具创建这些文件。
   完成后，使用 Bash 调用 package_skill.py 打包。"

Action:
  - Claude 用 Write 工具创建 SKILL.md
  - Claude 用 Write 工具创建其他参考文件（可选）
  - Claude 用 Bash 执行: python ~/.agents/skills/skill-creator/scripts/package_skill.py ~/.ai_skills/{skill_name}
  - 生成 ~/.ai_skills/{skill_name}.skill 文件
```

---

## 4. 系统组件定义

### 4.1 Orchestrator (orchestrator.py)

```python
import asyncio
from typing import List, Optional
from .config import Config

class SkillFactoryOrchestrator:
    """
    主调度器，支持并发执行技能孵化任务
    """

    def __init__(self, max_concurrent: Optional[int] = None):
        # 优先使用传入参数，否则从 Config 读取
        self.max_concurrent = max_concurrent or Config.MAX_CONCURRENT_WORKERS
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.results: List[SkillResult] = []

    async def run(self):
        """
        主循环：
        1. load_skills_todo() → List[SkillSpec]
        2. 并发执行所有 Worker（带限流和超时）
        3. generate_summary()
        """
        todos = load_skills_todo()

        # 创建所有任务
        tasks = [
            self.spawn_worker_with_timeout(skill, timeout=Config.WORKER_TIMEOUT)
            for skill in todos
        ]

        # 并发执行（一个失败不影响其他）
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for skill_spec, result in zip(todos, results):
            if isinstance(result, Exception):
                self.log_error(skill_spec, result)
            elif isinstance(result, SkillResult):
                self.save_result(result)

        self.generate_summary_report()

    async def spawn_worker_with_timeout(self, skill_spec: SkillSpec, timeout: int):
        """
        启动单个 Worker（带并发控制和超时）
        """
        async with self.semaphore:  # 限制并发数
            try:
                return await asyncio.wait_for(
                    self._run_single_worker(skill_spec),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                return SkillResult(skill_spec.name, "timeout", f"超过 {timeout} 秒")
            except Exception as e:
                return SkillResult(skill_spec.name, "error", str(e))

    async def _run_single_worker(self, skill_spec: SkillSpec) -> SkillResult:
        """运行单个 Worker"""
        worker = SkillFactoryWorker(skill_spec)
        return await worker.run()

    def save_result(self, result: SkillResult):
        """保存技能到 ~/.ai_skills/"""
        self.results.append(result)
```

### 4.2 Worker Agent (worker.py)

```python
class SkillFactoryWorker:
    """
    基于 ClaudeSDKClient 的单个技能孵化 Agent
    
    特点：
    - 多轮对话（ClaudeSDKClient 维持会话）
    - 调用 skill-browser-crawl 爬取文档（作为一个 Claude Skill）
    - 调用 Context7 MCP 获取外部文档信息（可选）
    - 使用 Claude Code 的 Write/Edit/Bash 工具
    - 自动修复失败（重试 3 次）
    - 最终生成 Skill
    """
    
    def __init__(self, skill_spec: SkillSpec):
        self.skill_spec = skill_spec

        # 构建环境变量（支持自定义 API）
        env_vars = {}
        if Config.ANTHROPIC_BASE_URL:
            env_vars["ANTHROPIC_BASE_URL"] = Config.ANTHROPIC_BASE_URL
        if Config.ANTHROPIC_AUTH_TOKEN:
            env_vars["ANTHROPIC_AUTH_TOKEN"] = Config.ANTHROPIC_AUTH_TOKEN

        self.client_options = ClaudeAgentOptions(
            # Context 7 MCP 配置（由用户提供的 mcp.json）
            mcp_servers={
                "context7": {
                    "type": "http",
                    "url": Config.CONTEXT7_API_URL,
                    "headers": {
                        "CONTEXT7_API_KEY": Config.CONTEXT7_API_KEY
                    },
                    "tools": ["query-docs", "resolve-library-id"]
                }
            },
            allowed_tools=[
                # Context 7 MCP 工具
                "mcp__context7__query-docs",
                "mcp__context7__resolve-library-id",
                # Claude Code 工具
                "Read",
                "Write",
                "Edit",
                "Bash",
                # skill-browser-crawl（作为一个可调用的 Skill）
                # 注：Claude Code 本身支持调用 Skill
            ],
            permission_mode=Config.PERMISSION_MODE,
            model=Config.CLAUDE_MODEL,
            env=env_vars,  # 传递自定义 API 配置
            cwd=str(Config.SKILLS_DIR)
        )
    
    async def run(self) -> SkillResult:
        """
        执行完整的自愈循环
        """
        async with ClaudeSDKClient(options=self.client_options) as client:
            # Round 1: Research
            await client.query(self._prompt_research())
            async for msg in client.receive_response():
                pass  # Claude 调用 skill-browser-crawl + Context7 MCP
            
            # Round 2: Drafting
            await client.query(self._prompt_drafting())
            async for msg in client.receive_response():
                pass  # Claude 用 Write 创建文件
            
            # Round 3+: Test & Fix
            for attempt in range(1, 4):
                await client.query(self._prompt_test(attempt))
                async for msg in client.receive_response():
                    pass  # Claude 用 Bash 调用 docker run
                
                if self._is_success():
                    break
            
            # Round N+1: Distill & Package
            await client.query(self._prompt_distill())
            async for msg in client.receive_response():
                pass  # Claude 用 Write 创建 SKILL.md，用 Bash 调用 package_skill.py
        
        return SkillResult(...)
```

### 4.3 Skill 与 MCP 的调用方式

**skill-browser-crawl**（一个独立的 Skill）
```
Worker Prompt:
  "使用 skill-browser-crawl 爬取关键词 'LlamaIndex v0.10' 的官方文档"
  
Claude 执行：
  → Claude Code 原生支持调用其他 Skill
  → 文档保存到 ~/.ai_skills/docs/
  → Claude 可以 Read 这些文件
```

**Context 7 MCP**（配置的外部工具）
```
Worker Prompt:
  "可选地，使用 query-docs 查询 LlamaIndex 的官方文档库"
  
Claude 执行：
  → 调用 mcp__context7__query-docs(...)
  → 获取外部数据
  → 结合本地爬取的文档
```

---

## 5. 数据结构定义

### 5.1 SkillSpec (输入)

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SkillSpec:
    """
    技能孵化任务规范
    """
    name: str  # "skill-001-llamaindex-extraction"
    keyword: str  # "LlamaIndex v0.10 Entity Extraction"
    description: str  # "Learn Entity Extraction with LlamaIndex"
    
    # 调研策略配置
    research_strategy: str = "context7_first"  # "context7_first" | "local_first" | "hybrid"
    min_context_tokens: int = 20000  # 触发本地爬取的最小上下文 token 数
    max_distilled_tokens: int = 10000  # 蒸馏后文档的最大 token 数
    
    # 可选字段
    references: Optional[list] = field(default_factory=list)  # 显式指定的 URL
    skip_distillation: bool = False  # 跳过知识蒸馏（用于调试）
```

### 5.2 SkillResult (输出)

```python
@dataclass
class SkillResult:
    """
    技能孵化结果
    """
    skill_name: str
    status: str  # "success" | "partial_success" | "failed"
    skill_dir: str  # ~/.ai_skills/skill-001-...
    skill_file: str  # ~/.ai_skills/skill-001-....skill
    demo_code: str  # 验证通过的代码
    error_log: str  # 若失败，记录错误
    created_at: str  # ISO 时间戳
```

### 5.3 skills_todo.json (任务清单，含调研策略)

```json
{
  "skills": [
    {
      "name": "skill-001-llamaindex-extraction",
      "keyword": "LlamaIndex v0.10 Entity Extraction",
      "description": "Learn Entity Extraction with LlamaIndex",
      
      "research_strategy": "context7_first",
      "min_context_tokens": 20000,
      "max_distilled_tokens": 10000,
      
      "references": [
        "https://docs.llamaindex.ai/en/stable/modules/querying/retriever/",
        "https://github.com/run-llama/llama_index/tree/main/llama-index-core/llama_index/extractors"
      ]
    },
    {
      "name": "skill-002-fastapi-websocket",
      "keyword": "FastAPI WebSocket Authentication",
      "description": "Secure WebSocket connections in FastAPI",
      
      "research_strategy": "hybrid",
      "min_context_tokens": 15000,
      "max_distilled_tokens": 15000,
      
      "references": []
    }
  ]
}
```

---

## 6. 执行流程 (时序)

```
启动 Agent
  ↓
load_skills_todo.json
  ↓
【并发启动】使用 asyncio.gather 启动所有 Worker（最多3个并行）
  │
  ├─ Worker 1: skill-001-llamaindex ━━━━━━━━━━━━━━━━━━━━━━┐
  ├─ Worker 2: skill-002-fastapi   ━━━━━━━━━━━━━━━━━━━━━━┤
  └─ Worker 3: skill-003-pydantic  ━━━━━━━━━━━━━━━━━━━━━━┤ (并行执行)
                                                        │
每个 Worker 内部流程:                                   │
  │                                                      │
  ├─ 初始化 ClaudeSDKClient                              │
  │                                                      │
  ├─ Round 1 (Research):                                │
  │   Claude → Context7 MCP query-docs（优先）            │
  │   [若不足] → skill-browser-crawl 补充                │
  │                                                      │
  ├─ Round 2 (Drafting):                                │
  │   Claude → Write 工具创建 demo.py + requirements.txt │
  │                                                      │
  ├─ Round 3 (Test):                                    │
  │   Claude → Bash: timeout 300 docker run ...          │
  │   ├─ ✅ Exit 0 → Round N+1                          │
  │   └─ ❌ Exit != 0 → Round 3.1                       │
  │                                                      │
  ├─ Round 3.1+ (Fix Loop, 最多3次):                    │
  │   Claude → 分析错误 → Edit 工具修改                  │
  │   Claude → Bash: timeout 300 docker run ...          │
  │   ├─ ✅ 成功 → Round N+1                            │
  │   └─ ❌ 第3次失败 → 返回错误结果                    │
  │                                                      │
  ├─ Round N+1 (Distill):                               │
  │   Claude → Write 工具创建 SKILL.md                   │
  │                                                      │
  └─ Round N+2 (Package):                               │
      Claude → Bash: 调用 package_skill.py              │
      生成 skill-name.skill 文件                         │
                                                       │
【并发收集】所有 Worker 完成 ━━━━━━━━━━━━━━━━━━━━━┛
  ↓
save_result(all_results)
  - 记录到 results_log.json
  ↓
generate_summary_report()
  ✅ 成功: N | ❌ 失败: N | ⏰ 超时: N
```

**关键并发特性**：
- `asyncio.Semaphore(3)`：限制最多 3 个 Worker 并行
- `asyncio.wait_for(worker, timeout=600)`：每个 Worker 最多 10 分钟
- `return_exceptions=True`：一个失败不影响其他

---

## 7. 关键的 Worker Prompt 模板

### Prompt 1: Research（含知识蒸馏）

**Prompt 1-A：Context 7 优先模式（推荐）**

```
你是一个资深技术研究员。你的任务是高效地获取技术信息，并进行知识蒸馏。

技能名称: {skill_name}
研究关键词: {keyword}
描述: {description}

执行流程：

【第一步】调用 Context 7 MCP 获取官方文档
1. 使用 mcp__context7__query-docs(keyword="{keyword}")
2. 使用 mcp__context7__resolve-library-id(keyword="{keyword}")
3. 评估返回的上下文大小（token 数）

【第二步】知识蒸馏（关键！）
若上下文 >= {min_context_tokens} tokens，执行以下蒸馏：
  a) 识别 3-5 个核心概念（简洁定义，每个 1-2 句话）
  b) 筛选 10-20 个关键 API/函数/类（列表形式）
  c) 提取 3-5 个代表性使用示例（可直接运行的代码片段）
  d) 列出 3-5 个常见错误和最佳实践
  
  【重要】舍弃以下内容：
  - 与 "{keyword}" 无直接关系的章节
  - 已过时的版本信息
  - 冗长的理论介绍（保留 1 段总结即可）
  
  最终蒸馏文档应控制在 {max_distilled_tokens} tokens 以内。

【第三步】若上下文不足，补充本地爬取
若 Context 7 返回 < {min_context_tokens} tokens，则：
  1. 使用 skill-browser-crawl 爬取官方文档
  2. 重复第二步的知识蒸馏流程

【最终输出】
整理成结构化的蒸馏笔记，包含：
- 版本信息和更新日期
- 核心概念（蒸馏后）
- 关键 API 列表
- 基本使用示例代码
- 常见错误和最佳实践
```

**Prompt 1-B：本地爬取优先模式**

```
你是一个资深技术研究员。你的任务是深入研究技术主题，并进行知识蒸馏。

技能名称: {skill_name}
研究关键词: {keyword}
描述: {description}

执行流程：

【第一步】本地爬取官方文档
1. 使用 skill-browser-crawl 爬取：
   - 官方文档（HTML → Markdown）
   - GitHub 仓库信息
   - PyPI 包信息（如适用）
2. 文档保存到本地 ~/.ai_skills/docs/

【第二步】知识蒸馏
执行以下蒸馏（同 Prompt 1-A 的第二步）：
  a) 识别 3-5 个核心概念
  b) 筛选 10-20 个关键 API/函数/类
  c) 提取 3-5 个使用示例
  d) 列出 3-5 个常见错误和最佳实践
  最终控制在 {max_distilled_tokens} tokens 以内

【第三步】可选补充
使用 Context 7 MCP 补充外部文档库的最新信息（如有）。

【最终输出】
结构化的蒸馏笔记（同 Prompt 1-A）
```

**Prompt 1-C：混合模式**

```
你是一个资深技术研究员。你将并行获取多个信息源，并进行综合知识蒸馏。

【第一步】并行获取文档（两个来源同时进行）
来源 A：Context 7 MCP
  - mcp__context7__query-docs(keyword="{keyword}")
  - mcp__context7__resolve-library-id(keyword="{keyword}")

来源 B：本地爬取
  - 使用 skill-browser-crawl 爬取官方文档

【第二步】综合知识蒸馏
1. 合并两个来源的信息，去重
2. 识别 3-5 个核心概念
3. 筛选 15-25 个关键 API（允许更多内容）
4. 提取 5-10 个使用示例
5. 列出 5-10 个最佳实践和常见陷阱

最终蒸馏文档应控制在 {max_distilled_tokens} tokens 以内。

【最终输出】
综合的蒸馏笔记，融合两个信息源的优势
```

### Prompt 2: Drafting

```
你现在有了完整的文档背景。基于刚才整理的文档，生成一个可运行的演示代码。

要求：
1. 使用 Write 工具创建 ~/.ai_skills/{skill_name}/scripts/demo.py
   - 代码必须可以直接运行（无交互式输入）
   - 包含 assert 语句验证功能是否正确
   - 清晰的代码注释
   - 演示 {keyword} 的核心功能

2. 使用 Write 工具创建 ~/.ai_skills/{skill_name}/scripts/requirements.txt
   - 列出所有依赖包及具体版本号
   - 使用 == 而不是 * 或 ~
```

### Prompt 3: Test (Attempt N)

```
现在测试代码的可运行性。这是第 {attempt}/3 次尝试。

你需要：
1. 使用 Bash 工具执行以下命令（带 5 分钟超时保护）：

   timeout 300 docker run --rm -v ~/.ai_skills/{skill_name}/scripts:/app python:3.10-slim bash -c "
   cd /app && \
   pip install -q -r requirements.txt && \
   python demo.py
   "

   注意：timeout 300 确保 docker 命令最多运行 5 分钟，防止代码死循环

2. 检查返回的输出：
   - 若包含 "AssertionError": 说明逻辑错误，需要修复
   - 若包含 "ModuleNotFoundError": 说明依赖缺失或版本不对，需要修复
   - 若包含 "Timeout": 说明代码执行超时，需要优化或检查逻辑
   - 若包含其他错误: 根据具体情况修复

3. 若失败，分析原因：
   - 使用 Edit 工具修改 demo.py 或 requirements.txt
   - 重新执行 docker run 命令
   - 最多重试 3 次

   第 4 次失败则停止，记录为"待人工审查"

4. 若成功（返回 0，无异常），进入下一轮
```

### Prompt 4: Distill

```
代码已验证可运行！现在为这个技能编写完整的文档并打包。

你需要：

1. 使用 Write 工具创建 ~/.ai_skills/{skill_name}/SKILL.md
   
   格式参考 (来自 .agents/skills/skill-creator/SKILL.md):
   ---
   name: {skill_name}
   description: {description}. Use this skill when you need to {action_description}.
   ---

   # {Skill Title}

   ## Overview
   [核心概念，2-3 段]

   ## Prerequisites
   [依赖说明，包括 Python 版本、系统库]

   ## Quick Start
   [基本使用示例]

   ## API Reference
   [主要函数/类的说明]

   ## Best Practices
   [最佳实践和注意事项]

   ## Troubleshooting
   [常见错误和解决方案]

2. 若需要，使用 Write 工具创建其他文件：
   - ~/.ai_skills/{skill_name}/references/api_docs.md
   - ~/.ai_skills/{skill_name}/assets/example.json 等

3. 完成后，使用 Bash 工具执行打包命令：
   
   python ~/.agents/skills/skill-creator/scripts/package_skill.py ~/.ai_skills/{skill_name}
   
   这会生成 ~/.ai_skills/{skill_name}.skill 文件
```

---

## 8. 文件结构

```
SkillFactory_agent/
├── IMPLEMENTATION_DESIGN_v2.md (本文档)
├── PRD.md (原需求文档)
├── IMPLEMENTATION_DESIGN.md (v1.0，已弃用)
│
├── src/
│   ├── orchestrator.py        # 主调度器
│   ├── worker.py              # Worker Agent
│   ├── models.py              # 数据结构
│   └── config.py              # 配置管理
│
├── data/
│   ├── skills_todo.json       # 任务清单
│   └── results_log.json       # 执行结果日志
│
├── .ai_skills/                # 生成的技能存储
│   ├── docs/                  # 爬取的文档
│   ├── skill-001-xxx/
│   ├── skill-001-xxx.skill
│   ├── skill-002-yyy/
│   ├── skill-002-yyy.skill
│   ...
│
├── logs/
│   └── agent.log
│
└── requirements.txt
    - claude-agent-sdk
    - crawl4ai
    - python-dotenv
```

---

## 9. 配置管理 (config.py)

```python
from pathlib import Path
import os
from typing import Optional

class Config:
    """配置管理 - 支持环境变量覆盖"""

    # ===== 并发配置 =====
    MAX_CONCURRENT_WORKERS = int(os.getenv("MAX_CONCURRENT_WORKERS", "3"))
    WORKER_TIMEOUT = int(os.getenv("WORKER_TIMEOUT", "600"))  # 10分钟

    # ===== Docker 配置 =====
    DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "python:3.10-slim")
    DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "300"))  # 5分钟

    # ===== Worker 配置 =====
    MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))

    # ===== 存储路径 =====
    SKILLS_DIR = Path.home() / ".ai_skills"
    DATA_DIR = Path(__file__).parent.parent / "data"
    LOGS_DIR = Path(__file__).parent.parent / "logs"

    # ===== Claude SDK 配置 =====
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet")
    PERMISSION_MODE = os.getenv("PERMISSION_MODE", "bypassPermissions")

    # 自定义 API 配置（用于使用其他厂商的兼容 API）
    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
    ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN", "")

    # ===== Context 7 MCP =====
    # ⚠️ TODO: 建议改为从环境变量读取，不要硬编码
    CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY", "")
    CONTEXT7_API_URL = os.getenv("CONTEXT7_API_URL", "https://mcp.context7.com/mcp")

    @classmethod
    def init(cls):
        """初始化所有目录"""
        cls.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
```

### 9.1 配置使用指南

#### 环境变量优先级

所有配置项都支持通过环境变量覆盖，优先级如下：

```
环境变量 > Config 类默认值
```

示例：
```bash
# .env 文件
MAX_CONCURRENT_WORKERS=5
WORKER_TIMEOUT=900

# 代码中
orchestrator = SkillFactoryOrchestrator()
# 实际使用 MAX_CONCURRENT_WORKERS=5，而不是默认的 3
```

#### 根据机器性能调整并发数

| 机器配置 | 推荐 MAX_CONCURRENT_WORKERS | 推荐 WORKER_TIMEOUT |
|---------|---------------------------|---------------------|
| **低配** (<4GB RAM, 2核 CPU) | 1-2 | 900 (15分钟) |
| **中配** (4-8GB RAM, 4核 CPU) | 3 | 600 (10分钟) |
| **高配** (>8GB RAM, 8+核 CPU) | 5 | 600 (10分钟) |

**调整建议**：
- 并发数过高可能导致内存不足或 API 限流
- 并发数过低会降低整体效率
- 建议从默认值 3 开始，根据实际情况调整

#### 运行时覆盖配置

```python
# 方法 1: 通过构造函数覆盖
orchestrator = SkillFactoryOrchestrator(max_concurrent=5)

# 方法 2: 通过环境变量覆盖
import os
os.environ["MAX_CONCURRENT_WORKERS"] = "5"
orchestrator = SkillFactoryOrchestrator()
```

#### 使用其他厂商的兼容 API

如果你的厂商提供兼容 Anthropic API 的服务，可以通过以下配置使用：

```bash
# .env 文件
ANTHROPIC_BASE_URL=https://your-provider.com/v1
ANTHROPIC_AUTH_TOKEN=your-provider-api-key
CLAUDE_MODEL=your-model-name
```

**支持的厂商**（需兼容 Anthropic API 格式）：
- AWS Bedrock (Claude)
- Google Cloud Vertex AI (Claude)
- 其他兼容 OpenAI/Anthropic 格式的 API 服务

**工作原理**：
SDK 会将 `ANTHROPIC_BASE_URL` 和 `ANTHROPIC_AUTH_TOKEN` 通过 `ClaudeAgentOptions.env` 传递给底层 CLI，从而覆盖默认的 Anthropic API 端点。

---

## 10. 核心优势

✅ **完全自驱动**：启动后无需人工干预，一次跑完所有技能
✅ **并发执行**：asyncio + Semaphore 实现 3 个技能并行，效率提升 3 倍
✅ **错误隔离**：Docker 容器确保失败代码不影响主 Agent
✅ **超时保护**：Worker 超时 + Docker timeout 双重保障
✅ **标准化输出**：符合 Claude Skill 规范，直接可用
✅ **可追踪**：详细的日志和结果记录，便于调试
✅ **可扩展**：支持动态添加新技能到任务清单
✅ **高可靠性**：自动修复机制 + 人工审查的备选方案  

---

## 11. Research 阶段优化详解

### 11.1 调研策略优化的核心思想

**三种策略**：
- **Context 7 优先**（推荐）：成本低、速度快，适合主流库
- **本地爬取优先**：详尽全面，适合冷门库或需要最新版本
- **混合模式**：最全面，适合关键技能

**知识蒸馏**（关键！）：
- 提取 3-5 个**核心概念**
- 筛选 10-20 个**关键 API**
- 提取 3-5 个**使用示例**
- 列出 3-5 个**最佳实践**
- 最终控制在 **5000-10000 token**（可在一个 prompt 内处理）

**预期收益**：⚡ 成本降低 30-50% | 📉 延迟降低 | 🎯 准确度提升 | 🔧 灵活性提升

---

## 12. 包管理：使用 uv（推荐）

### 12.1 为什么选择 uv？

- ✅ 速度快 10-100 倍（用 Rust 实现）
- ✅ 单一工具（包管理 + 版本管理 + 运行脚本）
- ✅ Python 官方推荐（Astral 主导）
- ✅ pyproject.toml 优先（现代化）
- ✅ 无缝集成 VSCode + Pylance

### 12.2 快速开始

```bash
# 安装 uv
pip install uv

# 初始化环境
uv sync

# 激活虚拟环境（Windows PowerShell）
.\.venv\Scripts\Activate.ps1

# 运行 Agent
uv run python run_agent.py
```

### 12.3 常用命令

```bash
uv sync              # 安装所有依赖
uv add anthropic     # 添加包
uv add --dev pytest  # 添加开发依赖
uv run python ...    # 运行 Python
```

---

**下一步**：开始实现代码骨架！
1. `src/models.py` - 数据结构
2. `src/config.py` - 配置管理
3. `src/orchestrator.py` - 主调度器
4. `src/worker.py` - Worker Agent
