from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .config import Config
from .models import SkillResult, SkillSpec
from .utils.docker_multilang import MultiLangDockerRunner


class SkillFactoryWorker:
    """基于 ClaudeSDKClient 的单个技能孵化 Agent"""

    def __init__(self, skill_spec: SkillSpec):
        self.skill_spec = skill_spec
        self._last_test_success: bool = False
        self._last_error: str = ""
        self.logger = logging.getLogger("skillfactory")
        self.docker_runner = MultiLangDockerRunner()  # 多语言 Docker 执行器

        env_vars: dict[str, str] = {}
        if Config.ANTHROPIC_BASE_URL:
            env_vars["ANTHROPIC_BASE_URL"] = Config.ANTHROPIC_BASE_URL
        if Config.ANTHROPIC_AUTH_TOKEN:
            env_vars["ANTHROPIC_AUTH_TOKEN"] = Config.ANTHROPIC_AUTH_TOKEN

        self.client_options = ClaudeAgentOptions(
            mcp_servers={
                "context7": {
                    "type": "http",
                    "url": Config.CONTEXT7_API_URL,
                    "headers": {"CONTEXT7_API_KEY": Config.CONTEXT7_API_KEY},
                    "tools": ["query-docs", "resolve-library-id"],
                }
            },
            allowed_tools=[
                "mcp__context7__query-docs",
                "mcp__context7__resolve-library-id",
                "Skill",  # 启用 Skill 工具以使用 .claude/skills/ 中的技能
                "Read",
                "Write",
                "Edit",
                "Bash",
            ],
            # 禁止网页相关工具，强制使用 Skill 爬取
            disallowed_tools=[
                "WebSearch",
                "WebFetch",
                "webReader",
                "BrowserFetch",
            ],
            permission_mode=Config.PERMISSION_MODE,
            model=Config.CLAUDE_MODEL,
            env=env_vars,
            # 设置 cwd 为项目根目录，这样 .claude/skills/ 才能被正确加载
            cwd=str(Config.ROOT_DIR),
            # 从文件系统加载 Skills（从 project 和 user 目录）
            setting_sources=["project", "user"],
        )
        
        self.logger.info(f"Worker initialized for skill: {skill_spec.name}")
        self.logger.info(f"Research strategy: {skill_spec.research_strategy}")
        self.logger.info(f"Allowed tools: {self.client_options.allowed_tools}")
        self.logger.info(f"Disallowed tools: {self.client_options.disallowed_tools}")
        self.logger.info(f"Setting sources: {self.client_options.setting_sources}")
        self.logger.info(f"CWD: {self.client_options.cwd}")

    async def run(self) -> SkillResult:
        skill_dir = Config.SKILLS_DIR / self.skill_spec.name
        skill_file = Config.SKILLS_DIR / f"{self.skill_spec.name}.skill"
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 检查 Docker 是否可用
        docker_available = await self.docker_runner.check_docker_available()
        if not docker_available:
            self.logger.warning("Docker not available, skipping code validation")

        async with ClaudeSDKClient(options=self.client_options) as client:
            self.logger.info("Worker start: %s", self.skill_spec.name)
            
            # Round 1: Research
            await self._run_round(client, self._prompt_research())
            
            # Round 2: Drafting (生成简单的 demo.py 和 requirements.txt)
            await self._run_round(client, self._prompt_drafting())
            
            # Round 3-N: Test & Fix Loop (如果 Docker 可用)
            if docker_available:
                for attempt in range(1, Config.MAX_RETRY_ATTEMPTS + 1):
                    self.logger.info(f"Test attempt {attempt}/{Config.MAX_RETRY_ATTEMPTS}")
                    
                    # 读取生成的代码
                    demo_file = skill_dir / "scripts" / self._get_code_filename()
                    req_file = skill_dir / "scripts" / self._get_deps_filename()
                    
                    if not demo_file.exists() or not req_file.exists():
                        self.logger.warning("Code files not found, skipping test")
                        break
                    
                    code = demo_file.read_text(encoding="utf-8")
                    dependencies = req_file.read_text(encoding="utf-8")
                    
                    # 在 Docker 中运行代码（传递语言参数）
                    result = await self.docker_runner.run_code(
                        code=code,
                        dependencies=dependencies,
                        work_dir=skill_dir / "scripts",
                        language=self.skill_spec.language,
                    )
                    
                    if result.success:
                        self.logger.info("Code validation successful!")
                        self._last_test_success = True
                        break
                    else:
                        self.logger.warning(f"Code validation failed (attempt {attempt})")
                        self._last_error = result.stderr or result.error or "Unknown error"
                        
                        # 如果不是最后一次尝试，让 Claude 修复代码
                        if attempt < Config.MAX_RETRY_ATTEMPTS:
                            await self._run_round(
                                client,
                                self._prompt_fix(attempt, result),
                                check_test_status=False,
                            )
                        else:
                            self.logger.error("Max retry attempts reached, code validation failed")
            
            # Round N+1: Distill (生成最终 SKILL.md)
            await self._run_round(client, self._prompt_distill())
            
            status = "success" if self._last_test_success or not docker_available else "partial_success"
            self.logger.info("Worker end: %s (%s)", self.skill_spec.name, status)

        return SkillResult(
            skill_name=self.skill_spec.name,
            status=status,
            skill_dir=str(skill_dir),
            skill_file=str(skill_file),
            demo_code="",
            error_log=self._last_error,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _run_round(
        self, client: ClaudeSDKClient, prompt: str, check_test_status: bool = False
    ) -> None:
        self.logger.info("Round start (%s): %s", self.skill_spec.name, prompt.splitlines()[0])
        await client.query(prompt)
        response_text = await self._collect_response_text(client)
        # 打印响应摘要（前 500 字符），便于调试
        response_summary = response_text[:500].replace("\n", " ")
        self.logger.debug("Response (%s): %s...", self.skill_spec.name, response_summary)
        if check_test_status:
            self._update_test_status(response_text)
        self.logger.info("Round end (%s)", self.skill_spec.name)

    async def _collect_response_text(self, client: ClaudeSDKClient) -> str:
        parts: list[str] = []

        async def _collect() -> None:
            try:
                async for message in client.receive_response():
                    # 打印消息类型用于调试
                    msg_type = type(message).__name__
                    self.logger.debug(f"Received message type: {msg_type}")
                    
                    # 跳过 SystemMessage，只处理 AssistantMessage 和 ResultMessage
                    if hasattr(message, "content") and isinstance(getattr(message, "content"), list):
                        # AssistantMessage 有 content: list[ContentBlock]
                        content = getattr(message, "content")
                        self.logger.debug(f"Content blocks count: {len(content)}")
                        
                        for block in content:
                            block_type = type(block).__name__
                            self.logger.debug(f"Content block type: {block_type}")
                            
                            if hasattr(block, "text"):
                                text = str(getattr(block, "text"))
                                if text.strip():
                                    parts.append(text)
                                    self.logger.debug(f"Extracted text ({len(text)} chars)")
                            elif hasattr(block, "name"):
                                # ToolUseBlock
                                tool_name = getattr(block, "name", "unknown")
                                self.logger.info(f"Tool called: {tool_name}")
                    
                    # 当收到 ResultMessage 时停止
                    if hasattr(message, "subtype") and getattr(message, "subtype") == "final":
                        self.logger.debug("Received final message, stopping collection")
                        break
            except Exception as e:
                self.logger.debug(f"Error collecting response ({self.skill_spec.name}): {e}")

        try:
            await asyncio.wait_for(_collect(), timeout=Config.ROUND_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger.warning(
                "Round timeout after %s seconds (%s)",
                Config.ROUND_TIMEOUT,
                self.skill_spec.name,
            )
        
        response_text = "\n".join(parts)
        self.logger.info(f"Response collected ({self.skill_spec.name}): {len(response_text)} chars")
        return response_text

    @staticmethod
    def _message_to_text(message: object) -> str:
        """已废弃，改为在 _collect_response_text 中直接处理"""
        if hasattr(message, "content"):
            content = getattr(message, "content")
            if isinstance(content, list):
                texts = []
                for block in content:
                    if hasattr(block, "text"):
                        texts.append(str(getattr(block, "text")))
                if texts:
                    return "\n".join(texts)
        return str(message)

    def _update_test_status(self, response_text: str) -> None:
        if not response_text:
            return

        lower = response_text.lower()
        if "assertionerror" in lower or "modulenotfounderror" in lower or "traceback" in lower:
            self._last_test_success = False
            self._last_error = response_text[-4000:]
            return

        if re.search(r"exit\s*code\s*:?\s*0", lower) or "success" in lower:
            self._last_test_success = True
            self._last_error = ""

    def _prompt_research(self) -> str:
        if self.skill_spec.research_strategy == "local_first":
            return self._prompt_research_local_first()
        if self.skill_spec.research_strategy == "hybrid":
            return self._prompt_research_hybrid()
        return self._prompt_research_context7_first()

    def _prompt_research_context7_first(self) -> str:
        return f"""
你是一个资深技术研究员。你的任务是高效地获取技术信息，并进行知识蒸馏。

技能名称: {self.skill_spec.name}
研究关键词: {self.skill_spec.keyword}
描述: {self.skill_spec.description}

执行流程：

【第一步】调用 Context 7 MCP 获取官方文档
1. 使用 mcp__context7__query-docs(keyword="{self.skill_spec.keyword}")
2. 使用 mcp__context7__resolve-library-id(keyword="{self.skill_spec.keyword}")
3. 评估返回的上下文大小（token 数）

【第二步】知识蒸馏（关键！）
若上下文 >= {self.skill_spec.min_context_tokens} tokens，执行以下蒸馏：
  a) 识别 3-5 个核心概念（简洁定义，每个 1-2 句话）
  b) 筛选 10-20 个关键 API/函数/类（列表形式）
  c) 提取 3-5 个代表性使用示例（可直接运行的代码片段）
  d) 列出 3-5 个常见错误和最佳实践

  【重要】舍弃以下内容：
  - 与 "{self.skill_spec.keyword}" 无直接关系的章节
  - 已过时的版本信息
  - 冗长的理论介绍（保留 1 段总结即可）

  最终蒸馏文档应控制在 {self.skill_spec.max_distilled_tokens} tokens 以内。

【第三步】若上下文不足，补充本地爬取
若 Context 7 返回 < {self.skill_spec.min_context_tokens} tokens，则：
  1. 使用 skill-browser-crawl 爬取官方文档
  2. 重复第二步的知识蒸馏流程

【最终输出】
整理成结构化的蒸馏笔记，包含：
- 版本信息和更新日期
- 核心概念（蒸馏后）
- 关键 API 列表
- 基本使用示例代码
- 常见错误和最佳实践
""".strip()

    def _prompt_research_local_first(self) -> str:
        references_str = "\n  ".join(self.skill_spec.references) if self.skill_spec.references else "无"
        return f"""
你是一个资深技术研究员。你的任务是深入研究技术主题，并进行知识蒸馏。

技能名称: {self.skill_spec.name}
研究关键词: {self.skill_spec.keyword}
描述: {self.skill_spec.description}
参考文档 URL:
  {references_str}

执行流程：

【第一步】使用 skill-browser-crawl Skill 爬取官方文档（必须使用 Skill，不要使用网页工具）
1. 调用 skill-browser-crawl Skill 来深度爬取参考文档 URL
   - 爬虫策略：递归爬取，深度优先
   - 关键词过滤："{self.skill_spec.keyword}"
   - 最大页面数：50-100 页
   - 排除模式：/api/changelog, /blog, /community
   - 包含模式：/docs, /guide, /tutorial, /reference
2. Skill 会将爬取的文档保存到本地 Markdown 格式
3. 等待 Skill 完成爬取

【第二步】阅读爬取的本地文档并进行知识蒸馏
1. 使用 Read 工具阅读爬取的 Markdown 文档
2. 查找与以下内容相关的部分：
   - 核心 API 和类定义
   - 使用示例和教程
   - 配置选项和参数
   - 常见问题和最佳实践
   - 版本信息和更新日志

3. 执行知识蒸馏：
   a) 识别 3-5 个核心概念（简洁定义，每个 1-2 句话）
   b) 筛选 10-20 个关键 API/函数/类（列表形式）
   c) 提取 3-5 个代表性使用示例（可直接运行的代码片段）
   d) 列出 3-5 个常见错误和最佳实践

【重要】舍弃以下内容：
  - 与 "{self.skill_spec.keyword}" 无直接关系的章节
  - 已过时的版本信息
  - 冗长的理论介绍（保留 1 段总结即可）

最终蒸馏文档应控制在 {self.skill_spec.max_distilled_tokens} tokens 以内。

【最终输出】
整理成结构化的蒸馏笔记，包含：
- 版本信息和更新日期
- 核心概念（蒸馏后）
- 关键 API 列表
- 基本使用示例代码
- 常见错误和最佳实践
- 参考文档链接
""".strip()

    def _prompt_research_hybrid(self) -> str:
        references_str = "\n  ".join(self.skill_spec.references) if self.skill_spec.references else "无"
        return f"""
你是一个资深技术研究员。你将并行获取多个信息源，并进行综合知识蒸馏。

技能名称: {self.skill_spec.name}
研究关键词: {self.skill_spec.keyword}
描述: {self.skill_spec.description}
参考文档 URL:
  {references_str}

【第一步】并行获取文档（两个来源同时进行）

来源 A：Context 7 MCP（快速查询）
  - 使用 mcp__context7__query-docs(keyword="{self.skill_spec.keyword}")
  - 使用 mcp__context7__resolve-library-id(keyword="{self.skill_spec.keyword}")
  - 评估返回的上下文大小

来源 B：本地爬取（深度研究）
  - 使用 skill-browser-crawl 爬取参考文档 URL
  - 爬取策略：深度爬虫，递归爬取相关页面
  - 关键词过滤："{self.skill_spec.keyword}"
  - 将爬取的文档保存到本地

【第二步】文档阅读与分析
1. 阅读爬取的 Markdown 文档
2. 查找与以下内容相关的部分：
   - 核心 API 和类定义
   - 使用示例和教程
   - 配置选项
   - 常见问题和最佳实践

【第三步】综合知识蒸馏
1. 合并两个来源的信息，去重
2. 识别 3-5 个核心概念（简洁定义）
3. 筛选 15-25 个关键 API/函数/类（列表形式）
4. 提取 5-10 个代表性使用示例（可直接运行的代码片段）
5. 列出 5-10 个最佳实践和常见陷阱

【重要】舍弃以下内容：
  - 与 "{self.skill_spec.keyword}" 无直接关系的章节
  - 已过时的版本信息
  - 冗长的理论介绍（保留 1 段总结即可）

最终蒸馏文档应控制在 {self.skill_spec.max_distilled_tokens} tokens 以内。

【最终输出】
整理成结构化的蒸馏笔记，包含：
- 版本信息和更新日期
- 核心概念（蒸馏后）
- 关键 API 列表
- 基本使用示例代码
- 常见错误和最佳实践
- 参考文档链接
""".strip()

    def _prompt_drafting(self) -> str:
        # 使用绝对路径而不是 ~ 路径
        skill_dir = Config.SKILLS_DIR / self.skill_spec.name
        lang = self._get_language_display_name()
        code_file = self._get_code_filename()
        deps_file = self._get_deps_filename()
        
        # 根据语言生成不同的说明
        if self.skill_spec.language == "python":
            deps_example = """
例如：
```
requests==2.31.0
numpy==1.24.0
```
"""
        else:  # JavaScript/TypeScript
            deps_example = """
例如：
```json
{
  "name": "demo",
  "version": "1.0.0",
  "dependencies": {
    "axios": "^1.6.0",
    "lodash": "^4.17.21"
  }
}
```
"""
        
        return f"""
现在基于研究结果创建演示代码（简化版）。

**目标语言**: {lang}

任务：
1. 使用 Write 工具创建 {skill_dir}/scripts/{code_file}
   - 代码长度：100-150 行（简洁）
   - 只演示核心功能，不要复杂的多个测试用例
   - 代码必须可以直接运行
   - 包含 3-5 个 assert 语句验证正确性（或等效的测试代码）

2. 使用 Write 工具创建 {skill_dir}/scripts/{deps_file}
   - 列出核心依赖及版本号
   {deps_example}

完成后直接结束，下一轮会进行代码测试和验证。
""".strip()

    def _prompt_fix(self, attempt: int, result) -> str:
        """生成修复代码的 Prompt"""
        error_info = result.stderr or result.error or "Unknown error"
        skill_dir = Config.SKILLS_DIR / self.skill_spec.name
        code_file = self._get_code_filename()
        deps_file = self._get_deps_filename()
        lang = self._get_language_display_name()
        
        return f"""
代码执行失败（第 {attempt}/{Config.MAX_RETRY_ATTEMPTS} 次尝试）。

**语言**: {lang}

错误信息：
```
{error_info[:2000]}  # 限制错误信息长度
```

请分析错误原因并修复代码：

1. 常见错误类型：
   - ModuleNotFoundError/Cannot find module: 依赖缺失或版本不对 → 检查 {deps_file}
   - ImportError: 导入错误 → 检查模块名称和版本
   - AssertionError: 逻辑错误 → 检查代码逻辑
   - SyntaxError: 语法错误 → 检查代码语法
   - TimeoutError: 执行超时 → 优化代码或检查死循环

2. 修复步骤：
   - 使用 Edit 工具修改 {skill_dir}/scripts/{code_file}
   - 或使用 Edit 工具修改 {skill_dir}/scripts/{deps_file}
   - 确保修复后的代码可以运行

3. 注意事项：
   - 保持代码简洁（100-150 行）
   - 确保依赖版本正确
   - 避免使用过时的 API

完成修复后直接结束，系统会自动重新测试。
""".strip()

    def _prompt_distill(self) -> str:
        test_status = "✅ 代码已通过验证" if self._last_test_success else "⚠️ 代码未通过验证（需人工审查）"
        skill_dir = Config.SKILLS_DIR / self.skill_spec.name
        
        return f"""
研究完成！现在为这个技能编写 SKILL.md 文档。

{test_status}

你需要：

1. 使用 Write 工具创建 {skill_dir}/SKILL.md

   文件格式应为：

   ---
   name: {self.skill_spec.name}
   description: {self.skill_spec.description}. Use this skill when you need to {self.skill_spec.keyword}.
   ---

   # {self.skill_spec.name}

   ## Overview
   基于刚才研究的核心概念，用 2-3 段落描述该技能的作用和适用场景。

   ## Prerequisites
   列出所需的 Python 版本、环境和其他依赖说明。

   ## Quick Start
   提供最简单的可运行使用示例。

   ## Key Concepts
   列出在研究中发现的关键概念、API、函数或类。

   ## Common Use Cases
   列举 2-3 个实际应用场景。

   ## Best Practices
   总结 3-5 个最佳实践和注意事项。

2. 若需要，使用 Write 工具创建其他文件：
   - {skill_dir}/references/research.md (如果有额外的研究总结)

完成后，任务就结束了。
""".strip()


    def _get_code_filename(self) -> str:
        """根据语言返回代码文件名"""
        if self.skill_spec.language == "python":
            return "demo.py"
        elif self.skill_spec.language == "typescript":
            return "demo.ts"
        else:  # javascript
            return "demo.js"

    def _get_deps_filename(self) -> str:
        """根据语言返回依赖文件名"""
        if self.skill_spec.language == "python":
            return "requirements.txt"
        else:  # javascript, typescript
            return "package.json"

    def _get_language_display_name(self) -> str:
        """返回语言的显示名称"""
        names = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
        }
        return names.get(self.skill_spec.language, self.skill_spec.language)
