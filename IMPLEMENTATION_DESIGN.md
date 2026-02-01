# 🎯 SkillFactory Agent - 实现设计文档

**时间**：2026-02-01  
**版本**：v1.0  
**目标**：基于 Claude Agent SDK + Docker 隔离环境，自动孵化可运行的技能(Skills)

---

## 1. 架构全景图

```
┌─────────────────────────────────────────────────────────────┐
│                    SkillFactory Agent                        │
│          (独立Docker容器内运行，无需中断)                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Main Orchestrator (single-threaded)         │   │
│  │  - 读取 skills_todo.json (技能孵化任务清单)          │   │
│  │  - 顺序遍历每个技能                                  │   │
│  │  - 初始化 Worker Agent                              │   │
│  │  - 等待 Worker 完成，保存结果                        │   │
│  └─────────────────────────────────────────────────────┘   │
│           ↓                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │      Worker Agent (ClaudeSDKClient)                 │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────┐    │   │
│  │  │   Round 1: Research                        │    │   │
│  │  │  - 调用 skill-browser-crawl 爬取文档       │    │   │
│  │  │  - 可选：Context7 MCP 查询外部文档        │    │   │
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
│  │  │ (Crawl4AI)      │  │   resolve-library)  │    │   │
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

```python
# Agent 一旦启动，就持续跑完全部任务队列，不依赖外部确认
# 这与原 PRD 的 "permission_mode='acceptEdits'" 不同

class OrchestratorLoop:
    async def run(self):
        todos = load_skills_todo()  # 从文件读取任务清单
        for skill_spec in todos:
            try:
                result = await self.spawn_worker_and_wait(skill_spec)
                self.save_result(result)
            except Exception as e:
                self.log_error(skill_spec, e)
                # 继续下一个技能，不中断
        
        self.generate_summary_report()
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

Worker Agent 可选调用 Context 7 获取额外信息。

参考 `.agents/skills/skill-creator/SKILL.md`：

- **SKILL.md**: YAML frontmatter (name, description) + Markdown body
- **scripts/**: 可复用的代码脚本
- **references/**: 文档参考资料
- **assets/**: 模板、图片等非代码资源
- **package_skill.py**: 打包为 `.skill` 文件（zip格式）

```
my-skill/
├── SKILL.md
├── scripts/
│   ├── demo.py
│   └── requirements.txt
├── references/
│   └── api_docs.md
└── assets/
    └── example.json
```

---

## 3. Worker Agent 的自愈循环 (Self-Healing Loop)

### 阶段 1：研究 (Research)

```
Worker Prompt (第1轮):
  "获取关键词 'LlamaIndex v0.10 Entity Extraction' 的最新文档。
   使用 browser_crawl 工具访问官方文档、GitHub repo，整理成 Markdown。
   确保包含：版本信息、核心概念、依赖说明。"

Action:
  - 调用 browser_crawl("https://docs.llamaindex.ai/...")
  - 收集官方文档、示例代码、API参考
  - Claude 总结成结构化 Markdown
```

### 阶段 2：草稿 (Drafting)

```
Worker Prompt (第2轮，Claude记住研究结果):
  "基于刚才整理的 LlamaIndex 文档，生成一个可运行的 demo.py。
   要求：
   - 所有依赖列在 requirements.txt 中
   - 代码包含 assert 验证逻辑
   - 演示核心概念：如何使用 Entity Extraction"

Action:
  - Claude 生成 demo.py + requirements.txt
  - write_skill 工具保存到临时目录
```

### 阶段 3-N：测试与修复 (Test & Fix Loop)

```
Worker Prompt (第3轮):
  "执行 demo.py，确保能在干净的环境中运行。
   使用 docker_execute 工具。"

Action:
  - docker_execute(code=demo_code, dependencies=requirements)
  - 返回 {status, exit_code, logs}

Outcome:
  ✅ 成功 → 进入阶段 N+1: Distill
  ❌ 失败 → 阶段 3.1: Analyze

阶段 3.1：失败分析与修复
Worker Prompt:
  "代码执行失败，报错如下：
   [stderr 内容]
   
   分析错误原因（版本问题/逻辑错误/依赖缺失），修复代码。
   重新提交 docker_execute。"

Action:
  - Claude 分析错误
  - 修改 demo.py / requirements.txt
  - 再次 docker_execute
  
重试策略:
  - 最多重试 3 次
  - 第 4 次失败 → 记录为"待人工审查"
  - 不返回，继续下一个技能
```

### 阶段 N+1：蒸馏与打包 (Distill & Package)

```
Worker Prompt (最后一轮):
  "代码已验证可运行。现在总结一个完整的 Skill，包括：
   
   1. SKILL.md:
      - frontmatter: name, description
      - body: 核心概念、使用指南、最佳实践、版本注意
   
   2. scripts/demo.py: 验证过的代码
   
   3. scripts/requirements.txt: 依赖列表
   
   4. references/api_docs.md: 官方文档摘要
   
   5. assets/: 示例配置文件等（如适用）
   
   使用 write_skill 工具生成完整的技能目录。"

Action:
  - Claude 调用 write_skill 生成目录结构
  - 调用 shell 执行 package_skill.py
  - 生成 skill-name.skill 文件
  - 记录成功日志
```

---

## 4. 系统组件定义

### 4.1 Orchestrator (orchestrator.py)

```python
class SkillFactoryOrchestrator:
    """
    主调度器，单线程顺序处理技能孵化任务
    """
    
    async def run(self):
        """
        主循环：
        1. load_skills_todo() → List[SkillSpec]
        2. for each skill: spawn_worker_and_wait()
        3. generate_summary()
        """
        
    async def spawn_worker_and_wait(self, skill_spec: SkillSpec):
        """
        为一个技能启动 Worker Agent，等待完成
        """
        worker = SkillFactoryWorker(skill_spec)
        result = await worker.run()
        return result
    
    def save_result(self, skill_name: str, result: SkillResult):
        """
        保存技能到 ~/.ai_skills/
        """
```

### 4.2 Worker Agent (worker.py)

```python
class SkillFactoryWorker:
    """
    基于 ClaudeSDKClient 的单个技能孵化 Agent
    
    特点：
    - 多轮对话（ClaudeSDKClient 维持会话）
    - 调用唯一的 MCP 工具：fetch_external_docs
    - 使用 Claude Code 的 Write/Edit 工具来创建文件
    - 调用 skill-creator 元 Skill 来打包
    - 自动修复失败（重试 3 次）
    - 最终生成 Skill
    """
    
    def __init__(self, skill_spec: SkillSpec):
        self.skill_spec = skill_spec
        self.mcp_server = self._setup_mcp_tools()
        self.client_options = ClaudeAgentOptions(
            mcp_servers={"skill_factory": self.mcp_server},
            allowed_tools=[
                "mcp__skill_factory__fetch_external_docs",
                "Read",        # Claude Code 自带工具
                "Write",       # Claude Code 自带工具
                "Edit",        # Claude Code 自带工具
                "Bash",        # 用于执行 docker 等
            ],
            permission_mode="bypassPermissions",  # 完全自驱动
            cwd=str(Config.SKILLS_DIR)  # 工作目录
        )
    
    async def run(self) -> SkillResult:
        """
        执行完整的自愈循环
        """
        async with ClaudeSDKClient(options=self.client_options) as client:
            # Round 1: Research (获取外部文档)
            await client.query(self._prompt_research())
            async for msg in client.receive_response():
                pass  # Claude 调用 fetch_external_docs
            
            # Round 2: Drafting (生成 demo.py + requirements.txt)
            await client.query(self._prompt_drafting())
            async for msg in client.receive_response():
                pass  # Claude 用 Write 工具创建文件
            
            # Round 3+: Test & Fix (Docker 执行 + 修复)
            for attempt in range(1, 4):
                await client.query(self._prompt_test(attempt))
                async for msg in client.receive_response():
                    pass  # Claude 用 Bash 调用 docker run
                
                if self._is_success():
                    break
            
            # Round N+1: Distill & Package (生成 SKILL.md + 打包)
            await client.query(self._prompt_distill())
            async for msg in client.receive_response():
                pass  # Claude 用 Write 创建 SKILL.md，调用 skill-creator
        
        return SkillResult(...)
    
    def _setup_mcp_tools(self) -> McpSdkServerConfig:
        """
        创建 MCP 服务器，只包含 fetch_external_docs
        """
```

### 4.3 MCP 工具集 (tools.py)

#### 核心 MCP 工具：fetch_external_docs

```python
@tool(
    "fetch_external_docs",
    "Fetch documentation/code snippets from official sources (PyPI, GitHub API, etc.)",
    {
        "keyword": str,  # e.g., "LlamaIndex v0.10"
        "source_type": str,  # "pypi" | "github" | "official_docs"
        "url": str,  # optional, specific URL to fetch
    }
)
async def fetch_external_docs(args: dict[str, Any]) -> dict[str, Any]:
    """
    从官方来源获取文档片段、依赖信息、版本信息等
    
    支持的来源：
    - PyPI API: 获取最新版本、依赖关系、更新日期
    - GitHub API: 获取 README、latest release notes、示例代码
    - 官方文档: Crawl4AI 获取 HTML → Markdown
    
    这是与外部世界的唯一接口！
    """
    import json
    from typing import Dict, Any
    
    keyword = args["keyword"]
    source_type = args.get("source_type", "official_docs")
    url = args.get("url")
    
    results = {}
    
    # 1. PyPI 信息（包版本、依赖、更新日期）
    if source_type in ["pypi", "all"]:
        results["pypi"] = await _fetch_pypi_info(keyword)
    
    # 2. GitHub 信息（最新代码、示例、issues）
    if source_type in ["github", "all"]:
        results["github"] = await _fetch_github_info(keyword)
    
    # 3. 官方文档（HTML → Markdown）
    if source_type in ["official_docs", "all"] or url:
        results["docs"] = await _fetch_official_docs(url or keyword)
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(results, ensure_ascii=False, indent=2)
        }]
    }


async def _fetch_pypi_info(keyword: str) -> Dict[str, Any]:
    """从 PyPI 获取包信息"""
    import httpx
    
    # Extract package name from keyword (e.g., "LlamaIndex v0.10" → "llama-index")
    package_name = keyword.lower().split()[0]
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://pypi.org/pypi/{package_name}/json")
            if response.status_code == 200:
                data = response.json()
                return {
                    "latest_version": data["info"]["version"],
                    "updated_at": data["info"]["last_updated"],
                    "summary": data["info"]["summary"],
                    "requires_python": data["info"]["requires_python"],
                    "requires_dist": data["info"]["requires_dist"],
                    "classifiers": data["info"]["classifiers"]
                }
    except Exception as e:
        return {"error": str(e)}
    
    return {}


async def _fetch_github_info(keyword: str) -> Dict[str, Any]:
    """从 GitHub API 获取最新代码、示例、release notes"""
    import httpx
    import os
    
    # 这需要 Claude 在 prompt 中提供完整的 repo path
    # 或者在更高层的 prompt 中指定搜索策略
    
    github_token = os.getenv("GITHUB_TOKEN", "")
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    return {
        "note": "GitHub API 集成：Claude 应该通过 fetch_external_docs(keyword, source_type='github', url='github.com/owner/repo') 调用"
    }


async def _fetch_official_docs(keyword_or_url: str) -> Dict[str, Any]:
    """使用 Crawl4AI 爬取官方文档"""
    from crawl4ai import AsyncWebCrawler
    
    # 如果是 URL，直接爬取；否则尝试常见 URL 模式
    url = keyword_or_url if keyword_or_url.startswith("http") else None
    
    if not url:
        keyword = keyword_or_url.lower().replace(" ", "-")
        urls_to_try = [
            f"https://{keyword}.readthedocs.io/",
            f"https://docs.{keyword}.io/",
        ]
    else:
        urls_to_try = [url]
    
    try:
        async with AsyncWebCrawler() as crawler:
            for try_url in urls_to_try:
                try:
                    result = await crawler.arun(url=try_url)
                    return {
                        "url": try_url,
                        "markdown": result.markdown[:10000],  # 限制长度
                        "title": result.title if hasattr(result, 'title') else "N/A"
                    }
                except:
                    continue
    except Exception as e:
        return {"error": str(e)}
    
    return {"error": "No docs found"}
```

---

## 5. 为什么只有一个 MCP 工具？

### 传统方案（我之前的建议）
```
MCP 工具：
  - browser_crawl      ❌ 其实不需要 MCP，CLI 工具更好
  - docker_execute     ❌ 其实不需要 MCP，可以用 Bash 工具
  - write_skill        ❌ Claude Code 的 Write 工具就够了
  - package_skill      ❌ 可以调用 skill-creator 这个元 Skill
```

### 新方案（更简洁）
```
MCP 工具：
  - fetch_external_docs  ✅ 唯一需要的！获取外部数据

其他工具：
  - Claude Code Write/Edit  → 创建文件、目录
  - Claude Code Bash        → 执行 docker run
  - skill-creator Skill     → 打包为 .skill 文件
```

**优势：**
- MCP 工具集最小化 → 更易维护
- Docker 执行用 Bash 工具 → 不需要特殊权限
- 文件创建用 Claude Code → 原生支持，无需额外工具
- 打包逻辑复用 skill-creator → 不重复造轮子
```

### 4.3 MCP 工具集 (tools.py)

#### 核心 MCP 工具：fetch_external_docs

```python
@tool(
    "fetch_external_docs",
    "Fetch documentation/code snippets from official sources (PyPI, GitHub API, etc.)",
    {
        "keyword": str,  # e.g., "LlamaIndex v0.10"
        "source_type": str,  # "pypi" | "github" | "official_docs"
        "url": str,  # optional, specific URL to fetch
    }
)
async def fetch_external_docs(args: dict[str, Any]) -> dict[str, Any]:
    """
    从官方来源获取文档片段、依赖信息、版本信息等
    
    支持的来源：
    - PyPI API: 获取最新版本、依赖关系、更新日期
    - GitHub API: 获取 README、latest release notes、示例代码
    - 官方文档: Crawl4AI 获取 HTML → Markdown
    
    这是与外部世界的唯一接口！
    """
    import json
    from typing import Dict, Any
    
    keyword = args["keyword"]
    source_type = args.get("source_type", "official_docs")
    url = args.get("url")
    
    results = {}
    
    # 1. PyPI 信息（包版本、依赖、更新日期）
    if source_type in ["pypi", "all"]:
        results["pypi"] = await _fetch_pypi_info(keyword)
    
    # 2. GitHub 信息（最新代码、示例、issues）
    if source_type in ["github", "all"]:
        results["github"] = await _fetch_github_info(keyword)
    
    # 3. 官方文档（HTML → Markdown）
    if source_type in ["official_docs", "all"] or url:
        results["docs"] = await _fetch_official_docs(url or keyword)
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(results, ensure_ascii=False, indent=2)
        }]
    }


async def _fetch_pypi_info(keyword: str) -> Dict[str, Any]:
    """从 PyPI 获取包信息"""
    import httpx
    
    # Extract package name from keyword (e.g., "LlamaIndex v0.10" → "llama-index")
    package_name = keyword.lower().split()[0]
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://pypi.org/pypi/{package_name}/json")
            if response.status_code == 200:
                data = response.json()
                return {
                    "latest_version": data["info"]["version"],
                    "updated_at": data["info"]["last_updated"],
                    "summary": data["info"]["summary"],
                    "requires_python": data["info"]["requires_python"],
                    "requires_dist": data["info"]["requires_dist"],
                    "classifiers": data["info"]["classifiers"]
                }
    except Exception as e:
        return {"error": str(e)}
    
    return {}


async def _fetch_github_info(keyword: str) -> Dict[str, Any]:
    """从 GitHub API 获取最新代码、示例、release notes"""
    import httpx
    import os
    
    # e.g., "LlamaIndex" → "run-llama/llama-index"
    # 这里需要手动映射或 Claude 自己提供完整的 repo path
    
    github_token = os.getenv("GITHUB_TOKEN", "")
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    # 假设 Claude 已经知道 repo path，通过 keyword 推导
    # 或者在更高层的 prompt 中指定
    
    return {
        "note": "GitHub API 集成需要明确的 repo path，建议由 Claude prompt 提供"
    }


async def _fetch_official_docs(keyword_or_url: str) -> Dict[str, Any]:
    """使用 Crawl4AI 爬取官方文档"""
    from crawl4ai import AsyncWebCrawler
    
    # 如果是 URL，直接爬取；否则先搜索
    url = keyword_or_url if keyword_or_url.startswith("http") else None
    
    if not url:
        # 需要搜索，简单方案：try common patterns
        keyword = keyword_or_url.lower().replace(" ", "-")
        urls_to_try = [
            f"https://docs.llamaindex.ai/en/stable/",
            f"https://{keyword}.readthedocs.io/",
            f"https://github.com/search?q={keyword}",
        ]
    else:
        urls_to_try = [url]
    
    try:
        async with AsyncWebCrawler() as crawler:
            for try_url in urls_to_try:
                try:
                    result = await crawler.arun(url=try_url)
                    return {
                        "url": try_url,
                        "markdown": result.markdown,
                        "title": result.title if hasattr(result, 'title') else "N/A"
                    }
                except:
                    continue
    except Exception as e:
        return {"error": str(e)}
    
    return {"error": "No docs found"}
```

**为什么只有这一个工具？**

- **write_skill**: Claude Code 自己有 Write、Edit 工具，可以直接创建文件和目录
- **package_skill**: 交给 skill-creator 这个元 skill 来处理，Claude 可以调用它
- **docker_execute**: 可以做成一个独立的 Skill（包含执行指令和隔离逻辑）
- **browser_crawl**: 可以做成一个独立的 Skill（包含爬虫策略和解析逻辑）

**只有 fetch_external_docs 需要作为 MCP 工具**，因为它需要：
1. 在 Agent 内部运行
2. 调用外部 API（PyPI、GitHub、Crawl4AI）
3. 返回结构化数据给 Claude 做后续处理

---

## 5. 数据结构定义

### 5.1 SkillSpec (输入)

```python
from dataclasses import dataclass

@dataclass
class SkillSpec:
    """
    技能孵化任务规范
    """
    name: str  # "skill-001-llamaindex-extraction"
    keyword: str  # "LlamaIndex v0.10 Entity Extraction"
    description: str  # "Learn Entity Extraction with LlamaIndex"
    references: list[str] = None  # ["https://docs.llamaindex.ai/...", "https://github.com/..."]
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

### 5.3 skills_todo.json (任务清单)

```json
{
  "skills": [
    {
      "name": "skill-001-llamaindex-extraction",
      "keyword": "LlamaIndex v0.10 Entity Extraction",
      "description": "Learn Entity Extraction with LlamaIndex",
      "references": [
        "https://docs.llamaindex.ai/en/stable/modules/querying/retriever/",
        "https://github.com/run-llama/llama_index/tree/main/llama-index-core/llama_index/extractors"
      ]
    },
    {
      "name": "skill-002-fastapi-websocket",
      "keyword": "FastAPI WebSocket Authentication",
      "description": "Secure WebSocket connections in FastAPI",
      "references": [...]
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
for each skill_spec in skills:
  │
  ├─ Orchestrator: spawn_worker(skill_spec)
  │
  ├─ Worker: 初始化 ClaudeSDKClient + 唯一的 MCP 工具
  │
  ├─ Round 1 (Research):
  │   Claude → fetch_external_docs(keyword) 
  │   获取 PyPI、GitHub、官方文档信息
  │
  ├─ Round 2 (Drafting):
  │   Claude → Write 工具创建 demo.py + requirements.txt
  │   (使用 Claude Code 原生工具)
  │
  ├─ Round 3 (Test):
  │   Claude → Bash 工具执行: docker run -it python:3.10-slim ...
  │   ├─ ✅ Exit 0: continue to Round N+1
  │   └─ ❌ Exit != 0: 进入 Round 3.1
  │
  ├─ Round 3.1+ (Fix Loop, 最多 3 次):
  │   Claude → 分析错误 → Edit 工具修改代码
  │   Claude → Bash 工具重新执行 docker run
  │   ├─ ✅ Exit 0: continue to Round N+1
  │   ├─ ❌ 第 3 次失败: 记录为"待人工审查"，跳到 save_result
  │   └─ ❌ timeout: 同上
  │
  ├─ Round N+1 (Distill):
  │   Claude → Write 工具创建 SKILL.md
  │   (包含 frontmatter + body，参考 skill-creator 规范)
  │
  ├─ Round N+2 (Package):
  │   Claude → Bash 工具或 Python 脚本调用 skill-creator
  │   生成 skill-name.skill 文件
  │   (基于 ~/.agents/skills/skill-creator/ 中的 package_skill.py)
  │
  └─ save_result(skill_result)
     记录到 results_log.json

全部完成
  ↓
generate_summary_report()
  - 成功数、失败数、待审查数
  - 每个技能的输出路径
```

---

## 7. 关键的 Worker Prompt 模板

### Prompt 1: Research

```
你是一个资深技术研究员。你的任务是深入研究技术主题，获取最新的官方文档和版本信息。

技能名称: {skill_name}
研究关键词: {keyword}
描述: {description}

你需要：
1. 使用 fetch_external_docs 工具，获取以下信息：
   - PyPI 包信息（最新版本、依赖、更新日期）
   - GitHub 仓库信息（latest release、代码示例）
   - 官方文档（HTML → Markdown）
   
   建议的调用序列：
   - fetch_external_docs(keyword={keyword}, source_type="pypi")
   - fetch_external_docs(keyword={keyword}, source_type="github", url="https://github.com/...")
   - fetch_external_docs(url="https://docs.{keyword}.io/")

2. 整理成结构化的研究报告，包含：
   - 版本信息和更新日期
   - 核心概念解释
   - 依赖说明（Python 版本、pip packages 等）
   - 基本用法示例代码片段
   - 常见问题和最佳实践

3. 确保内容准确、完整、最新。
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

3. 完成后，告诉我文件路径。
```

### Prompt 3: Test (Attempt N)

```
现在测试代码的可运行性。这是第 {attempt}/3 次尝试。

你需要：
1. 使用 Bash 工具执行以下命令：
   
   docker run --rm -v ~/.ai_skills/{skill_name}/scripts:/app python:3.10-slim bash -c "
   cd /app && \
   pip install -q -r requirements.txt && \
   python demo.py
   "

2. 检查返回的输出：
   - 若包含 "AssertionError": 说明逻辑错误，需要修复
   - 若包含 "ModuleNotFoundError": 说明依赖缺失或版本不对，需要修复
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

2. 若需要，创建 references/ 或 assets/ 目录：
   - Write 工具创建 ~/.ai_skills/{skill_name}/references/api_docs.md
   - 或创建 ~/.ai_skills/{skill_name}/assets/example.json 等

3. 完成后，使用 Bash 工具执行打包命令：
   
   python ~/.agents/skills/skill-creator/scripts/package_skill.py ~/.ai_skills/{skill_name}
   
   这会生成 ~/.ai_skills/{skill_name}.skill 文件
```

---

## 8. 文件结构

```
SkillFactory_agent/
├── IMPLEMENTATION_DESIGN.md (本文档)
├── PRD.md (原需求文档)
├── Agent SDK 参考 - Python.md
│
├── src/
│   ├── orchestrator.py        # 主调度器
│   ├── worker.py              # Worker Agent
│   ├── tools.py               # MCP 工具实现
│   ├── models.py              # 数据结构
│   └── config.py              # 配置管理
│
├── data/
│   ├── skills_todo.json       # 任务清单
│   └── results_log.json       # 执行结果日志
│
├── .ai_skills/                # 生成的技能存储
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
    - docker
    - python-dotenv
```

---

## 9. 配置管理 (config.py)

```python
from pathlib import Path
from typing import Optional
import os

class Config:
    """配置管理"""
    
    # Docker 配置
    DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "python:3.10-slim")
    MAX_DOCKER_TIMEOUT = 300  # 5 分钟
    
    # Worker 配置
    MAX_RETRY_ATTEMPTS = 3
    MAX_WORKER_TIMEOUT = 600  # 10 分钟
    
    # 存储路径
    SKILLS_DIR = Path.home() / ".ai_skills"
    DATA_DIR = Path(__file__).parent.parent / "data"
    LOGS_DIR = Path(__file__).parent.parent / "logs"
    
    # Claude SDK 配置
    CLAUDE_MODEL = "claude-3-5-sonnet"  # 或其他
    PERMISSION_MODE = "bypassPermissions"
    
    # Crawl4AI 配置
    CRAWL4AI_TIMEOUT = 30
    
    @classmethod
    def init(cls):
        """初始化所有目录"""
        cls.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
```

---

## 10. 关键改进点 vs. 原 PRD

| 方面 | 原 PRD | 新设计 |
|------|--------|--------|
| **并发** | asyncio.gather (3个并发) | 单线程顺序处理（更稳定） |
| **中断** | 需要人工确认 | 完全自驱动，无中断 |
| **Docker** | 提及但无具体方案 | Bash 工具调用 docker run，容器隔离 |
| **SandboxSettings** | 使用 Agent SDK 的沙箱 | 不使用，容器本身提供隔离 |
| **MCP 工具** | 4 个（browser, docker, write, package） | **1 个**（fetch_external_docs） |
| **文件创建** | write_skill MCP 工具 | Claude Code 原生 Write 工具 |
| **打包逻辑** | package_skill MCP 工具 | 复用 skill-creator 脚本 |
| **错误恢复** | 提及但无机制 | 最多 3 次重试，清晰的失败记录 |

---

## 11. 核心优势

✅ **完全自驱动**：启动后无需人工干预，一次跑完所有技能  
✅ **错误隔离**：Docker 容器确保失败代码不影响主 Agent  
✅ **标准化输出**：符合 Claude Skill 规范，直接可用  
✅ **可追踪**：详细的日志和结果记录，便于调试  
✅ **可扩展**：支持动态添加新技能到任务清单  
✅ **高可靠性**：自动修复机制 + 人工审查的备选方案  
✅ **最小化 MCP 工具**：只有一个工具，职责单一（获取外部文档）  
✅ **复用现有资源**：利用 Claude Code、skill-creator，减少重复造轮子  

---

**下一步**：开始实现代码骨架！

