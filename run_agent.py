#!/usr/bin/env python3
"""
SkillFactory Agent - 启动脚本

使用方式：
  uv run python -m src.orchestrator
  
或直接调用：
  uv run python src/orchestrator.py
"""

if __name__ == "__main__":
    import sys
    import asyncio
    from pathlib import Path

    # 添加项目根目录到 Python 路径
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    from src.orchestrator import SkillFactoryOrchestrator
    from src.config import Config

    # 初始化配置
    Config.init()

    # 运行 Orchestrator
    orchestrator = SkillFactoryOrchestrator()
    asyncio.run(orchestrator.run())
