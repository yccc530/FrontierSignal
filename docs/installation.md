# 安装与启动

[返回项目首页](../README.md) · [下一步：使用指南](usage.md) · [遇到问题](troubleshooting.md)

本文面向首次安装、日常启动和版本更新。所有命令都在克隆后的 **FrontierSignal 项目根目录**运行，除非特别说明。

## 选择运行方式

| 方式            | 应用运行位置             | 数据库                             | 启动入口                |
| --------------- | ------------------------ | ---------------------------------- | ----------------------- |
| Windows + WSL2  | WSL 中的 Python / Node   | Docker Desktop 的 PostgreSQL       | `bash scripts/start.sh` |
| Windows 原生    | Windows 的 Python / Node | Docker Desktop 的 PostgreSQL       | `.\scripts\Start.ps1`   |
| 已有 PostgreSQL | 你选择的本地环境         | 自行准备 PostgreSQL 18 与 pgvector | 启动脚本跳过数据库启动  |

完整功能验收是在 WSL2 的用户态 PostgreSQL 环境完成的。Windows 原生脚本语法及 Compose 配置已检查，但 Docker Desktop 容器部署和 Windows 原生全流程尚未独立验收。历史环境与结果见 [验收记录](validation-history.md)。

Docker Compose **只运行数据库**，应用本身由 uv 启动。不要把 `docker compose up -d db` 当成完整应用启动。

## 环境准备

安装 Git、uv、Node.js 22.22.2 或更高的 22 系列版本，以及 Docker Desktop。Python 由 uv 根据项目要求准备，无需替换系统 Python。

官方安装入口：[Git](https://git-scm.com/downloads)、[uv](https://docs.astral.sh/uv/getting-started/installation/)、[Node.js](https://nodejs.org/en/download)、[Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)、[WSL](https://learn.microsoft.com/windows/wsl/install)。

在实际运行项目的终端检查：

```text
git --version
uv --version
node --version
npm --version
docker compose version
docker info
```

WSL 用户需要在 Docker Desktop 中开启对应发行版的 WSL Integration，并把仓库放在 WSL 的用户目录，例如 `~/FrontierSignal`。Windows 和 WSL 分别安装依赖，不能共享 `.venv` 或 `node_modules`。

## 首次安装

### WSL2

在 WSL 终端执行：

```bash
cd ~
git clone https://github.com/yccc530/FrontierSignal.git
cd FrontierSignal
bash scripts/start.sh
```

### Windows PowerShell

在准备存放项目的目录执行：

```powershell
git clone https://github.com/yccc530/FrontierSignal.git
cd FrontierSignal
.\scripts\Start.ps1
```

若 PowerShell 阻止执行脚本，可以使用下面的分步命令；无需永久放宽执行策略。

### 分步执行

以下命令同时适用于 PowerShell 和 WSL，也便于定位失败步骤：

```text
uv sync --locked
uv run python scripts/setup.py
docker compose up -d db
uv run python scripts/wait_db.py
uv run alembic upgrade head
npm --prefix frontend ci
npm --prefix frontend run build
uv run uvicorn frontiersignal.main:app --host 127.0.0.1 --port 8000 --workers 1
```

`setup.py` 从 `.env.example` 生成 `.env`，使用随机数据库密码，保留已存在的配置。不要把示例中的 `CHANGE_ME` 当成可用密码，也不要直接用示例覆盖旧 `.env`。

数据库连接成功并完成迁移后，应用会初始化默认来源与分类。浏览器访问 **http://localhost:8000**；首次采集步骤见 [使用指南](usage.md)。

## 确认启动成功

1. 浏览器能打开工作台，侧栏显示「本地服务已连接」。
2. 打开 `http://localhost:8000/api/health`，返回 `status: "ok"`、`database: "postgresql"`。
3. 「信息来源」中能看到默认来源。「运行任务」可以查看后续采集结果。

未配置 LLM 时，健康接口的 `llm_configured: false` 是正常状态。首页没有资讯不代表启动失败；查看任务和资讯库，确认首轮采集是否完成。

## 日常启动与停止

完成首次安装后，可直接再次使用对应的一键脚本。它会检查依赖、迁移并重新构建前端。若代码未变化，也可以运行：

```text
docker compose up -d db
uv run python scripts/wait_db.py
uv run uvicorn frontiersignal.main:app --host 127.0.0.1 --port 8000 --workers 1
```

前台运行时按 `Ctrl+C` 停止应用。需要同时停止 Docker 数据库时，再执行：

```text
docker compose stop db
```

这会保留数据库卷。应用关闭或电脑休眠时，定时采集和分析暂停；重新启动后检查到期来源，但不能保证补齐远端已移出订阅窗口的历史内容。

### WSL 后台运行

仅适用于 WSL/Linux。需要先完成依赖安装、数据库启动、迁移和前端构建，并停止占用 8000 端口的前台服务。

```bash
uv run python scripts/background.py
```

停止后台应用：

```bash
uv run python scripts/background.py --stop
```

日志位于 `.runtime/backend.log`。后台启动器不启动数据库、不执行构建、不配置开机自启；停止它也不会停止 PostgreSQL。不要同时运行两个后端实例。

## 使用已有数据库

先运行 `uv sync --locked` 和 `uv run python scripts/setup.py`。在 `.env` 中将 `FS_DATABASE_URL` 改为已有 PostgreSQL 连接，数据库中需要能创建 `vector` 扩展。迁移使用的账户必须有相应权限。

示例格式，不能原样使用：

```dotenv
FS_DATABASE_URL=postgresql+psycopg://your_user:your_password@127.0.0.1:54329/frontiersignal
```

密码含 URL 特殊字符时，需要在连接 URL 中编码。然后执行其中一种：

```bash
bash scripts/start.sh --skip-database
```

```powershell
.\scripts\Start.ps1 -SkipDatabase
```

这两个参数只跳过数据库启动，仍然执行连接检查、迁移、前端构建和应用启动。

### 受限 WSL 环境的备选

仓库保留 `scripts/install_user_postgres.sh`，将 PostgreSQL 软件包解包到用户目录，不修改系统服务。它针对开发时使用的 **Ubuntu 26.04 软件包环境**，不是通用 Linux 安装器。仅在发行版和软件包匹配时使用：

```bash
uv sync --locked
uv run python scripts/setup.py
bash scripts/install_user_postgres.sh
uv run python scripts/local_postgres.py
bash scripts/start.sh --skip-database
```

数据目录为 `.runtime/postgres/`，端口为 `127.0.0.1:54329`。日后先运行 `local_postgres.py` 启动数据库，再启动应用；使用 `local_postgres.py --stop` 停止数据库。不要与同端口 Docker 数据库同时运行。

## 更新版本

1. 先创建并验证 [数据库备份](backup-recovery.md)，单独保存私有 `.env`。
2. 停止后端，保留数据库运行。检查 `git status`，先妥善处理自己的源码修改。
3. 阅读 [更新记录](../CHANGELOG.md)，再执行：

```text
git pull --ff-only
uv sync --locked
uv run alembic upgrade head
npm --prefix frontend ci
npm --prefix frontend run build
```

4. 对照 `.env.example` 补充需要的新配置，不覆盖原密钥和数据库密码。
5. 按原来的方式启动后端，检查健康接口、来源与历史资讯。

若更新说明要求历史标签重算，先执行 `uv run python scripts/backfill_technical.py` 预览，再明确加 `--apply` 写入；不必每次更新都重算。迁移失败时先停止升级并检查错误，不删除数据库或盲目降级。

## 本地端口与数据位置

| 位置                         | 用途                                   |
| ---------------------------- | -------------------------------------- |
| `http://localhost:8000`      | 日常使用入口，后端同时提供已构建的前端 |
| `http://localhost:5173`      | 前端开发服务器，仅开发时使用           |
| `127.0.0.1:54329`            | 默认 PostgreSQL 端口                   |
| `.env`                       | 私有配置和密钥                         |
| Docker 的 `postgres_data` 卷 | Compose 数据库的持久化数据             |
| `.runtime/postgres/`         | 仅用户态 PostgreSQL 备选方案使用       |
| `backups/`                   | 备份文件及校验清单                     |

默认仅允许本机访问，没有远程用户认证。不要通过监听 `0.0.0.0` 或端口转发直接公开管理界面。
