# SkillFactory Agent

🤖 自动化 AI 技能孵化器 - 基于 Claude Agent SDK

自动将技术关键词转化为可运行的 Claude Skills，包括文档研究、代码生成和知识蒸馏。

## ✨ 核心特性

- ✅ **自动文档爬取**：使用 skill-browser-crawl 深度爬取官方文档
- ✅ **智能知识蒸馏**：从海量文档中提取核心概念和最佳实践
- ✅ **代码自动生成**：生成可运行的演示代码和依赖清单
- ✅ **多语言支持**：支持 Python、JavaScript、TypeScript
- ✅ **多策略研究**：支持 Context7 优先、本地优先、混合策略
- ✅ **并发任务处理**：支持串行/并行孵化多个技能
- ✅ **Docker 沙盒验证**：自动在容器中运行代码并验证

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，填入真实的 API Key
# - CLAUDE_API_KEY: Claude API 密钥（必需）
# - CONTEXT7_API_KEY: Context7 MCP 密钥（可选）
# - MAX_CONCURRENT_WORKERS: 并发数（见下方说明）
```

### 3. 配置任务

编辑 `data/skills_todo.json`：

```json
{
  "skills": [
    {
      "name": "skill-llamaindex-entity-extraction",
      "keyword": "LlamaIndex structured entity extraction",
      "description": "Extract structured entities using LlamaIndex",
      "research_strategy": "local_first",
      "references": ["https://docs.llamaindex.org.cn/en/stable/"]
    }
  ]
}
```

### 4. 运行孵化器

```bash
uv run python run_agent.py
```

### 5. 查看结果

生成的 Skill 保存在 `~/.ai_skills/` 目录：

```
~/.ai_skills/
├── skill-llamaindex-entity-extraction/
│   ├── SKILL.md                    # 技能文档
│   ├── scripts/
│   │   ├── demo.py                 # 演示代码
│   │   └── requirements.txt        # 依赖清单
│   └── references/
│       └── research.md             # 研究总结
└── ...
```

## ⚙️ 配置说明

### 并发配置（重要！）

`MAX_CONCURRENT_WORKERS` 控制**同时孵化的技能数量**：

| 服务器配置 | 推荐并发数 | 说明 |
|-----------|-----------|------|
| **4C4G** | `1` | 串行执行，内存占用低（推荐） |
| **8C8G+** | `2-3` | 并行执行，提升效率 |

**为什么 4C4G 推荐设置为 1？**
- Claude Code Agent 本身占用 1-2GB 内存
- skill-browser-crawl 爬取文档时占用 500MB-1GB
- Docker 容器运行代码占用 500-800MB
- 并发数过高会导致 OOM（内存不足）

**串行 vs 并行**：

```bash
# 串行模式（并发=1）- 4C4G 服务器推荐
MAX_CONCURRENT_WORKERS=1
# Task 1 → Task 2 → Task 3（依次执行）

# 并行模式（并发=2-3）- 8C8G+ 服务器
MAX_CONCURRENT_WORKERS=2
# Task 1 ┐
# Task 2 ┴ 同时执行
```

### 研究策略

支持三种研究策略（在 `skills_todo.json` 中配置）：

1. **context7_first**（Context7 优先）
   - 先使用 Context7 MCP 快速查询
   - 若信息不足，补充 skill-browser-crawl
   - 适合：主流框架，成本低

2. **local_first**（本地爬取优先）✅ 推荐
   - 使用 skill-browser-crawl 深度爬取
   - 可选：使用 Context7 MCP 补充
   - 适合：冷门库或需要最新版本

3. **hybrid**（混合策略）
   - 并行使用两种方式
   - 综合两个来源的信息
   - 适合：关键技能，最全面

## 📊 工作流程

```
1. Input: 从 skills_todo.json 加载任务
   ↓
2. Research: Worker 调用 skill-browser-crawl 爬取文档
   ↓
3. Drafting: Worker 生成 demo.py + requirements.txt
   ↓
4. Distilling: Worker 生成 SKILL.md 文档
   ↓
5. Output: 保存到 ~/.ai_skills/
```

## 🛠️ 技术栈

- **Python 3.10+**
- **Claude Agent SDK** - AI Agent 框架
- **Context7 MCP** - 文档查询服务（可选）
- **skill-browser-crawl** - 网页爬取 Skill
- **asyncio** - 并发管理
- **uv** - Python 包管理器

## 📝 日志和结果

- **执行日志**: `logs/agent.log`
- **结果报告**: `data/results_log.json`
- **生成的 Skills**: `~/.ai_skills/`

## 🐛 故障排除

### 内存不足（OOM）

**症状**：进程被 killed，日志显示 "Killed"

**解决方案**：
```bash
# 降低并发数
MAX_CONCURRENT_WORKERS=1

# 或增加服务器内存
```

### Docker 不可用

**症状**：日志显示 "Docker not ready"

**解决方案**：
```bash
# 检查 Docker 是否安装
docker version

# 启动 Docker 服务
sudo systemctl start docker
```

### Docker 镜像拉取失败（中国大陆）

**症状**：
```
Error response from daemon: Get "https://registry-1.docker.io/v2/": net/http: request canceled
```

**解决方案**：配置 Docker 镜像加速器

```bash
# 编辑 .env 文件，推荐使用 1Panel 镜像（免费，无需注册，速度快）
DOCKER_REGISTRY_MIRROR=https://docker.1panel.live

# 或使用其他镜像加速器
# DOCKER_REGISTRY_MIRROR=https://docker.xuanyuan.me
# DOCKER_REGISTRY_MIRROR=https://docker.chenby.cn
```

详细配置请查看 [Docker 镜像加速指南](docs/DOCKER_MIRROR.md)

### Skill 未加载

**症状**：日志显示 "skill-browser-crawl not found"

**解决方案**：
```bash
# 检查 Skill 目录
ls .claude/skills/skill-browser-crawl/

# 确保 SKILL.md 有正确的 YAML frontmatter
cat .claude/skills/skill-browser-crawl/SKILL.md
```

## 📚 文档

完整文档请查看 [docs/](docs/) 目录：

- **[快速开始](docs/QUICKSTART.md)** - 5 分钟快速上手 ⭐ 推荐新手
- **[多语言支持](docs/MULTILANG_SUPPORT.md)** - Python/JavaScript/TypeScript 支持 🌐 新功能
- **[Docker 镜像加速](docs/DOCKER_MIRROR.md)** - 解决镜像拉取慢的问题 🚀 中国大陆必看
- **[项目结构](docs/PROJECT_STRUCTURE.md)** - 项目结构说明
- **[产品需求文档](docs/PRD.md)** - 当前实现状态
- **[Agent SDK 参考](docs/Agent%20SDK%20参考%20-%20Python.md)** - Claude Agent SDK 参考
- **[文档索引](docs/DOCS.md)** - 完整文档导航

> 💡 **提示**：第一次使用？从 [快速开始指南](docs/QUICKSTART.md) 开始！  
> 🇨🇳 **中国大陆用户**：请先配置 [Docker 镜像加速](docs/DOCKER_MIRROR.md)

## ⚡ 性能优化建议

### 4C4G 服务器推荐配置

```bash
# .env 文件
MAX_CONCURRENT_WORKERS=1        # 串行执行
WORKER_TIMEOUT=900              # 15分钟
DOCKER_IMAGE=python:3.10-slim   # 平衡性能和兼容性
DOCKER_MEMORY_LIMIT=800m        # 限制容器内存
DOCKER_CPU_LIMIT=1.0            # 限制容器 CPU
LOG_LEVEL=INFO                  # 生产环境日志级别
```

### 研究策略选择

- **context7_first**（推荐）：快速、成本低，适合主流库
- **local_first**：详尽全面，适合冷门库或需要最新版本
- **hybrid**：最全面，适合关键技能

### 性能监控

```bash
# 监控内存使用
watch -n 1 free -h

# 查看日志
tail -f logs/agent.log

# 查看 Docker 资源
docker stats
```

## 📄 许可证

MIT License

---

**版本**: v2.1  
**最后更新**: 2026-02-07
