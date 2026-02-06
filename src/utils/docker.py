"""Docker 沙盒执行工具 - 针对 4C4G 服务器优化"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

from ..config import Config


class DockerExecutionResult:
    """Docker 执行结果"""

    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        timeout: bool = False,
        error: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timeout = timeout
        self.error = error

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timeout and not self.error

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"DockerExecutionResult(status={status}, exit_code={self.exit_code})"


class DockerRunner:
    """
    Docker 沙盒执行器
    
    针对 4C4G 服务器优化：
    - 使用 alpine 镜像（更轻量）
    - 限制内存和 CPU 使用
    - 自动清理容器
    """

    def __init__(self):
        self.logger = logging.getLogger("skillfactory.docker")
        self.image = Config.DOCKER_IMAGE
        self.timeout = Config.DOCKER_TIMEOUT
        self.memory_limit = Config.DOCKER_MEMORY_LIMIT
        self.cpu_limit = Config.DOCKER_CPU_LIMIT

    async def run_code(
        self,
        code: str,
        requirements: str,
        work_dir: Optional[Path] = None,
    ) -> DockerExecutionResult:
        """
        在 Docker 容器中运行 Python 代码
        
        Args:
            code: Python 代码内容
            requirements: requirements.txt 内容
            work_dir: 工作目录（可选，默认使用临时目录）
        
        Returns:
            DockerExecutionResult: 执行结果
        """
        # 创建临时目录
        if work_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="skillfactory_"))
        else:
            temp_dir = work_dir
            temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 写入文件
            code_file = temp_dir / "demo.py"
            req_file = temp_dir / "requirements.txt"
            code_file.write_text(code, encoding="utf-8")
            req_file.write_text(requirements, encoding="utf-8")

            self.logger.info(f"Running code in Docker (image={self.image}, memory={self.memory_limit}, cpu={self.cpu_limit})")

            # 构建 Docker 命令
            # 注意：alpine 镜像需要先安装 gcc 等编译工具（如果依赖需要编译）
            docker_cmd = [
                "docker",
                "run",
                "--rm",  # 自动清理
                f"--memory={self.memory_limit}",  # 内存限制
                f"--cpus={self.cpu_limit}",  # CPU 限制
                # 注意：允许网络访问以便安装依赖
                # 如果需要更严格的安全控制，可以使用 --network=bridge 并配置防火墙
                "-v",
                f"{temp_dir.absolute()}:/app",  # 挂载代码目录
                "-w",
                "/app",
                self.image,
                "sh",
                "-c",
                # alpine 镜像的安装命令
                "pip install --no-cache-dir -q -r requirements.txt && python demo.py",
            ]

            # 执行 Docker 命令（带超时）
            try:
                process = await asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )

                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = process.returncode or 0

                self.logger.info(f"Docker execution completed (exit_code={exit_code})")

                return DockerExecutionResult(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=False,
                )

            except asyncio.TimeoutError:
                self.logger.warning(f"Docker execution timeout after {self.timeout}s")
                # 尝试杀死进程
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass

                return DockerExecutionResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution timeout after {self.timeout} seconds",
                    timeout=True,
                )

        except Exception as e:
            self.logger.error(f"Docker execution error: {e}")
            return DockerExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="",
                error=str(e),
            )

        finally:
            # 清理临时目录（如果是自动创建的）
            if work_dir is None:
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    async def check_docker_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=5)
            return process.returncode == 0
        except Exception:
            return False

    async def pull_image(self) -> bool:
        """预拉取 Docker 镜像"""
        try:
            self.logger.info(f"Pulling Docker image: {self.image}")
            process = await asyncio.create_subprocess_exec(
                "docker",
                "pull",
                self.image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=300)  # 5分钟超时
            success = process.returncode == 0
            if success:
                self.logger.info(f"Docker image pulled successfully: {self.image}")
            else:
                self.logger.error(f"Failed to pull Docker image: {self.image}")
            return success
        except Exception as e:
            self.logger.error(f"Error pulling Docker image: {e}")
            return False
