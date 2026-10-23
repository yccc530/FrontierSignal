# 测试与验收

测试分两类：离线夹具测试验证可重复逻辑；真实服务测试证明当时环境的连通性。
两者不能相互替代。已按用户授权配置火山网关并完成真实模型调用；X / Reddit 已从
当前产品和本机数据库删除，不再需要相关凭据。向量服务仍未配置。

当前只保留桌面代码和浏览器测试，10 张历史手机截图已删除。下文手机测试结果仅是历史记录，
不代表仍保留手机界面、测试配置或截图文件。

## 增长动量重构验收（2026-10-22，当前版本）

- 后端 75 项测试通过，新增小项目快速增长超过大项目、老项目真实加速回榜、最近减速不回退
  到旧热度、未知/零/负增长、UTC 日窗口、过期和缺失证据、搜索分组及跟踪优先级等回归。
  官方历史更新不会制造累计快照或重复触发成功文章的分析。
- 前端 Vitest：7 passed（1.56 秒）；TypeScript / Vite 生产构建通过。
- 桌面 Playwright：7 passed（7.7 秒），验证增长/新项目/全部范围、指标、检索、分页、
  收藏、来源和设置。初次 6 passed / 1 failed 是旧测试假设搜索词必须出现在标题：
  实际新发布说明在正文命中 vllm。改为核对 API 全文命中和真实首条标题，完整复测通过。
- Ruff check 和 59 个 Python 文件格式检查通过。真实隔离 PostgreSQL 全量迁移与
  pgvector 0.8.1 查询通过；业务库已增量升级到 `8ac491d20e63`。
- 真实调用官方 Search、Repositories、Releases、Contents、Stargazers History API。
  任务 `70c48834-50ed-4a0e-b5f6-a256833c0e51` 新增 26、重复 13、规则过滤 6、失败计数 1。
  失败原因是上游搜索 `incomplete_results`，任务状态如实为 partial，脚本非零退出；
  不能宣称这轮完整采集成功。已经获取的项目、发布、历史与本地快照均保存。
- 当时 57 个技术项目中有 1 个增长异动、4 个近 30 天新项目。首页显示 1 个异动和另外
  3 个观察候选，跨分区不重复；已有可见项目资讯 ID 均保持不变。
- 实际例子：Generated-Computers/Locals 累计 195 Stars，官方 UTC 本日截至
  2026-10-22 13:17:33 UTC（北京时间 21:17:33）记录 55 次获星，约 4.14/小时，
  为此前 6 个完整 UTC 日平均速度的 4.69 倍。这是官方日获星，不能说成滚动 24h 净增。
  记录保存在本机 `.runtime/momentum-check.json`，不是生产演示数据。
- 真实备份恢复包含 606 条资讯、914 个原始版本、66 个候选仓库、98 条本地快照；
  10 张业务表恢复计数一致，详情见 backup-recovery.md。
- 仍有限制：官方搜索与分页覆盖有界，Stars 变化不证明技术质量；API 历史可能延迟或缺失。
  本地真实 24h/7d 连续窗口及长期运行效果仍待持续观察，本轮没有额外执行 LLM 付费验证。

## 手机界面清理验收（2026-10-22）

- 删除 10 张手机截图、7 处手机/平板布局断点、弹窗手机样式和移动视口设置；未新增项目文件。
- 扫描项目源码与本机产物，没有剩余手机专用文件或移动端样式分支；保留桌面宽屏及无障碍样式。
- TypeScript / Vite 生产构建通过；前端单元测试 7 passed（1.48 秒）；仅桌面 Playwright
  7 passed（7.2 秒），覆盖推荐、检索、分页、详情、收藏、来源和设置。
- 本轮未修改后端或数据库结构，未重跑后端及外部服务采集测试。启动原有本地 PostgreSQL
  和后台服务后完成桌面联调，入口仍为 `http://localhost:8000`。

## 技术情报推荐验收（2026-10-22，增长重构前）

- 按用户明确的使用范围，当前仅验收本机电脑端，Playwright 默认只运行桌面 1440x1000。
- 后端 `uv run pytest -q`：60 passed（3.86 秒）；Ruff check 与 56 个 Python 文件格式检查通过。
  覆盖去重、真实快照时间窗口、未知/零/负增长、HN 热度排序、来源隔离、模型过滤后移出推荐，
  并确认被过滤项目的原文和快照仍保留。
- 最终前端 Vitest：7 passed（1.03 秒）；TypeScript / Vite 生产构建通过。
- 最终桌面 Playwright：7 passed（6.8 秒），包括连续切换搜索/排序和项目翻页的真实接口验证。
- 本轮较早的 Playwright 结果为 14 passed（12.9 秒），当时包含桌面和手机。
  后续按用户要求删除手机测试配置；以下覆盖范围仍用于桌面验收。
  验证五个推荐分区、技术主题、项目检索/排序、Stars 历史、收藏/已读、研究偏好持久化、
  X / Reddit 入口移除，并回归原有资讯、来源、任务和设置功能。
- 首次本轮浏览器结果为 12 passed / 2 failed：项目搜索框和提交按钮同名，测试定位不唯一。
  改为按 textbox 角色精确定位，完整重跑 14 项通过，没有跳过失败用例。
- 随后新增分页检查时再次发现连续清空搜索并切换排序会带回旧查询。请求记录确认问题后，
  保存尚未渲染完成的最新筛选参数，避免路由更新覆盖；同时复用现有箭头分页组件修正文字挤压。
- 真实隔离 PostgreSQL 数据库执行全部 Alembic 迁移，pgvector 0.8.1 查询与调度锁验证通过。
  当前业务库迁移为 `4f6a329b8102`，新增项目、快照、技术规则与来源指标字段。
- 原有 247 条资讯继续保留。两轮真实 GitHub 采集后，共 38 个候选仓库、36 个技术项目、
  48 条真实 Stars 快照；第二轮新增 47 条项目/发布记录、重复 10 条，失败 0。
  首轮项目的资讯 ID 在第二轮保持一致，指标更新不重复创建资讯。
- 13 个来源均已实际采集成功；当时共有 509 条资讯、734 个原始版本。HN 评论为真实样本，
  样本数与平台报告的总评论数分开显示。HF 模型/数据集、arXiv LG/CL/CV 均返回实际记录。
- 真实火山网关模型 `volcengine/deepseek-v4.1-flash` 分别分析 DeepSpeed 项目、HN Agent
  沙箱讨论、arXiv Transformer 论文，3 个任务均 success，中文标题/摘要已持久化。
  逐条对照原始标题、正文和链接均未改变；成功记录再次提交返回 409，调用次数未增加。
  本机记录为 `.runtime/technical-llm-check.json`。
- 删除 X 来源 1 个、历史失败任务 1 条、资讯 0 条；私有 `.env` 的 X 凭据已删除，旧库恢复
  后的停用平台会在启动时禁用。其他来源和已有火山模型配置继续使用。
- 120 个可提交文件扫描没有发现本机配置中的完整密钥；`.env` 权限为 0600。
  私有比较确认 LLM 地址、密钥和请求模型与用户授权的 OpenCode 火山网关配置一致。
- 10 张业务表的实际备份恢复通过，详见 `docs/backup-recovery.md`；恢复只创建随机测试库。
- 当前所有项目的 24h / 7d 增长均为未知，因为真实历史窗口尚未形成。窗口边界、未知、零、
  负增长、陈旧/未来样本由离线夹具验证，不宣称已观察到真实长期增长。
- GitHub 使用官方搜索/仓库/发布 API，本地推荐不是官网 Trending 名次。
  Anthropic 常见官方 RSS 地址实际返回 404，未接入未经确认的替代来源。

桌面截图：`.runtime/desktop-recommendations.png`、`.runtime/desktop-projects.png`、
`.runtime/desktop-stars-history.png`。长期无人值守、实际 24h / 7d 增长、
Windows 原生安装启动与未配置的向量服务仍未通过本轮实机验收。

## X 与来源调整复测（2026-10-22，历史记录，功能已移除）

以下仅保留当时的验证证据；其中 X 脚本、界面和凭据均已删除，不再适用于当前版本。

- 后端 `uv run pytest -q`：55 passed（3.38 秒）。覆盖官方令牌请求格式、拒绝重定向、
  凭据错误脱敏、私有配置、分页高水位、空结果、401/402/403/429、部分失败重试与去重、
  默认手动调度、查询修改及 Reddit 接口移除。X 纯文本中的尖括号不被 HTML 清洗误删。
- 前端 Vitest：5 passed（1.33 秒），包括查询保存和游标重置提交真实 API 契约的夹具测试。
- Playwright：10 passed（9.1 秒），桌面 1440x1000 / 手机 390x844。
  浏览器连接真实后端，验证 X 配置显示、开关刷新持久化、X 添加表单及 Reddit 入口消失，
  同时回归检索、收藏/已读、详情、来源管理和系统设置。
- 初次浏览器验证为 6 passed / 4 failed：原文标题与对话框标题同名时，旧测试选择器不唯一；
  X 查询输入的说明文字被误包含在字段名称中。修正标题层级定位与表单 label/description，
  重新运行全部 10 项通过，没有跳过失败用例或删除断言。
- TypeScript/Vite 生产构建、Ruff 静态检查及 51 个 Python 文件格式检查通过。
- 本机 PostgreSQL 实际删除 Reddit 来源 1 个、任务 1 条，相关资讯 0 条；
  API 不再返回 Reddit，私有 `.env` 中删除 `FS_REDDIT_TOKEN`，新启动不会重新创建来源。
- X 消费者密钥按用户授权写入忽略的 `.env`，权限为 0600。109 个可提交文件及后端日志
  扫描未发现完整 X/LLM 密钥；设置 API 不返回完整密钥，只返回是否配置。
- 真实 `POST https://api.x.com/oauth2/token` 返回 HTTP 403、错误码 99，响应明确为凭据无法
  验证。可能的图片字符识别或失效凭据原因尚不能确定；不能据此判断账户余额或读取权限。
- `uv run python scripts/verify_x.py` 实际退出码 1；任务
  `b2f44d9a-f345-433e-be5e-01cc7a1c8c98` 状态 failed，新增 0、重复 0、失败 1，
  X 已存资讯 0。中文授权错误持久化并在来源和任务页显示；没有创建模拟帖子。
- 当时 X 来源 `x-openai`：查询 `from:OpenAI -is:retweet`、每页最多 10 条，自动关闭。
  后续按用户要求移除，不再配置或尝试调用。
- 当时的桌面 X 截图：`.runtime/desktop-x-sources.png`。
  浏览器测试临时停用 X 来源后切换自动状态，最后恢复，避免测试触发付费 API 读取。
- 最终重启后 `/api/health` 为 ok / postgresql，scheduler 为 true；原有 7 个来源均启用，
  Reddit 来源为 0，X 启用但 automatic 为 false，真实 X 资讯仍为 0。火山网关地址、
  密钥与请求模型通过私有比较确认与用户指定 OpenCode 配置一致，没有输出比较值。
  Windows PowerShell 实际请求 `http://localhost:8000/api/health` 返回 ok。

该历史轮次没有修改数据库结构，使用现有 JSON 字段保存 X 配置/游标。未重新运行原本已经通过的
全量迁移、备份恢复或真实 LLM 付费测试；它们的前次证据仍见下文。

## 中文阅读与火山网关复测（2026-10-22）

- 从用户指定的 OpenCode 配置读取「火山AI网关」，使用请求模型标识
  `volcengine/deepseek-v4.1-flash`；`DeepSeek-V4.1-Flash1017` 是配置中的显示名。
  没有修改 OpenCode 配置，没有在输出中打印密钥。
- 一次独立接口验证返回有效中文标题与摘要，服务端报告输入 268、输出 674 词元。
  这条验证消息未作为新闻写入资讯表。
- `uv run python scripts/verify_chinese.py --batches 4`：4 个真实分析任务均 success，
  每批 5 条，首页 20 条中文标题/摘要已持久化；原始标题和正文逐条对照保持一致。
  成功条目再次请求分析返回 409，调用审计记录数不增加。
- 首条资讯前两次请求超时，第三次请求成功；失败与成功尝试均被保留，原文未丢失。
  这是本次服务的真实重试观察，不是伪造故障或额外注入的模拟响应。
- 全部 20 条共记录 26 次分析尝试：20 次成功、3 次超时/连接失败、3 次格式或中文校验失败。
  各条最终均成功。没有保留失败响应全文，不能进一步断言具体哪个返回字段有误。
  本机网关请求超时随后从 60 调整为 120 秒，密钥、模型及 JSON 模式保持不变。
- 运行中服务的 `scripts/probe_llm.py` 也实际通过：任务 `cc4e0084-965a-4d4b-8665-1e43c464d1c6`
  为 success，退出码 0；这条接口验证不新增新闻。
- 后端 pytest：40 passed（3.69 秒）；前端 Vitest：4 passed（1.33 秒）；
  Playwright：8 passed（7.1 秒），覆盖桌面和手机、中文标题默认显示及原文展开。
- TypeScript/Vite 构建、Ruff 检查和 47 个 Python 文件格式检查通过。
  新库完整迁移、pgvector 查询及调度锁验证通过；主库已升级到 `e62bc8c7a103`。
- 模型结果入库后的新备份恢复通过：244 条资讯、326 个原始版本、29 个任务、26 次分析尝试，
  新库恢复后 8 张业务表计数一致。配置匹配检查确认地址、密钥和模型与指定网关一致，
  `/api/settings` 响应不包含完整密钥。
- 重启后首页 20 条中文结果保持，模型配置与 120 秒超时生效，自动调度恢复并已开始下一批。
  Windows PowerShell 再次访问主页得到 200，健康状态 ok，模型已配置、调度已开启。
- 中文处理证据在 `.runtime/chinese-check.json`，桌面截图在 `.runtime/desktop-feed.png`。
  这些本机忽略文件可重新生成，不包含接口密钥。
- 中文摘要是模型概括，不是全文逐句翻译；模型质量仍需阅读核对。向量服务、Reddit、
  Windows 原生完整启动和长期稳定性仍未完成实测。

## 阶段 0（2026-10-22）

六个候选仓库均实际克隆；审阅核心文件但未执行上游应用/测试。
Docker socket 无权限，Compose 不可用；用户态 PostgreSQL 18.6 已启动。

## 阶段 1（通过）

- `uv run pytest -q`：6 passed，0.13 秒。
- `npm --prefix frontend run build`：TypeScript 与 Vite 7.3.7 构建成功。
- `uv run alembic upgrade head`：真实 PostgreSQL 初始迁移成功。
- 第一轮实际采集失败：WSL 直连连接被重置，任务正确记录 failed。
  增加环境代理支持和公网 IP 固定连接后，Fetcher 与后续完整采集均已通过。
- npm 依赖扫描发现旧测试工具问题，升级 Vitest 后 npm audit 为 0 漏洞。
- `scripts/smoke_live.py` 两轮通过：新增 30 / 0，第二轮条件请求 304，记录 ID 不变。
- 实际停止并重新启动 uvicorn，API 仍返回 30 条；原记录 ID 保留。
- Chromium 1440x1000：20 条真实记录、0 pageerror；390x844 无横向溢出。
  截图发现 WSL 无中文字体，已在用户目录安装 Noto CJK，后续截图中文字已正常显示。

## 阶段 2（通过）

- `uv run pytest -q`：10 passed。包含 HN 单条故障、GitHub 条件请求、并发任务提交、
  来源隔离、重复计数、禁用来源、重启恢复。SQLite 夹具使用单采集 worker；真实并发另测。
- `scripts/check_sources.py`：真实 PostgreSQL、3 个采集 worker，7 个来源均 success。
  Hugging Face 条件请求 0 新增；OpenAI、DeepMind、HN、vLLM、LangChain、arXiv 各新增 30。
  初始共 210 条。运行时 API 可正常查询。`.runtime/source-check.json` 保存最近一次复测结果，
  后续运行会更新该文件，不能将当前文件当作初次 210 条的快照。
- 实际源请求受网络和 feed 窗口变化影响，不保证将来的新增数量相同。

## 阶段 3 初始验收（当时未配置模型）

阶段 3：`uv run pytest -q` 为 20 passed（1.70s）；`uv run python scripts/integration_db.py`
在随机命名的隔离 PostgreSQL 数据库执行完整迁移、插入测试向量、查询 pgvector 0.8.1
余弦相似度并验证关联和双来源记录保留，成功后清理自己的测试库。
LLM HTTP 使用 MockTransport 及可控 Provider 夹具；没有真实模型调用成功的声明。
缺少本地模型凭据时 `/api/analyze` 明确返回 409，不生成假摘要和假分析任务。

## 初始化交付复测（2026-10-22，模型接入之前）

| 检查 | 实际结果 |
| --- | --- |
| 后端单元/API/任务测试 | `uv run pytest -q`：37 passed，2.91 秒 |
| Python 静态检查 | Ruff check 通过；43 个 Python 文件 format 检查通过 |
| Python 依赖 | `uv lock --check` 通过；`uv run pip check` 无冲突 |
| 前端单元测试 | Vitest：3 passed |
| 前端构建 | TypeScript 与 Vite 构建通过 |
| 浏览器真实联调 | Playwright：8 passed，6.4 秒；1440x1000 / 390x844 |
| npm 依赖扫描 | `npm audit`：0 个已报告漏洞（不等于无安全风险） |
| 真采集 | 7 个公共来源全部 success；244 条资讯；最近轮次 vLLM 重复 30、失败 0 |
| 数据库集成 | 新库执行全部 Alembic 迁移、pgvector 0.8.1 余弦查询、双来源记录保留、第二调度实例拒绝与锁丢失检测通过 |
| 备份恢复 | 244 条资讯、326 个原始版本、24 个任务；新库恢复后 8 张业务表计数一致 |
| 后台服务 | WSL 启动、停止、再次启动及 HTTP 健康检查通过；PostgreSQL 和历史资讯保持 |
| Windows 静态检查 | 实际 PowerShell 5.1 解析 Start.ps1 通过；Windows Docker Compose v5.5.1 配置解析通过 |
| Windows 访问 WSL | PowerShell 请求 `http://localhost:8000`：主页 HTTP 200、FrontierSignal 标题存在、API 状态 ok / postgresql |
| 真实 LLM 探测 | 未配置，脚本退出码 2；没有真实分析或向量服务成功结果 |

浏览器用例覆盖真实资讯检索、来源筛选、分页、详情、原始记录、来源图片加载、收藏/已读与
刷新持久化、来源开关、任务历史、非敏感设置保存和页面横向溢出检查。
运行前须有真实采集记录；用例会恢复被修改的收藏、已读和来源状态，不写入模拟新闻。
桌面截图位于 `.runtime/desktop-feed.png` 及对应详情/来源/设置截图。
这些是本次机器的忽略文件，重新运行用例可生成，不能用于证明未来的外部服务可用性。

最终联调中发现并修正了两项问题：

- vLLM 长发布说明触发 simhash 2.1.2 / NumPy 2 的 uint8 权重溢出，3 条被计为失败。
  类型提升补丁通过长重复文本精确指纹与短文本兼容回归测试，并在 30 条真实 vLLM 文本
  （最长 49,489 字符）上验证；再次真实采集 30 条重复、0 失败，原部分失败任务仍可追踪。
- 收藏 E2E 点击后立即读取数据库存在时序竞争；已改为等待 PATCH 响应和列表更新，再独立
  查询持久化结果。没有跳过断言或用固定等待掩盖失败；桌面与手机复测均通过。

当时未验证：真实 LLM/Embedding/Reddit、Windows 原生安装启动、Docker Desktop 容器运行、
X 采集、长期无人值守、海量数据性能。模型失败/重试等由受控 HTTP/Provider 夹具覆盖，
不冒充真实供应商调用。模型现状以上面的最新复测为准。Windows uv 当时未安装，Docker Desktop 引擎未启动。

## 命令（PowerShell 与 WSL 通用）

```text
uv sync --locked
uv run pytest -q
uv run ruff check backend tests scripts
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
uv run python scripts/integration_db.py
uv run python scripts/smoke_live.py
uv run python scripts/check_sources.py
uv run python scripts/verify_discovery.py
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
uv run python scripts/backup.py --verify
uv run python scripts/probe_llm.py
```

`smoke_live.py` 访问 127.0.0.1:8000，触发两轮真实采集并比较记录 ID。
`check_sources.py` 汇总所有来源结果，任何任务未成功时返回非零退出码。
`verify_discovery.py` 触发项目发现、HN、HF 模型/数据集和新增论文来源，检查真实任务与推荐。
这些命令会联网并保存真实记录；不在普通离线测试中自动运行。
`integration_db.py` 只清理自己创建的随机测试库；备份恢复也只写新库。
`probe_llm.py` 在未配置或已有模型任务占用时返回 2，真实请求失败返回 1，结构验证通过才返回 0。
不要把真实来源可用性当作离线 CI 的必要条件。Playwright 首次需要安装 Chromium；
Windows 和 WSL 的浏览器与 node_modules 应分别安装，不共享依赖目录。
