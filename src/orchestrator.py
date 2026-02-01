from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import Config
from .models import SkillResult, SkillSpec
from .worker import SkillFactoryWorker


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("skillfactory")
    if logger.handlers:
        return logger

    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    log_file = Config.LOGS_DIR / "agent.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    return logger


def load_skills_todo() -> list[SkillSpec]:
    data_file = Config.DATA_DIR / "skills_todo.json"
    if not data_file.exists():
        return []

    with data_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    skills = data.get("skills", [])
    return [SkillSpec.from_dict(item) for item in skills]


def _write_results(results: list[SkillResult]) -> None:
    results_file = Config.DATA_DIR / "results_log.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": [r.to_dict() for r in results],
    }
    with results_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _log_docker_status(logger: logging.Logger) -> None:
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            version = result.stdout.strip() or "unknown"
            logger.info("Docker detected: %s", version)
        else:
            stderr = result.stderr.strip() or "unknown error"
            logger.warning("Docker not ready (exit=%s): %s", result.returncode, stderr)
    except FileNotFoundError:
        logger.warning("Docker CLI not found in PATH")


class SkillFactoryOrchestrator:
    """主调度器，支持并发执行技能孵化任务"""

    def __init__(self, max_concurrent: Optional[int] = None):
        self.max_concurrent = max_concurrent or Config.MAX_CONCURRENT_WORKERS
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.results: List[SkillResult] = []
        self.logger = _setup_logger()

    async def run(self) -> None:
        Config.init()
        self.logger.info("SkillFactory Agent starting...")
        if not Config.ANTHROPIC_AUTH_TOKEN and not Config.CLAUDE_API_KEY:
            self.logger.warning(
                "未检测到 Claude API Key（CLAUDE_API_KEY/ANTHROPIC_AUTH_TOKEN），Worker 可能无法连接。"
            )
        if not Config.CONTEXT7_API_KEY:
            self.logger.warning("未检测到 Context7 API Key（CONTEXT7_API_KEY）。")
        _log_docker_status(self.logger)
        todos = load_skills_todo()
        if not todos:
            self.logger.warning("skills_todo.json 为空或不存在，未执行任何任务")
            return
        self.logger.info("待执行技能数量: %s", len(todos))

        tasks = [
            self.spawn_worker_with_timeout(skill, timeout=Config.WORKER_TIMEOUT)
            for skill in todos
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for skill_spec, result in zip(todos, results):
            if isinstance(result, Exception):
                self.log_error(skill_spec, result)
            elif isinstance(result, SkillResult):
                self.save_result(result)

        self.generate_summary_report()
        _write_results(self.results)

    async def spawn_worker_with_timeout(self, skill_spec: SkillSpec, timeout: int):
        async with self.semaphore:
            try:
                return await asyncio.wait_for(self._run_single_worker(skill_spec), timeout=timeout)
            except asyncio.TimeoutError:
                return SkillResult(
                    skill_name=skill_spec.name,
                    status="timeout",
                    skill_dir=str(Config.SKILLS_DIR / skill_spec.name),
                    skill_file=str(Config.SKILLS_DIR / f"{skill_spec.name}.skill"),
                    error_log=f"超过 {timeout} 秒",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as exc:  # pragma: no cover - 防守性处理
                return SkillResult(
                    skill_name=skill_spec.name,
                    status="failed",
                    skill_dir=str(Config.SKILLS_DIR / skill_spec.name),
                    skill_file=str(Config.SKILLS_DIR / f"{skill_spec.name}.skill"),
                    error_log=str(exc),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )

    async def _run_single_worker(self, skill_spec: SkillSpec) -> SkillResult:
        worker = SkillFactoryWorker(skill_spec)
        return await worker.run()

    def save_result(self, result: SkillResult) -> None:
        self.results.append(result)
        self.logger.info("技能完成: %s (%s)", result.skill_name, result.status)

    def log_error(self, skill_spec: SkillSpec, error: Exception) -> None:
        self.logger.error("技能失败: %s, error=%s", skill_spec.name, error)
        self.results.append(
            SkillResult(
                skill_name=skill_spec.name,
                status="failed",
                skill_dir=str(Config.SKILLS_DIR / skill_spec.name),
                skill_file=str(Config.SKILLS_DIR / f"{skill_spec.name}.skill"),
                error_log=str(error),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    def generate_summary_report(self) -> None:
        success = sum(1 for r in self.results if r.status == "success")
        failed = sum(1 for r in self.results if r.status == "failed")
        timeout = sum(1 for r in self.results if r.status == "timeout")
        partial = sum(1 for r in self.results if r.status == "partial_success")

        self.logger.info(
            "Summary: success=%s | partial=%s | failed=%s | timeout=%s",
            success,
            partial,
            failed,
            timeout,
        )


if __name__ == "__main__":
    orchestrator = SkillFactoryOrchestrator()
    asyncio.run(orchestrator.run())
