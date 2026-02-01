from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .config import Config
from .models import SkillResult, SkillSpec


class SkillFactoryWorker:
    """基于 ClaudeSDKClient 的单个技能孵化 Agent"""

    def __init__(self, skill_spec: SkillSpec):
        self.skill_spec = skill_spec
        self._last_test_success: bool = False
        self._last_error: str = ""
        self.logger = logging.getLogger("skillfactory")

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
                "Read",
                "Write",
                "Edit",
                "Bash",
            ],
            permission_mode=Config.PERMISSION_MODE,
            model=Config.CLAUDE_MODEL,
            env=env_vars,
            cwd=str(Config.SKILLS_DIR),
        )

    async def run(self) -> SkillResult:
        skill_dir = Config.SKILLS_DIR / self.skill_spec.name
        skill_file = Config.SKILLS_DIR / f"{self.skill_spec.name}.skill"
        skill_dir.mkdir(parents=True, exist_ok=True)

        async with ClaudeSDKClient(options=self.client_options) as client:
            self.logger.info("Worker start: %s", self.skill_spec.name)
            await self._run_round(client, self._prompt_research())
            await self._run_round(client, self._prompt_drafting())

            for attempt in range(1, Config.MAX_RETRY_ATTEMPTS + 1):
                await self._run_round(client, self._prompt_test(attempt), check_test_status=True)
                if self._last_test_success:
                    break

            if self._last_test_success:
                await self._run_round(client, self._prompt_distill())
                status = "success"
            else:
                status = "failed"
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
            async for message in client.receive_response():
                text = self._message_to_text(message)
                if text:
                    parts.append(text)

        try:
            await asyncio.wait_for(_collect(), timeout=Config.ROUND_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger.warning(
                "Round timeout after %s seconds (%s)",
                Config.ROUND_TIMEOUT,
                self.skill_spec.name,
            )
        return "\n".join(parts)

    @staticmethod
    def _message_to_text(message: object) -> str:
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
1. 使用 mcp__context7__query-docs(keyword=\"{self.skill_spec.keyword}\")
2. 使用 mcp__context7__resolve-library-id(keyword=\"{self.skill_spec.keyword}\")
3. 评估返回的上下文大小（token 数）

【第二步】知识蒸馏（关键！）
若上下文 >= {self.skill_spec.min_context_tokens} tokens，执行以下蒸馏：
  a) 识别 3-5 个核心概念（简洁定义，每个 1-2 句话）
  b) 筛选 10-20 个关键 API/函数/类（列表形式）
  c) 提取 3-5 个代表性使用示例（可直接运行的代码片段）
  d) 列出 3-5 个常见错误和最佳实践

  【重要】舍弃以下内容：
  - 与 \"{self.skill_spec.keyword}\" 无直接关系的章节
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
        return f"""
你是一个资深技术研究员。你的任务是深入研究技术主题，并进行知识蒸馏。

技能名称: {self.skill_spec.name}
研究关键词: {self.skill_spec.keyword}
描述: {self.skill_spec.description}

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
  最终控制在 {self.skill_spec.max_distilled_tokens} tokens 以内

【第三步】可选补充
使用 Context 7 MCP 补充外部文档库的最新信息（如有）。

【最终输出】
结构化的蒸馏笔记（同 Prompt 1-A）
""".strip()

    def _prompt_research_hybrid(self) -> str:
        return f"""
你是一个资深技术研究员。你将并行获取多个信息源，并进行综合知识蒸馏。

【第一步】并行获取文档（两个来源同时进行）
来源 A：Context 7 MCP
  - mcp__context7__query-docs(keyword=\"{self.skill_spec.keyword}\")
  - mcp__context7__resolve-library-id(keyword=\"{self.skill_spec.keyword}\")

来源 B：本地爬取
  - 使用 skill-browser-crawl 爬取官方文档

【第二步】综合知识蒸馏
1. 合并两个来源的信息，去重
2. 识别 3-5 个核心概念
3. 筛选 15-25 个关键 API（允许更多内容）
4. 提取 5-10 个使用示例
5. 列出 5-10 个最佳实践和常见陷阱

最终蒸馏文档应控制在 {self.skill_spec.max_distilled_tokens} tokens 以内。

【最终输出】
综合的蒸馏笔记，融合两个信息源的优势
""".strip()

    def _prompt_drafting(self) -> str:
        return f"""
你现在有了完整的文档背景。基于刚才整理的文档，生成一个可运行的演示代码。

要求：
1. 使用 Write 工具创建 ~/.ai_skills/{self.skill_spec.name}/scripts/demo.py
   - 代码必须可以直接运行（无交互式输入）
   - 包含 assert 语句验证功能是否正确
   - 清晰的代码注释
   - 演示 {self.skill_spec.keyword} 的核心功能

2. 使用 Write 工具创建 ~/.ai_skills/{self.skill_spec.name}/scripts/requirements.txt
   - 列出所有依赖包及具体版本号
   - 使用 == 而不是 * 或 ~
""".strip()

    def _prompt_test(self, attempt: int) -> str:
        return f"""
现在测试代码的可运行性。这是第 {attempt}/{Config.MAX_RETRY_ATTEMPTS} 次尝试。

你需要：
1. 使用 Bash 工具执行以下命令（带 {Config.DOCKER_TIMEOUT} 秒超时保护）：

   timeout {Config.DOCKER_TIMEOUT} docker run --rm -v ~/.ai_skills/{self.skill_spec.name}/scripts:/app {Config.DOCKER_IMAGE} bash -c "
   cd /app && \
   pip install -q -r requirements.txt && \
   python demo.py
   "

2. 检查返回的输出：
   - 若包含 "AssertionError": 说明逻辑错误，需要修复
   - 若包含 "ModuleNotFoundError": 说明依赖缺失或版本不对，需要修复
   - 若包含 "Timeout": 说明代码执行超时，需要优化或检查逻辑
   - 若包含其他错误: 根据具体情况修复

3. 若失败，分析原因：
   - 使用 Edit 工具修改 demo.py 或 requirements.txt
   - 重新执行 docker run 命令
   - 最多重试 {Config.MAX_RETRY_ATTEMPTS} 次

   第 {Config.MAX_RETRY_ATTEMPTS + 1} 次失败则停止，记录为"待人工审查"

4. 若成功（返回 0，无异常），进入下一轮
""".strip()

    def _prompt_distill(self) -> str:
        return f"""
代码已验证可运行！现在为这个技能编写完整的文档并打包。

你需要：

1. 使用 Write 工具创建 ~/.ai_skills/{self.skill_spec.name}/SKILL.md

   格式参考 (来自 .agents/skills/skill-creator/SKILL.md):
   ---
   name: {self.skill_spec.name}
   description: {self.skill_spec.description}. Use this skill when you need to {self.skill_spec.keyword}.
   ---

   # {self.skill_spec.name}

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
   - ~/.ai_skills/{self.skill_spec.name}/references/api_docs.md
   - ~/.ai_skills/{self.skill_spec.name}/assets/example.json 等

3. 完成后，使用 Bash 工具执行打包命令：

   python ~/.agents/skills/skill-creator/scripts/package_skill.py ~/.ai_skills/{self.skill_spec.name}

   这会生成 ~/.ai_skills/{self.skill_spec.name}.skill 文件
""".strip()
