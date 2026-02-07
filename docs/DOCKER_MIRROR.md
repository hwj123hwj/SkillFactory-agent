# 🐳 Docker 镜像加速配置指南

在中国大陆使用 Docker 时，由于网络原因，拉取镜像可能会很慢或失败。本指南介绍如何配置镜像加速器。

## 快速配置

### 方法 1：应用级配置（推荐）

在 `.env` 文件中配置镜像加速器：

```bash
# .env 文件
# 推荐使用 1Panel 镜像（免费，无需注册，速度快）
DOCKER_REGISTRY_MIRROR=https://docker.1panel.live

# 或使用轩辕镜像
# DOCKER_REGISTRY_MIRROR=https://docker.xuanyuan.me
```

**优点**：
- ✅ 只影响本项目
- ✅ 无需 root 权限
- ✅ 配置简单

### 方法 2：系统级配置（更彻底）

配置 Docker daemon（需要 root 权限）：

```bash
# 编辑 Docker 配置文件
sudo nano /etc/docker/daemon.json
```

添加以下内容：

```json
{
  "registry-mirrors": [
    "https://docker.1panel.live",
    "https://docker.xuanyuan.me",
    "https://docker.chenby.cn"
  ]
}
```

重启 Docker：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

**优点**：
- ✅ 影响所有 Docker 操作
- ✅ 无需在每个项目中配置

## 可用的镜像加速器

### 1. 轩辕镜像（推荐，免费）

```bash
DOCKER_REGISTRY_MIRROR=https://docker.xuanyuan.me
```

**特点**：
- ✅ 完全免费
- ✅ 无需注册
- ✅ 社区维护，使用广泛
- ✅ 提供技术支持（官方QQ群：1072982923）
- ✅ 速度快，稳定性好
- ⚠️ 可能有速率限制

**官方网站**：https://xuanyuan.cloud

**说明**：轩辕镜像是一个面向开发者和科研用户的免费 Docker 镜像加速服务，所有镜像均来源于原始仓库，不存储、不修改、不传播任何镜像内容。

### 2. Docker 代理镜像（推荐，免费）

```bash
# 1Panel 镜像
DOCKER_REGISTRY_MIRROR=https://docker.1panel.live

# Docker 陈镜像
DOCKER_REGISTRY_MIRROR=https://docker.chenby.cn

# Docker Anyhub
DOCKER_REGISTRY_MIRROR=https://docker.anyhub.us.kg

# Dockerhub ICU
DOCKER_REGISTRY_MIRROR=https://dockerhub.icu

# Docker AWS
DOCKER_REGISTRY_MIRROR=https://docker.aws19527.cn
```

**特点**：
- ✅ 完全免费
- ✅ 无需注册
- ✅ 多个备选地址
- ⚠️ 稳定性未知

### 3. 网易云（公共）

```bash
DOCKER_REGISTRY_MIRROR=https://hub-mirror.c.163.com
```

**特点**：
- ✅ 免费公共服务
- ✅ 无需注册
- ✅ 速度较快
- ⚠️ 可能不稳定（2026年初已失效）

### 4. 阿里云（推荐，需注册）

```bash
DOCKER_REGISTRY_MIRROR=https://your-id.mirror.aliyuncs.com
```

**获取方法**：
1. 访问 https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors
2. 登录阿里云账号
3. 获取专属加速地址（格式：`https://xxxxx.mirror.aliyuncs.com`）

**特点**：
- ✅ 速度快
- ✅ 稳定性好
- ✅ 专属地址
- ⚠️ 需要注册

### 3. 阿里云（推荐，需注册）

```bash
DOCKER_REGISTRY_MIRROR=https://your-id.mirror.aliyuncs.com
```

**获取方法**：
1. 访问 https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors
2. 登录阿里云账号
3. 获取专属加速地址（格式：`https://xxxxx.mirror.aliyuncs.com`）

**特点**：
- ✅ 速度快
- ✅ 稳定性好
- ✅ 专属地址
- ⚠️ 需要注册

### 4. 腾讯云（公共）

```bash
DOCKER_REGISTRY_MIRROR=https://mirror.ccs.tencentyun.com
```

**特点**：
- ✅ 免费公共服务
- ✅ 无需注册
- ⚠️ 可能限流

### 4. 腾讯云（公共）

```bash
DOCKER_REGISTRY_MIRROR=https://mirror.ccs.tencentyun.com
```

**特点**：
- ✅ 免费公共服务
- ✅ 无需注册
- ⚠️ 可能限流

### 5. Docker 中国（已停止服务）

```bash
# ❌ 已停止服务，不推荐使用
DOCKER_REGISTRY_MIRROR=https://registry.docker-cn.com
```

### 5. 轩辕镜像（免费，推荐）

```bash
DOCKER_REGISTRY_MIRROR=https://docker.xuanyuan.me
```

**特点**：
- ✅ 免费公共服务
- ✅ 无需注册
- ✅ 社区维护，使用广泛
- ✅ 提供技术支持（QQ群：1072982923）

**官方网站**：https://xuanyuan.cloud

### 6. 中科大（教育网）

```bash
DOCKER_REGISTRY_MIRROR=https://docker.mirrors.ustc.edu.cn
```

**特点**：
- ✅ 教育网速度快
- ⚠️ 公网可能较慢

## 配置步骤

### 步骤 1：选择镜像加速器

根据你的网络环境选择：
- **个人用户**：推荐 1Panel 镜像、轩辕镜像或阿里云
- **企业用户**：推荐阿里云（专属地址）
- **教育网**：推荐中科大

### 步骤 2：配置 .env 文件

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

添加或修改：

```bash
# Docker 镜像加速器（推荐使用 1Panel 镜像）
DOCKER_REGISTRY_MIRROR=https://docker.1panel.live
```

### 步骤 3：验证配置

运行测试：

```bash
uv run python run_agent.py
```

查看日志，应该看到：

```
Using Docker registry mirror: https://docker.1panel.live
Running javascript code in Docker (image=docker.1panel.live/library/node:20-alpine, ...)
```

## 工作原理

### 应用级配置

当配置了 `DOCKER_REGISTRY_MIRROR` 后，系统会自动转换镜像地址：

**原始镜像**：
```
python:3.10-slim
node:20-alpine
```

**转换后**（使用 1Panel 镜像加速）：
```
docker.1panel.live/library/python:3.10-slim
docker.1panel.live/library/node:20-alpine
```

### 镜像地址格式

Docker Hub 官方镜像的完整地址格式：

```
[registry]/[namespace]/[image]:[tag]

例如：
- 官方: docker.io/library/python:3.10-slim
- 1Panel: docker.1panel.live/library/python:3.10-slim
- 轩辕: docker.xuanyuan.me/library/python:3.10-slim
- 阿里: xxxxx.mirror.aliyuncs.com/library/python:3.10-slim
```

## 故障排除

### 问题 1：镜像加速器不生效

**症状**：
```
Error response from daemon: Get "https://registry-1.docker.io/v2/": net/http: request canceled
```

**解决方案**：
1. 检查 `.env` 文件中的配置是否正确
2. 尝试更换其他镜像加速器
3. 检查网络连接

### 问题 2：镜像拉取仍然很慢

**症状**：
```
Pulling Docker image: docker.1panel.live/library/node:20-alpine
... (长时间无响应)
```

**解决方案**：
1. 更换为阿里云专属加速器
2. 使用系统级配置（方法 2）
3. 检查防火墙设置

### 问题 3：镜像地址格式错误

**症状**：
```
Error response from daemon: pull access denied for hub-mirror.c.163.com/node
```

**解决方案**：
确保镜像地址格式正确，官方镜像需要 `/library/` 前缀：
```bash
# ❌ 错误
hub-mirror.c.163.com/node:20-alpine

# ✅ 正确
hub-mirror.c.163.com/library/node:20-alpine
```

## 性能对比

### 不使用加速器

```
拉取 node:20-alpine (180MB)
- 国外服务器: ~30秒
- 国内服务器: 超时或失败
```

### 使用 1Panel 镜像

```
拉取 node:20-alpine (180MB)
- 国内服务器: ~20-30秒
- 成功率: ~99%
```

### 使用轩辕镜像

```
拉取 node:20-alpine (180MB)
- 国内服务器: ~30-40秒
- 成功率: ~95%
```

### 使用网易云加速器

```
拉取 node:20-alpine (180MB)
- 国内服务器: ~40-60秒
- 成功率: ~90%
```

### 使用阿里云专属加速器

```
拉取 node:20-alpine (180MB)
- 国内服务器: ~20-30秒
- 成功率: ~99%
```

## 推荐配置

### 个人开发者

```bash
# .env 文件
# 推荐使用 1Panel 镜像（免费，速度快）
DOCKER_REGISTRY_MIRROR=https://docker.1panel.live

# 或使用轩辕镜像（免费，有技术支持）
# DOCKER_REGISTRY_MIRROR=https://docker.xuanyuan.me
```

### 团队/企业

1. 注册阿里云账号
2. 获取专属加速地址
3. 配置到 `.env`：

```bash
# .env 文件
DOCKER_REGISTRY_MIRROR=https://xxxxx.mirror.aliyuncs.com
```

### 生产环境

使用系统级配置（`/etc/docker/daemon.json`）：

```json
{
  "registry-mirrors": [
    "https://xxxxx.mirror.aliyuncs.com",
    "https://docker.1panel.live",
    "https://docker.xuanyuan.me"
  ]
}
```

## 相关链接

- [1Panel 官网](https://1panel.cn/)
- [轩辕镜像官网](https://xuanyuan.cloud)
- [阿里云镜像加速器](https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors)
- [Docker 官方文档](https://docs.docker.com/registry/recipes/mirror/)

---

**版本**: v2.3  
**最后更新**: 2026-02-07
