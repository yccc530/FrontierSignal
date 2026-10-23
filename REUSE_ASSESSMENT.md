# 开源复用审计

审计日期 2026-10-22。六个仓库均通过 GitHub 实际浅克隆到
`/tmp/frontiersignal-audit/`，阅读下列文件。未运行上游应用或上游测试；
维护状态仅依据所克隆 HEAD 的时间，不代表完整 issue 审计或可运行性证明。
原仓库地址由用户提供，下面的完整 SHA 可用于重建审计版本。

## AI News Brief

- 仓库：`https://github.com/frankzch/ai-news-brief`
- SHA：`3b3e182384b27461ebed8512c9e506c7a2fbb002`，2026-10-12。
- MIT，Copyright (c) 2026 frankzch。
- 已读：README、requirements.txt、config.yaml 的配置入口，以及
  `src/rss_fetcher.py`、`lsh_dedup.py`、`config_loader.py`、`scheduler.py`、
  `ai_engine.py`、`pipeline_runner.py`、`user_db.py`、`vector_store.py` 核心路径。
- Python 脚本；feedparser、OpenAI SDK、psycopg2、pgvector、sentence-transformers。
  配置为 YAML + .env；schedule 循环；PostgreSQL DDL 在程序启动时创建/修改；
  没有 Alembic。articles 使用全局 URL 唯一键，向量/SimHash 相似内容会跳过入库。
  公共仓库主要是采集引擎，没有目标 React/FastAPI 工作台。
- **适配后复用** RSS content/summary 优先级、UTC 时间转换和 SimHash 函数。
  记录缺失日期为 null，修复有符号 64 位 Hamming 距离，保留版权及许可证。
- **仅参考设计** 分阶段处理、类别提示词、抓取统计。
- **不采用** 存储层、全局删除式去重、用户/计费/审核模块、浏览器兜底。
  `RSSFetcher._fetch_url` 使用 `verify=False`；采集含 TLS 指纹模拟与浏览器兜底；
  `pipeline_runner` 在最终保存前过滤，无法满足原始记录持久保存要求。
  依赖大多只有下限，浏览器和本地 embedding 模型会显著增加 Windows 安装负担。

## AI News Aggregator

- 仓库：`https://github.com/flyryan/ai-news-aggregator`
- SHA：`c5e85356f8ddabd24ff7ca1d5ff123e75262777e`，2026-10-21。
- Apache-2.0。
- 已读：README、requirements.txt、frontend/package.json、run_pipeline.py、
  `agents/analysis_schema.py`、`agents/config/schema.py`、`agents/continuity/coordinator.py`、
  `admin_service/store.py`、docker-compose.yml；检索 orchestrator/checkpoint/生成器路径。
- Python gatherers/analyzers；Anthropic / 兼容代理配置；JSON checkpoint 与日报产物；
  管理服务独立 SQLite；Svelte 5 + SvelteKit + Vite 6 + MiniSearch；
  workflow/cron 日报触发。无统一业务 SQLAlchemy/Alembic 数据层。
- **仅参考设计** 分阶段记录、事件延续关联、来源异常与费用追踪；不复制代码。
  日报静态站与交互式个人管理的存储/前端不同，多代理与图片生成超出 MVP。
  读取到的依赖有较旧固定版本；未宣称它们存在已确认漏洞。

## TrendRadar

- 仓库：`https://github.com/sansan0/TrendRadar`
- SHA：`68c8916c450f8c8dd36cb88a189f7c2e46681ab5`，2026-10-20。
- GPL-3.0；pyproject 要求 Python >=3.12，与本项目 Python 3.11 不一致。
- 已读：README、pyproject、`trendradar/core/config.py` 配置入口、
  `core/scheduler.py`、`storage/rss_schema.sql`、`storage/manager.py`；检查模块目录。
- Python 模块包括 crawler、ai、notification、report、storage；配置 YAML，
  时间线调度、SQLite schema + 可选远端 S3 同步、HTML 报告与 MCP；不是 React 工作台。
- **仅参考设计** 来源启停、热点筛选、逐来源任务计数；不复制 GPL 代码进入本项目。
  不移植其时间线、通知矩阵和存储体系，避免引入运行时与许可证边界复杂度。

## RSSHub

- 仓库：`https://github.com/DIYgod/RSSHub`
- SHA：`ec765d3c4b95b515b0d6a651be98e75d94affbb9`，2026-10-22。
- **当前版本 AGPL-3.0**，不能按历史印象标为 MIT。
- 已读：package.json、LICENSE、`lib/types.ts`、`lib/config.ts`、
  `lib/middleware/cache.ts`、`lib/utils/cache/index.ts`；检查 routes/github。
- TypeScript/Hono，路由模块输出 Data/DataItem；环境变量配置；memory/Redis/HTTP/KV
  缓存，按请求抓取，非新闻业务数据库；Node ^22.22.2 或 ^24.15.0。
- **外部适配**：用户部署/获准使用的公开 HTTPS feed 可经 RSS 适配器消费；
  不内嵌完整路由仓库，不将第三方公共实例可用性作为核心依赖。

## Crawl4AI

- 仓库：`https://github.com/unclecode/crawl4ai`
- SHA：`30165f1ee1fb61f6cce1477feed2acc5e2181e25`，2026-10-20。
- LICENSE 为 Apache-2.0 文本后附 Attribution Requirement，要求可见署名；
  README 的“recommended”与 LICENSE 措辞不同。将来引入时需按实际文本复核。
- 已读：pyproject、LICENSE、README、`async_webcrawler.py`、`async_database.py`、
  `migrations.py`；检查 models、extraction、markdown 和 browser 模块目录。
- Python >=3.10，Pydantic、Playwright/patchright、SQLite 缓存与文件内容存储，
  自有迁移；不是资讯业务模型。浏览器/ML/代理依赖重，含本项目不采用的规避能力。
- **后续候选，当前不采用**：第一版只消费 feed/API 正文，避免额外网页请求。
  后续独立评估普通正文提取模式、许可及浏览器成本，不继承规避访问控制行为。

## twscrape

- 仓库：`https://github.com/vladkens/twscrape`
- SHA：`63f61a518e576ea5c132f1156c03dda0520d76c1`，2026-10-22。
- MIT；Python >=3.10；当前版本 0.20.1。
- 已读：readme.md、pyproject、LICENSE、`db.py`、`accounts_pool.py`、`login.py`。
- 异步 X GraphQL/search；SQLite 账户/密码/cookie/锁与 user_version 迁移；
  依赖授权账户，推荐导入 cookie，可选 curl-cffi，限流后账户切换。
  没有本项目需要的资讯数据库或前端，账户可用性与接口变化成本高。
- **不采用**：本版不保存 X 账户会话，不自动登录、不切换账户规避限流。
  后续只在官方 API 或明确授权接口和凭据可用后单独接入。

## 复用清单

复制/适配范围仅限 AI News Brief 的 RSS 解析小段与 SimHash 工具。
见 `THIRD_PARTY_NOTICES.md` 与 `licenses/ai-news-brief-MIT.txt`。
feedparser、SQLAlchemy、APScheduler、React 等以锁定依赖使用；没有合并完整上游仓库。

真实 vLLM 发布说明暴露了 `simhash 2.1.2` 与 NumPy 2 的兼容性问题：高频片段权重
超过 255 时，上游 uint8 位数组乘法溢出。项目固定 simhash 版本，在继承类的位数组
入口提升为 int64，再使用原算法。回归测试覆盖长重复文本的精确指纹及短文本与上游
结果一致性；升级该依赖时必须重新检查这个兼容补丁。
