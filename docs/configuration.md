# 配置说明

[返回项目首页](../README.zh-CN.md) · [使用指南](usage.md) · [信息来源](data-sources.md)

## 配置在哪里

首次执行 `uv run python scripts/setup.py` 会根据 [`.env.example`](../.env.example) 创建项目根目录的私有 `.env`。脚本保留已有配置，不替换旧密码。

| 配置                                 | 保存位置                    | 生效方式                 |
| ------------------------------------ | --------------------------- | ------------------------ |
| 密钥、数据库、代理、采集预算         | `.env` 或启动进程的环境变量 | 修改后重启后端           |
| 模型地址、模型名称、超时等非敏感参数 | 系统设置写回 `.env`         | 页面保存后对后续任务生效 |
| 研究偏好                             | `.env`                      | 页面保存后生效           |
| 来源启停、频率、专项范围             | PostgreSQL                  | 页面保存后生效           |
| 推荐份额、收藏、已读、展示记录       | PostgreSQL                  | 页面操作后生效           |

进程环境变量优先于 `.env`。若某个设置由进程环境变量管理，网页修改会被拒绝，需要修改启动环境。列表配置使用 JSON，例如 `FS_EXTRA_FEED_HOSTS=["example.org"]`。

`.env`、`.runtime/` 和 `backups/` 已被 Git 忽略。不要把真实密钥写进 README、Issue、命令截图或提交内容。

## LLM 中文分析

### 必需的三项

```dotenv
FS_LLM_BASE_URL=https://your-provider.example/v1
FS_LLM_API_KEY=replace_with_your_own_key
FS_LLM_MODEL=your-model-id
```

这是占位示例。三项都需要填写为服务商实际提供的值，地址中的 `/v1` 也应以服务商路径为准。程序在基础地址后追加 `/chat/completions`，不要把完整方法地址填入 `FS_LLM_BASE_URL`。

接口使用 Bearer Key 和 Chat Completions 格式；不支持仅提供其他协议的服务自动转换。外部地址须使用 HTTPS；本机 `localhost`、`127.0.0.1` 或 `::1` 可使用 HTTP。当前配置检查要求 API Key 非空，其他兼容性仍需实际探测。

在本地修改 `.env` 后重启后端，进入「系统设置」点击「验证接口」，再到「运行任务」查看「模型接口验证」结果。也可在后端已启动时执行：

```text
uv run python scripts/probe_llm.py
```

探测会真实调用服务并产生用量，不创建新闻记录。若自动分析正在运行，等该批结束再探测；需要先单独验证时，可将 `FS_SCHEDULER_ENABLED=false` 并重启，验证完成后改回 `true` 再重启。

### 调用参数

| 变量                    | 默认值  | 说明                                 |
| ----------------------- | ------- | ------------------------------------ |
| `FS_LLM_TIMEOUT`        | `60`    | 单次请求总超时，5–180 秒             |
| `FS_LLM_MAX_RETRIES`    | `2`     | 请求层最大重试次数，0–5              |
| `FS_LLM_BATCH_SIZE`     | `5`     | 每批分析条数，1–30                   |
| `FS_LLM_JSON_MODE`      | `false` | 仅在网关确实支持时开启               |
| `FS_PREFILTER_KEYWORDS` | `[]`    | 可选分析前关键词过滤；原始资讯仍保留 |
| `FS_EMBEDDING_MODEL`    | 空      | 可选向量模型，留空关闭向量关联       |
| `FS_SEMANTIC_THRESHOLD` | `0.94`  | 向量相似阈值，0.8–1                  |

JSON mode 关闭时仍会校验模型返回的数据结构、中文字段、分类和评分。程序不默认发送 `temperature`、`max_tokens` 或 JSON Schema 参数。不要因接口宣称兼容就假设所有参数可用。

默认启用调度时，配置完整的模型服务会自动处理待分析批次。模型输入包含标题和有限正文片段；数据会发送到你选择的服务商。Token 统计只记录接口实际返回的 usage，不是账单或费用上限。可通过批量大小和来源范围控制调用规模。

向量服务使用同一基础地址与密钥，并追加 `/embeddings`；必须选择实际支持的向量模型。它是可选项，尚不具备独立真实服务验收记录，不影响基础采集、阅读和精确去重。

### 可选：导入 OpenCode 网关

只有已配置 OpenCode 的用户需要此步骤，普通用户直接填写 `.env` 即可。

```text
uv run python scripts/configure_opencode.py
```

默认读取当前系统用户目录的 `.config/opencode/opencode.json`，选择 provider 键「火山AI网关」和模型 ID `volcengine/deepseek-v4.1-flash`。脚本只导入地址、密钥和模型，不修改 OpenCode 文件，不输出密钥；仓库不提供该网关的凭据。

自定义配置位置、provider 键和模型 ID：

```text
uv run python scripts/configure_opencode.py --config /path/to/opencode.json --provider your-provider-key --model your-model-id
```

Windows 路径可改为 `C:/Users/你的用户名/.config/opencode/opencode.json`，含空格时加引号。provider 参数是 JSON 中 `provider` 对象的键，模型参数是请求 ID，不是显示名称。导入后重启后端。若密钥写成 `{env:变量名}`，需在运行导入脚本的环境中提供该变量。

## GitHub 与采集预算

公共来源不要求 X、Reddit 或模型厂商的登录账号。GitHub 可以不配置令牌访问公开内容；遇到配额限制时，可选用自己的 GitHub Token：

```dotenv
FS_GITHUB_TOKEN=replace_with_your_github_token
```

只读取公开仓库，不需要为本项目授予写入权限。不要把 Token 加入来源 URL。修改后重启，系统设置仅显示是否配置。

| 变量                             | 默认值 | 每轮作用                     |
| -------------------------------- | ------ | ---------------------------- |
| `FS_GITHUB_QUERIES_PER_RUN`      | `2`    | 项目发现查询组数，1–4        |
| `FS_GITHUB_CANDIDATES_PER_QUERY` | `10`   | 每组候选数，1–30             |
| `FS_GITHUB_TRACK_PER_RUN`        | `10`   | 已发现仓库跟踪名额，1–15     |
| `FS_GITHUB_CODE_CHECKS`          | `3`    | 代码目录检查预算，0–10       |
| `FS_GITHUB_README_CHECKS`        | `2`    | README 读取预算，0–5         |
| `FS_GITHUB_HISTORY_CHECKS`       | `8`    | 官方获星历史请求预算，0–15   |
| `FS_HN_CANDIDATES`               | `60`   | Hacker News 候选预算，10–150 |
| `FS_HN_COMMENT_LIMIT`            | `3`    | 每个采样帖子顶层评论数，0–10 |
| `FS_HF_QUERIES_PER_RUN`          | `6`    | 模型查询名额，1–6            |
| `FS_HF_CANDIDATES_PER_QUERY`     | `5`    | 每次模型查询候选数，1–10     |
| `FS_HF_CARD_CHECKS`              | `6`    | 模型卡读取预算，0–15         |

预算限制单次任务的工作量，采集间隔在「信息来源」中设置。增加预算会提高请求数和耗时，无法绕过上游配额。没有必要为了“全方向覆盖”同时提高所有参数。

GLM / Meta 优先查询使用已有 HF 名额，不增加上述默认值。默认两轮检查三个官方账号；
拉长来源间隔、缩小预算或限定主题会改变实际检查周期，查看来源页的估计与最近扫描时间。

如需减少来源请求，可把 HF 间隔改为 120 或 240 分钟，并减少 `FS_HF_CARD_CHECKS`；
这也会降低新模型和完整说明的发现速度。应用不记录流量统计。

## 数据库与运行参数

| 变量                       | 默认值 / 位置    | 说明                                                     |
| -------------------------- | ---------------- | -------------------------------------------------------- |
| `FS_DATABASE_URL`          | 由初始化脚本生成 | SQLAlchemy PostgreSQL 连接，使用 `postgresql+psycopg://` |
| `POSTGRES_PASSWORD`        | 由初始化脚本生成 | Compose 初始化数据库的密码，应与连接配置一致             |
| `FS_SCHEDULER_ENABLED`     | `true`           | 自动采集、分析和持续运行采样；关闭后手动任务仍可用       |
| `FS_COLLECTOR_CONCURRENCY` | `3`              | 采集并发数，1–8                                          |
| `FS_FETCH_TIMEOUT`         | `25`             | 单次来源请求超时，2–120 秒                               |
| `FS_TASK_TIMEOUT`          | `180`            | 单来源任务总超时，10–600 秒                              |
| `FS_MAX_ITEMS`             | `30`             | 使用此上限的采集器每轮最多条数，1–100；专项采集另有预算  |
| `FS_ALLOWED_ORIGINS`       | `.env.example`   | 允许的本机前端 Origin 列表                               |
| `FS_INTEREST_TOPICS`       | 默认八个基础方向 | 研究偏好，建议在页面中修改；合法 ID 以主题目录为准       |

部分高级变量未列在 `.env.example` 中，可按需添加，完整定义在 [`config.py`](../backend/frontiersignal/config.py)。只改 `.env` 的数据库密码不会修改已经初始化的 PostgreSQL 用户密码；不要通过删除数据卷处理密码不一致。

## 网络代理与订阅域名

**采集器代理**：未设置 `FS_OUTBOUND_PROXY` 时读取 `HTTPS_PROXY` / `https_proxy`；设置为空表示采集直连。例如：

```dotenv
FS_OUTBOUND_PROXY=http://127.0.0.1:7890
```

地址必须从运行后端的环境可达。WSL 中的 `127.0.0.1` 是否能到达 Windows 代理取决于本机网络配置，不要直接假设两边相同。

**LLM 代理**：模型请求使用 HTTPX 的进程代理环境，不读取 `FS_OUTBOUND_PROXY`。需要代理时，在启动后端的终端设置 `HTTPS_PROXY`；本机 API 与数据库应绕过代理。例如：

```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
$env:NO_PROXY = "localhost,127.0.0.1,::1"
```

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=localhost,127.0.0.1,::1
```

新增公开订阅域名，在 `.env` 中设置并重启：

```dotenv
FS_EXTRA_FEED_HOSTS=["example.org","feeds.example.org"]
```

只写主机名，不写协议或路径。订阅必须使用公开 HTTPS 地址；解析为内网、回环或链路本地 IP 会被拒绝，加入域名也不会解除这个边界。跨域重定向的目标同样需要允许。系统不自动抓取文章中的任意外链。
