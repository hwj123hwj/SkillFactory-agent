from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


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
    ROUND_TIMEOUT = int(os.getenv("ROUND_TIMEOUT", "1200"))  # 20分钟

    # ===== 存储路径 =====
    ROOT_DIR = Path(__file__).resolve().parent.parent
    SKILLS_DIR = Path.home() / ".ai_skills"
    DATA_DIR = ROOT_DIR / "data"
    LOGS_DIR = ROOT_DIR / "logs"

    # ===== Claude SDK 配置 =====
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet")
    PERMISSION_MODE = os.getenv("PERMISSION_MODE", "bypassPermissions")

    # 自定义 API 配置（用于使用其他厂商的兼容 API）
    ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
    ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

    # ===== Context 7 MCP =====
    CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY", "")
    CONTEXT7_API_URL = os.getenv("CONTEXT7_API_URL", "https://mcp.context7.com/mcp")

    # ===== 日志配置 =====
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def init(cls) -> None:
        """初始化所有目录"""
        load_dotenv(dotenv_path=cls.ROOT_DIR / ".env", override=False)
        cls._reload_from_env()
        cls.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # 允许使用 CLAUDE_API_KEY 作为兼容变量
        if not cls.ANTHROPIC_AUTH_TOKEN and cls.CLAUDE_API_KEY:
            cls.ANTHROPIC_AUTH_TOKEN = cls.CLAUDE_API_KEY

    @classmethod
    def _reload_from_env(cls) -> None:
        cls.MAX_CONCURRENT_WORKERS = int(os.getenv("MAX_CONCURRENT_WORKERS", "3"))
        cls.WORKER_TIMEOUT = int(os.getenv("WORKER_TIMEOUT", "600"))
        cls.DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "python:3.10-slim")
        cls.DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "300"))
        cls.MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
        cls.ROUND_TIMEOUT = int(os.getenv("ROUND_TIMEOUT", "1200"))
        cls.CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet")
        cls.PERMISSION_MODE = os.getenv("PERMISSION_MODE", "bypassPermissions")
        cls.ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
        cls.ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
        cls.CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
        cls.CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY", "")
        cls.CONTEXT7_API_URL = os.getenv("CONTEXT7_API_URL", "https://mcp.context7.com/mcp")
        cls.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
