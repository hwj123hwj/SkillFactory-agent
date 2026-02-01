from __future__ import annotations

import argparse
import asyncio

from .config import Config
from .orchestrator import SkillFactoryOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="SkillFactory Agent CLI")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help="最大并发 Worker 数量（覆盖配置）",
    )
    args = parser.parse_args()

    Config.init()
    orchestrator = SkillFactoryOrchestrator(max_concurrent=args.max_concurrent)
    asyncio.run(orchestrator.run())


if __name__ == "__main__":
    main()
