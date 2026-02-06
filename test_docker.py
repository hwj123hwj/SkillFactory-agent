"""测试 Docker 沙盒功能"""

import asyncio
from src.utils.docker import DockerRunner


async def test_simple_code():
    """测试简单的 Python 代码"""
    print("=" * 60)
    print("Test 1: Simple Python code")
    print("=" * 60)
    
    runner = DockerRunner()
    
    # 检查 Docker 是否可用
    available = await runner.check_docker_available()
    print(f"Docker available: {available}")
    
    if not available:
        print("Docker not available, skipping test")
        return
    
    # 测试代码
    code = """
print("Hello from Docker!")
print("Python version:", __import__('sys').version)

# 简单的计算
result = 2 + 2
assert result == 4, f"Expected 4, got {result}"
print(f"Test passed: 2 + 2 = {result}")
"""
    
    requirements = """
# No dependencies needed for this test
"""
    
    result = await runner.run_code(code, requirements)
    
    print(f"\nResult: {result}")
    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"\nStdout:\n{result.stdout}")
    if result.stderr:
        print(f"\nStderr:\n{result.stderr}")


async def test_with_dependencies():
    """测试带依赖的代码"""
    print("\n" + "=" * 60)
    print("Test 2: Code with dependencies")
    print("=" * 60)
    
    runner = DockerRunner()
    
    code = """
import requests

print("Testing requests library...")
response = requests.get("https://httpbin.org/get", timeout=5)
assert response.status_code == 200, f"Expected 200, got {response.status_code}"
print(f"Test passed: HTTP GET returned {response.status_code}")
"""
    
    requirements = """
requests==2.31.0
"""
    
    result = await runner.run_code(code, requirements)
    
    print(f"\nResult: {result}")
    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"\nStdout:\n{result.stdout}")
    if result.stderr:
        print(f"\nStderr:\n{result.stderr}")


async def test_failing_code():
    """测试失败的代码"""
    print("\n" + "=" * 60)
    print("Test 3: Failing code (expected to fail)")
    print("=" * 60)
    
    runner = DockerRunner()
    
    code = """
print("This will fail...")
assert False, "Intentional failure for testing"
"""
    
    requirements = """
# No dependencies
"""
    
    result = await runner.run_code(code, requirements)
    
    print(f"\nResult: {result}")
    print(f"Success: {result.success}")
    print(f"Exit code: {result.exit_code}")
    print(f"\nStdout:\n{result.stdout}")
    if result.stderr:
        print(f"\nStderr:\n{result.stderr}")


async def main():
    """运行所有测试"""
    print("Testing Docker Runner...")
    print()
    
    await test_simple_code()
    # await test_with_dependencies()  # 需要网络访问，可能失败
    await test_failing_code()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
