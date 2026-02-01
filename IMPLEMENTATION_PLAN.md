# 🎯 SkillFactory Agent - 实现规划

**版本**：v1.0
**日期**：2026-02-01
**目标**：基于 Claude Agent SDK 的自动技能孵化系统

---

## 📁 一、项目结构设计

```
SkillFactory_agent/
├── src/
│   ├── __init__.py
│   ├── config.py              # 配置管理（优先级最高）
│   ├── models.py              # 数据结构定义
│   ├── orchestrator.py        # 主调度器（并发控制）
│   ├── worker.py              # Worker Agent（单个技能孵化）
│   ├── prompts.py             # Prompt 模板管理
│   └── utils/
│       ├── docker.py          # Docker 操作封装
│       ├── file_ops.py        # 文件操作工具
│       └── logger.py          # 日志管理
│
├── data/
│   ├── skills_todo.json       # 任务清单（输入）
│   └── results_log.json       # 执行结果（输出）
│
├── logs/
│   └── agent.log              # 运行日志
│
├── tests/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_orchestrator.py
│   └── test_worker.py
│
├── run_agent.py               # 主入口
├── pyproject.toml             # 项目配置
├── .env.example               # 环境变量示例
└── requirements.txt           # 依赖清单
```

---

## 🧩 二、核心模块职责

### 1. **config.py** - 配置管理（基础）

**职责**：
- 统一管理所有配置项
- 支持环境变量覆盖
- 提供配置验证

**关键配置**：
```python
- 并发配置: MAX_CONCURRENT_WORKERS, WORKER_TIMEOUT
- Docker 配置: DOCKER_IMAGE, DOCKER_TIMEOUT
- Claude SDK: CLAUDE_MODEL, PERMISSION_MODE
- 自定义 API: ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN
- Context 7 MCP: CONTEXT7_API_KEY, CONTEXT7_API_URL
```

### 2. **models.py** - 数据结构（基础）

**职责**：
- 定义输入输出数据结构
- 提供类型安全和序列化

**核心数据类**：
```python
- SkillSpec: 技能孵化任务规范
- SkillResult: 技能孵化结果
- WorkerState: Worker 运行状态
```

### 3. **orchestrator.py** - 主调度器（核心）

**职责**：
- 加载任务清单
- 并发调度 Worker
- 错误收集和报告
- 进度跟踪

**核心逻辑**：
```python
async def run():
    1. load_skills_todo()
    2. asyncio.gather(*workers)  # 并发
    3. collect_results()
    4. generate_report()
```

### 4. **worker.py** - Worker Agent（核心）

**职责**：
- 单个技能的完整孵化流程
- 多轮对话管理
- 自愈循环（Test → Fix → Retry）

**核心流程**：
```python
async def run():
    Round 1: Research (Context7 + skill-browser-crawl)
    Round 2: Drafting (生成 demo.py)
    Round 3-N: Test & Fix Loop (Docker 测试，最多 3 次)
    Round N+1: Distill (生成 SKILL.md)
    Round N+2: Package (打包为 .skill)
```

### 5. **prompts.py** - Prompt 模板

**职责**：
- 集中管理所有 Prompt
- 支持变量替换
- 根据策略动态生成 Prompt

**Prompt 模板**：
- Research Prompt (3 种策略)
- Drafting Prompt
- Test Prompt
- Distill Prompt

### 6. **utils/docker.py** - Docker 工具

**职责**：
- Docker 容器管理
- 超时控制
- 日志捕获

---

## 🛣️ 三、实现路径规划

### Phase 0: 前置准备（必须先完成）

| 任务 | 说明 | 依赖 |
|------|------|------|
| **环境配置** | 复制 `.env.example` → `.env`，填入真实 API Key | - |
| **Docker 测试** | 确保本地 Docker 可用 | Docker |
| **依赖安装** | `pip install claude-agent-sdk` | Python 3.10+ |
| **前置 Skill** | 实现 `skill-browser-crawl`（可选，Context 7 优先模式不需要） | Crawl4AI |

### Phase 1: 基础设施（Week 1）

#### ✅ **Step 1.1: 项目初始化**
```
优先级: 🔴 P0
耗时: 0.5 天
```

- [ ] 创建项目目录结构
- [ ] 配置 `pyproject.toml`（uv 推荐）
- [ ] 创建 `.env` 文件
- [ ] 编写 `requirements.txt`

#### ✅ **Step 1.2: 配置管理**
```
优先级: 🔴 P0
耗时: 1 天
```

- [ ] 实现 `src/config.py`
  - 支持环境变量读取
  - 配置验证逻辑
  - `Config.init()` 目录初始化
- [ ] 测试：运行时覆盖配置

#### ✅ **Step 1.3: 数据结构**
```
优先级: 🔴 P0
耗时: 1 天
```

- [ ] 实现 `src/models.py`
  - `SkillSpec` (输入)
  - `SkillResult` (输出)
  - JSON 序列化/反序列化
- [ ] 单元测试：数据类验证

### Phase 2: 核心功能（Week 2-3）

#### ✅ **Step 2.1: Worker Agent**
```
优先级: 🔴 P0
耗时: 3-4 天
```

- [ ] 实现 `src/worker.py` 基础结构
  - `__init__`: 构建 ClaudeAgentOptions
  - `run()`: 多轮对话框架
- [ ] 实现 `src/prompts.py`
  - 4 种 Prompt 模板
  - 变量替换逻辑
- [ ] **关键**: 实现 Round 1 (Research)
  - Context7 MCP 调用
  - 知识蒸馏逻辑
- [ ] 实现 Round 2 (Drafting)
  - 生成 demo.py + requirements.txt
- [ ] 实现 Round 3-N (Test & Fix)
  - Docker 测试集成
  - 重试循环（最多 3 次）
- [ ] 实现 Round N+1 (Distill & Package)
  - 生成 SKILL.md
  - 调用 package_skill.py

#### ✅ **Step 2.2: Docker 工具**
```
优先级: 🟡 P1
耗时: 1-2 天
```

- [ ] 实现 `src/utils/docker.py`
  - `run_code(code, dependencies, timeout)`
  - 超时控制（`timeout` 命令）
  - 错误日志捕获

#### ✅ **Step 2.3: Orchestrator**
```
优先级: 🔴 P0
耗时: 2-3 天
```

- [ ] 实现 `src/orchestrator.py`
  - `load_skills_todo()`
  - 并发执行（asyncio.gather）
  - 结果收集
  - 报告生成
- [ ] 错误处理
  - 异常捕获
  - 超时处理
  - 失败隔离

### Phase 3: 集成与优化（Week 4）

#### ✅ **Step 3.1: 主入口**
```
优先级: 🟡 P1
耗时: 1 天
```

- [ ] 实现 `run_agent.py`
  - 命令行参数解析
  - 初始化 Config
  - 启动 Orchestrator
- [ ] 日志配置

#### ✅ **Step 3.2: 测试与调试**
```
优先级: 🟡 P1
耗时: 2-3 天
```

- [ ] 单元测试（pytest）
- [ ] 集成测试（端到端）
- [ ] 手动测试
  - 测试 1 个技能（Context 7 优先）
  - 测试 3 个技能（并发）

#### ✅ **Step 3.3: 文档完善**
```
优先级: 🟢 P2
耗时: 1 天
```

- [ ] README.md
  - 快速开始
  - 配置说明
  - 使用示例
- [ ] API 文档

---

## 🔗 四、模块依赖关系

```
config.py (无依赖)
    ↓
models.py (依赖 config.py)
    ↓
prompts.py (依赖 models.py)
    ↓
utils/docker.py (依赖 config.py)
    ↓
worker.py (依赖 config.py, models.py, prompts.py, docker.py)
    ↓
orchestrator.py (依赖 config.py, models.py, worker.py)
    ↓
run_agent.py (依赖 orchestrator.py)
```

**实现顺序**：从上到下，逐层实现

---

## ⚠️ 五、技术难点与解决方案

### 难点 1: Claude SDK 的多轮对话管理

**问题**：如何维持会话上下文，让 Claude 记住之前的内容？

**解决方案**：
```python
async with ClaudeSDKClient(options) as client:
    # Round 1
    await client.query(prompt_1)
    async for msg in client.receive_response():
        pass  # Claude 会记住这个响应

    # Round 2 (Claude 记得上一个响应)
    await client.query(prompt_2)
    async for msg in client.receive_response():
        pass
```

### 难点 2: Docker 超时与安全

**问题**：代码可能死循环，如何防止？

**解决方案**：
```python
# 双重超时保护
# 1. asyncio.wait_for(worker, timeout=600)  # Worker 级别
# 2. timeout 300 docker run ...              # Docker 级别
```

### 难点 3: Context 7 MCP 调用

**问题**：MCP 服务器配置格式正确吗？

**解决方案**：
```python
mcp_servers={
    "context7": {
        "type": "http",
        "url": Config.CONTEXT7_API_URL,
        "headers": {"CONTEXT7_API_KEY": Config.CONTEXT7_API_KEY}
    }
}
```

### 难点 4: 并发错误隔离

**问题**：一个 Worker 失败不应该影响其他

**解决方案**：
```python
results = await asyncio.gather(*tasks, return_exceptions=True)
# 每个 Exception 会被单独捕获，不会中断整体
```

---

## 🎯 六、MVP 里程碑

### Milestone 1: 单技能孵化（第 2 周末）

**目标**：能够成功孵化 1 个技能

**验收标准**：
- ✅ 输入：`skills_todo.json` 中 1 个技能
- ✅ 流程：完整跑通 Research → Draft → Test → Distill → Package
- ✅ 输出：生成 `.skill` 文件
- ✅ 使用：Context 7 优先模式（不需要 skill-browser-crawl）

### Milestone 2: 并发多技能（第 3 周末）

**目标**：能够并发孵化 3 个技能

**验收标准**：
- ✅ 并发执行：3 个技能同时运行
- ✅ 错误隔离：1 个失败不影响其他
- ✅ 超时控制：超时自动终止
- ✅ 结果报告：生成详细报告

### Milestone 3: 生产就绪（第 4 周末）

**目标**：稳定可靠的完整系统

**验收标准**：
- ✅ 配置灵活：支持环境变量覆盖
- ✅ 日志完整：详细的运行日志
- ✅ 错误处理：优雅降级
- ✅ 文档齐全：README + API 文档

---

## 📊 七、推荐实现顺序

```
Day 1-2:  基础设施
  ├─ config.py ✅
  ├─ models.py ✅
  └─ 项目结构 ✅

Day 3-6:  Worker Agent
  ├─ prompts.py
  ├─ worker.py (核心逻辑)
  └─ utils/docker.py

Day 7-9:  Orchestrator
  ├─ orchestrator.py
  ├─ 并发控制
  └─ 错误处理

Day 10-12: 集成测试
  ├─ run_agent.py
  ├─ 单技能测试
  └─ 多技能测试

Day 13-14: 文档与优化
  ├─ README.md
  ├─ API 文档
  └─ 性能优化
```

---

## 🔑 八、关键成功因素

| 因素 | 重要性 | 建议 |
|------|--------|------|
| **配置管理** | 🔴 极高 | 优先实现，所有模块依赖它 |
| **Worker 稳定性** | 🔴 极高 | 核心逻辑，重点测试 |
| **Docker 隔离** | 🟡 高 | 确保安全性 |
| **并发控制** | 🟡 高 | 提升效率 |
| **日志完整** | 🟢 中 | 便于调试 |
| **文档齐全** | 🟢 中 | 降低维护成本 |

---

## ⚡ 九、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **SDK API 变化** | 高 | 严格按照参考文档实现，做好版本锁定 |
| **Context 7 不稳定** | 中 | 降级方案：skill-browser-crawl |
| **Docker 资源占用** | 中 | 限制并发数，添加超时 |
| **知识蒸馏不准确** | 低 | 多轮测试，优化 Prompt |

---

## 🚀 十、下一步行动

你现在可以：

1. **开始实现代码骨架** - 从 `config.py` 和 `models.py` 开始
2. **先实现 skill-browser-crawl** - 作为前置依赖
3. **测试 SDK 集成** - 验证 Claude SDK + Context 7 是否可用
4. **继续优化设计** - 还有其他细节需要调整？

---

**文档版本**：v1.0
**最后更新**：2026-02-01
