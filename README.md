# FrontierSignal

个人 AI 情报工作台，中文界面，保留原文与独立来源。前端连接真实 PostgreSQL 数据，
未配置 LLM 时仍可采集和阅读；不会生成演示摘要或虚假评分。
当前仅面向本机电脑浏览器，工作区最小宽度为 1200px；已移除手机布局、适配样式和截图。

已实现的本地版本包含：13 个默认公开技术来源、来源启停与频率、后台任务与错误记录、
检索/分类/日期筛选/排序/分页、收藏和已读、原始版本详情、模型配置与兼容性探测。
AI 分析包含中文标题、中文摘要、相关性、分类、关注度、证据说明、失败重试和调用审计。
已按用户授权接入 OpenCode 中的火山网关，使用 `volcengine/deepseek-v4.1-flash`，
并通过真实中文响应和资讯持久化验证。历史资讯按批次处理，未完成时明确显示待中文解读。
跨来源相似内容保留各自记录，支持 URL/标题/SimHash 关联及可选 Embedding + pgvector。
首页分为 AI 开源项目、技术热点、前沿论文、官方技术发布和高价值发现；原资讯检索移至
「资讯库」，收藏、已读、原文、中文摘要与详情仍可使用。
GitHub 默认展示短期增长异动，另设新项目观察和完整项目库；使用官方 API、真实日获星和本地
Stars 快照，不是累计 Stars 榜或 GitHub 官网 Trending 名次。支持检索、收藏、版本跟踪与历史。
X / Reddit 已退出当前产品，不需要其 API 配置，不会自动创建相关任务；统一采集接口保留。

当前阶段与验收见 [PROJECT_PLAN.md](PROJECT_PLAN.md)，真实测试记录见
[docs/testing.md](docs/testing.md)。上游代码审计与许可证见 [REUSE_ASSESSMENT.md](REUSE_ASSESSMENT.md)。

## Windows PowerShell

需要 Python 3.11（uv 自动安装）、uv、Node.js 22.22.2+、Git、启用 WSL2 的 Docker Desktop。
在项目目录执行：

```powershell
uv sync --locked
uv run python scripts/setup.py
docker compose up -d db
uv run python scripts/wait_db.py
uv run alembic upgrade head
npm --prefix frontend ci
npm --prefix frontend run build
uv run uvicorn frontiersignal.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://localhost:8000`。修改界面时另开终端运行
`npm --prefix frontend run dev`，打开 `http://localhost:5173`。

也可使用 `./scripts/Start.ps1`。数据库已由其他方式启动时使用
`./scripts/Start.ps1 -SkipDatabase`。本次只验证了 Windows PowerShell 语法与
Windows Docker Compose 配置解析；完整运行测试是在 WSL2 中完成的。

`.env` 是私有配置，初始化脚本不会覆盖现有文件。数据库密码由脚本随机生成。
不要把后端改为监听 `0.0.0.0` 或开放到公网；当前是个人本地管理应用，不提供远程账户认证。

## 当前 WSL 环境

代码放在 `/home/niannian/FrontierSignal`，不放在 `/mnt/c` 中运行依赖目录。
Windows 可通过 `\\wsl.localhost\<发行版>\home\niannian\FrontierSignal` 访问文件。
Windows 与 WSL 分别运行 `uv sync` / `npm ci`，不要共享虚拟环境或 node_modules。

本次环境 Docker socket 无权限、Compose 插件缺失。已在用户目录解包 PostgreSQL 18
作为本机开发替代，可运行 `uv run python scripts/local_postgres.py`；数据位于
`.runtime/postgres/`，TCP 仅监听 127.0.0.1:54329，需本地随机密码。
这不代表 Docker Desktop 已验收。常规用户应使用上面的 Docker 路径。

停止此用户态数据库：`uv run python scripts/local_postgres.py --stop`。
不要删除 `.runtime/postgres` 或执行 `docker compose down -v`，除非明确要删除数据。

WSL 一键启动：`bash scripts/start.sh`。本次 Ubuntu 26.04 的用户态安装可通过
`bash scripts/install_user_postgres.sh` 重建；其他发行版优先 Docker Desktop。
电脑休眠、关闭 WSL 或停止后端时，定时采集不会运行，RSS 也不保证补齐窗口外的历史。

当前 WSL 的数据库、迁移与前端构建已完成，可用以下命令管理后台服务：

```bash
uv run python scripts/background.py
uv run python scripts/background.py --stop
```

后台日志为 `.runtime/backend.log`，访问 `http://localhost:8000`。启动器检查已记录进程的
身份，拒绝替换占用端口的其他程序；停止后端不会停止 PostgreSQL。切换到前台启动前先停止
后台服务；修改代码后需要重新构建前端并重启后端。它不负责开机自启动。
已从 Windows PowerShell 实际访问此地址：主页 HTTP 200、API 健康状态 ok，证明本机
Windows 到 WSL 的 localhost 转发可用；后端与数据库仍运行在 WSL。

## 网络与密钥

应用继承 `HTTPS_PROXY`，也可通过 `FS_OUTBOUND_PROXY` 显式配置；空字符串表示直连。
采集代理连接使用已校验的公网目标 IP，TLS 仍校验原主机名。没有关闭证书校验。
来源主机必须在白名单中；新增公开域名用 `FS_EXTRA_FEED_HOSTS` JSON 数组。
内容中的外链只供浏览器打开，后端不会任意抓取它们。

LLM 凭据只写入 `.env`：`FS_LLM_BASE_URL`（包含服务所需的 `/v1`）、
`FS_LLM_MODEL`、`FS_LLM_API_KEY`。配置后重启。不要把密钥粘贴到 issue 或提交到 Git。
非标准参数不默认发送；JSON mode 需要显式开启并通过实际服务验证。

本机可从用户指定的 OpenCode 配置导入网关：

```powershell
uv run python scripts/configure_opencode.py
```

默认读取用户目录下的 `.config/opencode/opencode.json`，只选择「火山AI网关」和
`volcengine/deepseek-v4.1-flash`，将地址、密钥、模型写入项目 `.env`，保留其他配置，
不修改 OpenCode 文件、不输出密钥。显示名称 `DeepSeek-V4.1-Flash1017` 不作为请求模型标识。
其他配置位置可使用 `--config` 指定；导入后重启后端。
本机该网关的请求超时已根据实际慢响应调整为 120 秒，保留最多 2 次内部重试；
结构化输出参数仍默认关闭，所有响应继续经过中文字段和数据结构校验。

资讯列表和详情优先显示中文标题与摘要，原始标题与正文保留在详情的展开项中。
中文摘要是模型概括，不是全文逐句翻译；仅有标题的来源会标明信息不足。
搜索同时覆盖中文标题与原文。原文变化会清除过期的中文结果并重新排队。
真实中文处理可运行 `uv run python scripts/verify_chinese.py --batches 1` 验证，
该命令会实际调用已配置的服务并消耗用量；应在没有其他分析任务时执行。

## 技术推荐与项目发现

保留原有 7 个有效来源，新增 GitHub AI 项目发现、Hugging Face 模型/数据集，
以及 arXiv cs.LG、cs.CL、cs.CV。Anthropic 常见官方 RSS 地址本次返回 404，
未添加不稳定来源，也未采用未验证的第三方 feed 或网页抓取替代。

「开源项目」默认是增长异动：短期增长量、每小时速度、相对增幅/占比及加速倍数。
累计 Stars 仅作背景，不给最终排名加分；老牌项目只有出现真实异动才重新入榜。
「新项目」以 GitHub 实际创建不超过 30 天为准，「全部项目」保留历史仓库及原有收藏。
发现按 8 组技术主题与近 7/30/90 天创建、中小项目新动向交叉检索，并轮换候选页。
默认每小时 2 组查询、每组最多 10 个项目；10 个跟踪名额优先年轻和近期活跃项目，
最多读取 8 个官方获星历史、核验 3 个仓库根目录。大规模项目库会拉长实际跟踪间隔。

新发现时可由官方 `/stargazers/history` 提供真实日获星，显示「今日/昨日获星 (UTC)」及实际窗口。
它不是滚动 24 小时或取消 Star 后的净增。本地净增则需要两个合适时间点的快照，
不使用累计 Stars 冒充新增 Stars，不插值或回填虚构历史。净增包含取消 Star 的影响，
可为负数；实际采样跨度和时间可查看。快照超期或窗口没有合适基线时仍显示未知。
每仓库每小时保存一个最近实际观测，优先检测 1h/6h/24h 变化，另保留 7d 净增。
无增长证据时显示待观测，不用老牌项目填充增长榜。指标和历史变化不会重复创建项目或重跑模型。

HN 同时读取 top/best/new 榜单，默认最多 60 个候选，对优先技术帖采样最多 3 条公开评论，
展示真实 points、评论总数与采样范围。同一原文的不同讨论保留独立记录并关联；首页压缩重复事件。
arXiv 保留作者、摘要、原始分类、发布时间与链接，预印本不会被当作已证实结论。

推荐分是可解释的排序分，不是真实性概率。首页的「研究偏好」可保存关注方向；
技术规则与 AI 分析分开记录。非技术内容仍可在资讯库的「更多筛选 → 全部原始资讯」查看。
中文分析仅使用已配置火山网关，原文不被翻译覆盖。新提示词优先技术价值，旧模型结果不批量重跑。

可选 `FS_GITHUB_TOKEN` 仅用于 GitHub 官方 API；无令牌已完成真实公共访问验证，达到限额会记录错误。
预算可用 `.env.example` 中 `FS_GITHUB_*` / `FS_HN_*` 调整；不需要 X 或 Reddit 的账号、密码或 API Key。
升级已有数据库时，停止后端后运行：

```powershell
uv run alembic upgrade head
uv run python scripts/backfill_technical.py
npm --prefix frontend run build
```

技术标签回填只读取现有原文和快照，不访问外部来源、不调用 LLM。再按当前 WSL/Windows 启动方式启动。
运行 `uv run python scripts/verify_discovery.py` 可验证真实公开源与推荐结果；失败返回非零退出码。
算法、窗口与限制见 [技术推荐决策](docs/decisions/0002-technical-discovery.md)。

## 开发检查

```powershell
uv run pytest -q
uv run ruff check backend tests scripts
npm --prefix frontend test
npm --prefix frontend run build
uv run python scripts/integration_db.py
uv run python scripts/smoke_live.py
npm --prefix frontend run test:e2e
uv run python scripts/backup.py --verify
```

其中 `smoke_live.py` 需要已启动的 API 和真实外网；浏览器 E2E 需要已采集的真实
资讯，会修改并恢复测试涉及的收藏、已读和来源开关，设置测试保存当前非敏感配置。
`integration_db.py` 和备份恢复演练使用自己创建的新数据库，不覆盖主库。
详见 [测试记录](docs/testing.md)。

配置 LLM 后运行 `uv run python scripts/probe_llm.py`；成功后在界面触发分析。
默认每批 5 条、请求总超时 60 秒、内部重试 2 次。成功内容不会随重启重复处理。
调度开启时，配置完整后每 30 秒检查并自动处理待分析批次。若先只验证接口，可在 `.env`
设置 `FS_SCHEDULER_ENABLED=false` 后重启；这同时暂停自动采集，手动操作仍可使用。
启用 Embedding 必须单独指定服务商支持的 `FS_EMBEDDING_MODEL`；该真实接口也尚未验收。

## 文档

- [架构](docs/architecture.md) · [数据来源](docs/data-sources.md) · [测试](docs/testing.md)
- [备份恢复](docs/backup-recovery.md) · [故障排查](docs/troubleshooting.md)
- [开发约束](AGENTS.md) · [变更记录](CHANGELOG.md) · [第三方署名](THIRD_PARTY_NOTICES.md)
