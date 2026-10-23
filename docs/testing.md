# 开发与测试

[返回项目首页](../README.md) · [架构说明](architecture.md) · [历史验收记录](validation-history.md)

普通用户只需按 [安装指南](installation.md) 启动应用，不需要执行这里的验证脚本。本文面向修改代码、排查问题或验证新来源的开发者。

## 开发环境

先完成依赖安装、数据库启动和迁移。代码结构：

```text
backend/frontiersignal/   采集器、分析、存储、推荐、调度与 API
backend/alembic/          数据库迁移
frontend/src/            React 工作台
frontend/e2e/            桌面浏览器测试
tests/                   Python 测试与夹具
scripts/                 安装、运维及真实服务验证工具
docs/                    使用、架构与验收文档
```

开发前阅读 [AGENTS.md](../AGENTS.md) 和 [项目计划](../PROJECT_PLAN.md)。Python 依赖使用 `uv.lock`，前端使用 `package-lock.json`；不要在 Windows 与 WSL 之间共享虚拟环境或 Node 依赖目录。

为了避免热更新期间自动采集或产生 LLM 用量，可以在开发环境将 `FS_SCHEDULER_ENABLED=false`，调试结束后恢复。手动任务仍会执行，数据库也仍是真实数据库。

终端一，启动后端：

```text
uv run uvicorn frontiersignal.main:app --host 127.0.0.1 --port 8000 --reload
```

终端二，启动前端：

```text
npm --prefix frontend run dev
```

访问 `http://localhost:5173`。Vite 将 `/api` 转发到 8000。生产使用前执行 `npm --prefix frontend run build`，再按日常方式启动后端，访问 8000。

不要同时运行后台启动器和前台开发后端；调度要求单 worker。调整端口时还需要同步 Vite 代理与允许的 Origin。

## 按变更选择检查

| 修改内容                 | 必要检查                                                |
| ------------------------ | ------------------------------------------------------- |
| 文档                     | 链接与路径、命令对应的脚本和参数、默认值、Markdown 格式 |
| 标准化、去重、窗口或推荐 | 相关 pytest 用例、Ruff；数据库行为另做集成检查          |
| 前端逻辑或视觉           | Vitest、TypeScript / Vite 构建；受影响的桌面页面或 E2E  |
| 数据模型或迁移           | PostgreSQL 隔离集成、迁移检查和必要的备份恢复演练       |
| 采集器或模型兼容性       | 可控 HTTP 夹具；另选有界真实服务验证，分别报告结果      |

外部接口不稳定不应导致离线测试依赖真实网络。不要用夹具结果证明实际来源可用，也不要将短测当作 24 小时或 7 天观察。

## 离线检查

依赖已安装后，以下检查不需要真实来源或付费模型：

```text
uv run pytest -q
uv run ruff check backend tests scripts
npm --prefix frontend test
npm --prefix frontend run build
```

可以按受影响文件缩小 pytest 范围。测试覆盖标准化、URL、精确去重、数据库交互、模型失败重试、任务状态、推荐窗口与核心前端交互。

## GitHub Actions

配置文件为 [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)，工作流名称为 `CI`。

- 推送到 `main`、向 `main` 创建或更新 PR 时自动运行，也支持手动运行。
- `Backend checks`：Python 3.11、uv 0.12.5，按 `uv.lock` 安装依赖，执行 Ruff 和 pytest。
- `Frontend tests and build`：Node.js 22，执行 `npm ci`、Vitest 和 TypeScript / Vite 生产构建。
- 两个任务并行运行，单个任务最长 15 分钟；同一分支的新运行会取消尚未结束的旧运行。
- 第三方 Actions 固定到完整提交 SHA；仓库权限仅为读取，checkout 不保留认证凭据。

在 GitHub 仓库点击 **Actions → CI**，选择一次运行，再点击对应任务和步骤查看日志。绿色表示通过，红色表示失败。手动运行时，在 CI 页面选择 **Run workflow → 分支 → Run workflow**。

不需要添加 API Key、GitHub Token 或其他 Secrets。运行环境不创建私有 `.env`，后端关闭自动调度，现有单元测试使用临时 SQLite 和 HTTP 夹具；安装依赖和缓存仍需要网络。

这个工作流不启动日常采集服务，不执行付费 LLM、真实外网采集、PostgreSQL 集成或依赖真实资讯的 Playwright 测试，也不自动部署。CI 通过表示上述代码检查通过，不等于来源始终可用或 Windows 原生环境已验收。

## PostgreSQL 集成

```text
uv run python scripts/integration_db.py
```

需要可连接的 PostgreSQL、pgvector 和创建数据库权限。脚本创建随机名称的独立数据库，验证迁移及数据库行为，仅清理自己创建的测试库。它不替代主库备份。

## 浏览器验证

先安装 Chromium，启动 8000 端口的应用并准备已采集数据：

```text
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

按需运行单个测试文件：

```text
npm --prefix frontend run test:e2e -- discovery.spec.ts
```

测试读取实际 API，部分用例会修改并恢复收藏、已读、偏好、来源或设置。它们不是只读检查，空库可能不满足用例前提。只保留桌面测试，默认视口为 1440 × 1000；失败截图与追踪在被忽略的测试输出目录。

## 真实服务验证

运行前确认后端已启动、来源可访问，并了解脚本的写入或费用影响。需要避免自动任务干扰时，临时暂停调度并重启，结束后恢复原设置。

| 命令                                        | 行为与前提                                               |
| ------------------------------------------- | -------------------------------------------------------- |
| `uv run python scripts/probe_llm.py`        | 一次真实模型接口探测，消耗服务用量；不创建新闻           |
| `uv run python scripts/smoke_live.py`       | 触发两轮真实采集，保存内容并检查重复与 ID                |
| `uv run python scripts/check_sources.py`    | 触发来源采集并检查任务结果，写入真实资讯                 |
| `uv run python scripts/verify_discovery.py` | 检查项目发现、HN、HF 与论文链路，产生采集记录            |
| `uv run python scripts/verify_expansion.py` | 有界扩展方向验证，临时修改来源范围后恢复；默认不调用 LLM |
| `uv run python scripts/backup.py --verify`  | 生成备份并恢复到随机验证库，核对后清理该验证库           |

`verify_expansion.py --analyze-one` 会额外分析一条真实内容并产生模型用量。长轮次模型扫描还有 `verify_model_sources.py`，不是每次提交都必须执行的检查；其参数可用 `--help` 查看。

失败、部分成功、样本不足和未扫描需要如实记录。历史脚本中的轮次数只适用于当时目录和预算，不能保证当前所有主题都被覆盖。

## API 调试

应用启动后可访问 `http://localhost:8000/docs` 查看 OpenAPI，`/openapi.json` 为接口契约。

写入接口要求请求头 `X-FrontierSignal: 1`；只允许配置中的本机 Origin。Swagger 页面不会自动添加该自定义头，写操作调试需使用能显式设置请求头的客户端。这里的限制不是远程账户认证，不应据此公开部署。

## 验证记录

历史功能验收、真实服务调用和备份恢复证据见 [历史验收记录](validation-history.md)。2026-10-23 的 B4–B8 记录包含 138 项 pytest、10 项 Vitest、7 项选定桌面 E2E 和 13 张业务表恢复核验；这些是当次结果，并非每次文档修改都重跑的测试。

本次文档整理的检查结果另记于该文档，不刷新或冒用此前业务测试结果。Windows 原生完整部署、可选 Embedding 实际服务以及持续 24 小时 / 7 天观察仍按各自证据验收。
