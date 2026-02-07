# 🌐 多语言支持

SkillFactory Agent 现在支持多种编程语言的技能孵化！

## 支持的语言

| 语言 | 代码文件 | 依赖文件 | Docker 镜像 | 状态 |
|------|---------|---------|------------|------|
| **Python** | `demo.py` | `requirements.txt` | `python:3.10-slim` | ✅ 完全支持 |
| **JavaScript** | `demo.js` | `package.json` | `node:20-alpine` | ✅ 完全支持 |
| **TypeScript** | `demo.ts` | `package.json` | `node:20-alpine` | ✅ 完全支持 |

## 使用方法

### 1. 在任务配置中指定语言

编辑 `data/skills_todo.json`，添加 `language` 字段：

```json
{
  "skills": [
    {
      "name": "skill-python-requests",
      "keyword": "Python requests library",
      "description": "HTTP client for Python",
      "language": "python",
      "research_strategy": "context7_first"
    },
    {
      "name": "skill-js-axios",
      "keyword": "JavaScript axios library",
      "description": "HTTP client for JavaScript",
      "language": "javascript",
      "research_strategy": "context7_first"
    },
    {
      "name": "skill-ts-fetch",
      "keyword": "TypeScript fetch API",
      "description": "Typed fetch API for TypeScript",
      "language": "typescript",
      "research_strategy": "context7_first"
    }
  ]
}
```

### 2. 运行孵化器

```bash
uv run python run_agent.py
```

系统会自动：
1. 根据语言选择合适的 Docker 镜像
2. 生成对应语言的代码文件
3. 使用对应的包管理器安装依赖
4. 运行并验证代码

## 语言特性

### Python

**生成的文件**：
- `demo.py` - Python 代码
- `requirements.txt` - pip 依赖

**示例 requirements.txt**：
```
requests==2.31.0
numpy==1.24.0
```

**Docker 命令**：
```bash
pip install --no-cache-dir -q -r requirements.txt && python demo.py
```

### JavaScript

**生成的文件**：
- `demo.js` - JavaScript 代码
- `package.json` - npm 依赖

**示例 package.json**：
```json
{
  "name": "demo",
  "version": "1.0.0",
  "dependencies": {
    "axios": "^1.6.0",
    "lodash": "^4.17.21"
  }
}
```

**Docker 命令**：
```bash
npm install --silent && node demo.js
```

### TypeScript

**生成的文件**：
- `demo.ts` - TypeScript 代码
- `package.json` - npm 依赖（包含 TypeScript 相关包）

**示例 package.json**：
```json
{
  "name": "demo",
  "version": "1.0.0",
  "dependencies": {
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0",
    "ts-node": "^10.9.0"
  }
}
```

**Docker 命令**：
```bash
npm install --silent && npm install --silent ts-node typescript @types/node && npx ts-node demo.ts
```

## 完整示例

### Python 技能

```json
{
  "name": "skill-python-pandas",
  "keyword": "Python pandas data analysis",
  "description": "Learn pandas for data manipulation",
  "language": "python",
  "research_strategy": "context7_first",
  "references": ["https://pandas.pydata.org/docs/"]
}
```

**生成结果**：
```
~/.ai_skills/skill-python-pandas/
├── SKILL.md
├── scripts/
│   ├── demo.py
│   └── requirements.txt
└── references/
    └── research.md
```

### JavaScript 技能

```json
{
  "name": "skill-js-express",
  "keyword": "JavaScript Express.js web framework",
  "description": "Learn Express.js for web development",
  "language": "javascript",
  "research_strategy": "context7_first",
  "references": ["https://expressjs.com/"]
}
```

**生成结果**：
```
~/.ai_skills/skill-js-express/
├── SKILL.md
├── scripts/
│   ├── demo.js
│   └── package.json
└── references/
    └── research.md
```

### TypeScript 技能

```json
{
  "name": "skill-ts-nestjs",
  "keyword": "TypeScript NestJS framework",
  "description": "Learn NestJS for backend development",
  "language": "typescript",
  "research_strategy": "context7_first",
  "references": ["https://docs.nestjs.com/"]
}
```

**生成结果**：
```
~/.ai_skills/skill-ts-nestjs/
├── SKILL.md
├── scripts/
│   ├── demo.ts
│   └── package.json
└── references/
    └── research.md
```

## 混合语言项目

你可以在同一个任务清单中混合不同语言的技能：

```json
{
  "skills": [
    {
      "name": "skill-python-fastapi",
      "language": "python",
      "keyword": "Python FastAPI REST API"
    },
    {
      "name": "skill-ts-react",
      "language": "typescript",
      "keyword": "TypeScript React hooks"
    },
    {
      "name": "skill-js-vue",
      "language": "javascript",
      "keyword": "JavaScript Vue.js composition API"
    }
  ]
}
```

系统会自动为每个技能选择正确的语言环境。

## 性能考虑

### Docker 镜像大小

| 镜像 | 大小 | 首次拉取时间 |
|------|------|-------------|
| `python:3.10-slim` | ~150MB | ~30秒 |
| `node:20-alpine` | ~180MB | ~40秒 |

**建议**：首次使用前预拉取镜像：

```bash
# 拉取 Python 镜像
docker pull python:3.10-slim

# 拉取 Node.js 镜像
docker pull node:20-alpine
```

### 内存占用

| 语言 | 基础内存 | 推荐限制 |
|------|---------|---------|
| Python | ~200MB | 800MB |
| JavaScript | ~150MB | 800MB |
| TypeScript | ~200MB | 800MB |

## 故障排除

### 问题 1：TypeScript 编译错误

**症状**：
```
error TS2304: Cannot find name 'require'
```

**解决方案**：
确保 `package.json` 包含 `@types/node`：
```json
{
  "devDependencies": {
    "@types/node": "^20.0.0"
  }
}
```

### 问题 2：JavaScript 模块导入错误

**症状**：
```
Error [ERR_REQUIRE_ESM]: require() of ES Module not supported
```

**解决方案**：
在 `package.json` 中添加：
```json
{
  "type": "module"
}
```

或使用 CommonJS 语法：
```javascript
const axios = require('axios');  // CommonJS
// 而不是
import axios from 'axios';  // ES Module
```

### 问题 3：依赖安装超时

**症状**：
```
npm ERR! network timeout
```

**解决方案**：
增加 Docker 超时时间：
```bash
# .env 文件
DOCKER_TIMEOUT=600  # 10分钟
```

## 未来计划

计划支持的语言：

- 🚧 **Go** - 计划中
- 🚧 **Rust** - 计划中
- 🚧 **Java** - 计划中
- 🚧 **C#** - 计划中

---

**版本**: v2.1  
**最后更新**: 2026-02-06
