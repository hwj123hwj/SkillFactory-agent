"""Docker 沙盒执行工具 - 多语言支持版本"""

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


class MultiLangDockerRunner:
    """
    多语言 Docker 沙盒执行器
    
    支持的语言：
    - Python
    - JavaScript
    - TypeScript
    """

    # 语言配置
    LANGUAGE_CONFIG = {
        "python": {
            "image": "python:3.10-slim",
            "code_file": "demo.py",
            "deps_file": "requirements.txt",
            "install_cmd": "pip install --no-cache-dir -q -r requirements.txt",
            "run_cmd": "python demo.py",
        },
        "javascript": {
            "image": "node:20-alpine",
            "code_file": "demo.js",
            "deps_file": "package.json",
            "install_cmd": "npm install --silent",
            "run_cmd": "node demo.js",
        },
        "typescript": {
            "image": "node:20-alpine",
            "code_file": "demo.ts",
            "deps_file": "package.json",
            "install_cmd": "npm install --silent && npm install --silent ts-node typescript @types/node",
            "run_cmd": "npx ts-node demo.ts",
        },
    }

    def __init__(self):
        self.logger = logging.getLogger("skillfactory.docker")
        self.timeout = Config.DOCKER_TIMEOUT
        self.memory_limit = Config.DOCKER_MEMORY_LIMIT
        self.cpu_limit = Config.DOCKER_CPU_LIMIT
        self.registry_mirror = Config.DOCKER_REGISTRY_MIRROR

    def _get_image_with_mirror(self, image: str) -> str:
        """
        如果配置了镜像加速器，返回加速后的镜像地址
        
        例如：
        - 原始: python:3.10-slim
        - 加速: registry.cn-hangzhou.aliyuncs.com/library/python:3.10-slim
        """
        if not self.registry_mirror:
            return image
        
        # 如果镜像已经包含 registry 地址，不处理
        if "/" in image and "." in image.split("/")[0]:
            return image
        
        # 处理官方镜像（如 python:3.10-slim）
        # Docker Hub 官方镜像在 library 命名空间下
        if "/" not in image:
            # 移除协议前缀
            mirror = self.registry_mirror.replace("https://", "").replace("http://", "")
            return f"{mirror}/library/{image}"
        
        return image

    async def run_code(
        self,
        code: str,
        dependencies: str,
        work_dir: Optional[Path] = None,
        language: str = "python",
    ) -> DockerExecutionResult:
        """
        在 Docker 容器中运行代码
        
        Args:
            code: 代码内容
            dependencies: 依赖文件内容（requirements.txt 或 package.json）
            work_dir: 工作目录（可选，默认使用临时目录）
            language: 编程语言（python | javascript | typescript）
        
        Returns:
            DockerExecutionResult: 执行结果
        """
        # 验证语言支持
        if language not in self.LANGUAGE_CONFIG:
            return DockerExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="",
                error=f"Unsupported language: {language}. Supported: {list(self.LANGUAGE_CONFIG.keys())}",
            )

        config = self.LANGUAGE_CONFIG[language]

        # 创建临时目录
        if work_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="skillfactory_"))
        else:
            temp_dir = work_dir
            temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 写入文件
            code_file = temp_dir / config["code_file"]
            deps_file = temp_dir / config["deps_file"]
            code_file.write_text(code, encoding="utf-8")
            deps_file.write_text(dependencies, encoding="utf-8")

            # 获取镜像地址（可能使用加速器）
            image = self._get_image_with_mirror(config["image"])
            
            if self.registry_mirror:
                self.logger.info(f"Using Docker registry mirror: {self.registry_mirror}")
                self.logger.info(f"Original image: {config['image']}")
                self.logger.info(f"Mirrored image: {image}")
            else:
                self.logger.info(f"No registry mirror configured, using original image: {image}")

            self.logger.info(
                f"Running {language} code in Docker "
                f"(image={image}, memory={self.memory_limit}, cpu={self.cpu_limit})"
            )

            # 构建 Docker 命令
            docker_cmd = [
                "docker",
                "run",
                "--rm",  # 自动清理
                f"--memory={self.memory_limit}",  # 内存限制
                f"--cpus={self.cpu_limit}",  # CPU 限制
                "-v",
                f"{temp_dir.absolute()}:/app",  # 挂载代码目录
                "-w",
                "/app",
                image,  # 使用可能加速的镜像地址
                "sh",
                "-c",
                f"{config['install_cmd']} && {config['run_cmd']}",
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

    async def pull_image(self, language: str = "python") -> bool:
        """预拉取 Docker 镜像"""
        if language not in self.LANGUAGE_CONFIG:
            self.logger.error(f"Unsupported language: {language}")
            return False

        image = self._get_image_with_mirror(self.LANGUAGE_CONFIG[language]["image"])

        try:
            self.logger.info(f"Pulling Docker image: {image}")
            if self.registry_mirror:
                self.logger.info(f"Using registry mirror: {self.registry_mirror}")
                
            process = await asyncio.create_subprocess_exec(
                "docker",
                "pull",
                image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=300)  # 5分钟超时
            success = process.returncode == 0
            if success:
                self.logger.info(f"Docker image pulled successfully: {image}")
            else:
                self.logger.error(f"Failed to pull Docker image: {image}")
            return success
        except Exception as e:
            self.logger.error(f"Error pulling Docker image: {e}")
            return False
