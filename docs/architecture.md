# 架构

[返回项目首页](../README.md) · [开发与测试](testing.md) · [数据来源](data-sources.md)

模块化单体，单进程单 worker。React 通过 `/api` 访问 FastAPI，禁止前端连接数据库。

```text
Source -> Collector -> RawItem -> Normalizer -> Storage -> PostgreSQL
             ^                       |            |
       TaskManager / APScheduler     |        RawRecord versions
                                     v
                              Article processing status
                                     |
                              AI Pipeline / Provider
                                     |
                     persisted attempts / results / related reports
                                     |
                               API -> React
```

- `collectors/` 统一 collect(Source) -> Collection。网络与数据库无耦合。
- `network.py` 来源白名单、TLS、受限重定向、DNS 公网检查、响应大小、重试与代理。
- `normalizer.py` 可空日期、正文清洗、保留语义的 URL 规范化与 SHA-256。
- `storage.py` SQLAlchemy 事务、来源内 identity/URL/content 去重、不可变原始快照。
- `tasks.py` 持久化任务、有界并发、逐条提交、来源失败隔离与重启中断标记。
- `collectors/github_discovery.py` 官方仓库搜索、受限持续跟踪与版本发现；
  `collectors/huggingface.py` 模型发现、按提交缓存的模型卡与数据集主题轮换；HN 包含有界评论采样。
  `collectors/arxiv.py` 在原 RSS 之外提供有界专项查询，复用原规范化和存储。
- `topics.py` 统一主题、查询与采集能力目录；`discovery_state.py` 记录查询组扫描证据；
  `publishers.py` 保存已核验身份和公开依据，`model_info.py` 提取来源声明的模型元数据。
- `api.py` 查询接口；`main.py` 生命周期、Host/Origin 与写请求头校验、生产静态资源。
- `analysis.py` 规则预筛选、模型处理、输入版本保护、状态与重试；`llm.py` 最小兼容请求、
  60 秒总超时、1 MB 响应上限与严格 Pydantic 校验。密钥不会写入数据库。
- `similarity.py` 跨来源候选关联；`semantic.py` 可选 Embedding 存储与 pgvector 余弦查询。
- `queries.py` 参数化检索；`management_api.py` 收藏/已读/来源/统计；
  `settings_api.py` 非敏感本地配置与数据库分类管理。
- `backend/alembic/` 版本化迁移。生产不调用 metadata.create_all。

来源配置是实际配置而不是新闻种子数据。新闻仅来自采集器，测试夹具只在 tests 中。
来源的发布时间缺失时 API 返回 null，排序可退回采集时间，两者不混淆。

PostgreSQL advisory lock 防止多个 worker 同时调度；重启时将未完成任务标记 interrupted。
原始记录已提交的数据不会随任务取消回滚。默认采集任务总时限 180 秒、HTTP 25 秒。
该初版不是多进程任务队列；部署需坚持 `--workers 1`。
来源 `config.automatic` 控制是否参与调度，不影响手动触发。X / Reddit 已移除当前采集器，
启动时禁用遗留来源，API 不再创建或展示其配置，不再要求凭据。
普通条件请求仅在整轮成功后推进游标；GitHub/HF 搜索的游标是轮换主题位置，允许部分失败后
继续轮换，失败查询下轮循环仍会覆盖，避免一个失败的质量核验阻塞所有其他主题。

## 数据表与边界

`sources` 保存配置、条件请求游标和最近状态；`articles` 保存标准化内容与当前分析；
`raw_records` 按 payload 哈希保存版本；`task_runs` 保存任务；`analysis_attempts`
保存每次模型调用的状态、输入指纹、模型、结果与可用 token usage；`categories` 为可配置分类；
`article_links` 是候选关联；`article_embeddings` 保存模型与维度对应的向量。
新增 `repositories` 保存 GitHub 稳定 ID、元数据、质量证据、观察时间与跟踪状态，
`star_snapshots` 保存按仓库/小时唯一的实际 Stars 观测。`articles.metrics` 保存来源指标，
`technical_*` 字段保存独立规则判断；模型输出不会冒充规则结果或观测数据。
`projects.py` 负责项目快照写入与增长窗口，`technical.py` 负责技术规则，
`recommendations.py` 负责只读排序与事件压缩，`discovery_api.py` 提供项目/推荐/研究偏好 API。
`momentum.py` 负责短期速度、相对规模、加速与真实仓库年龄；默认增长榜排除没有异动证据的老项目。
官方逐日获星保存为 `repositories.star_history`，原始响应保存到原始版本；不写入历史累计快照。
迁移 `8ac491d20e63` 只增加可空 JSON 字段。项目 API 默认 `pool=rising`，另提供 new / all。
迁移 `4f6a329b8102` 是增量新增；`scripts/backfill_technical.py` 重算规则、旧 HN 指标及模型元数据，
默认事务回滚仅预览，明确 `--apply` 才提交；有界分页、重复运行幂等，不访问网络或调用 LLM。

`articles.title_zh` 保存模型生成的中文标题，`title` 与 `body` 始终保存来源原文。
分析提示词版本 `analysis-6-technical-expansion` 要求中文标题、摘要和证据说明，覆盖模型、工具链与科学应用，区分规格宣称、示例与实测；缺少中文标题的
响应不能被标记为成功。前端优先显示中文内容，原文可展开，查询包含两种标题。
迁移 `e62bc8c7a103` 只增加可空字段并重建全文索引，不批量覆盖原文或生成假翻译。
自动分析按资讯页的时间排序优先处理较新的内容；未配置向量模型时不会发送向量请求。

同源平台 ID / URL / 足够长的正文哈希用于精确去重。HF 模型/数据集按资源 ID/URL 去重，
不因不同资源简介相同而合并；明确不同的模型 ID 不建立文本相似关联，也不在首页合并。
不同来源不共享文章行。
HN 使用讨论 URL 作为身份 URL，原文链接独立保留；同一外链的两场讨论不会互相覆盖，
同源或跨源均可建立候选关联。首页以精确原文 URL、内容或高置信标题关联压缩重复展示。
URL/文本/标题相似仅产生候选关联，不能证明同一事实已被多个独立来源验证。
标题/SimHash 候选窗口为最近 200 条跨源记录，精确 URL/哈希最多 30 条；非全历史聚类。
pgvector 按模型及维度隔离，默认关闭；当前使用精确余弦查询，未引入 ANN 索引。

标准化与原始快照在采集事务中写入，再进行独立 AI 处理。无法建立有效身份的畸形条目
记入任务失败计数；本版不提供畸形输入的单独收件箱。AI 失败不回滚采集事务。
原文修改使分析待处理；旧输出保留在调用审计，进行中的旧版本结果会被标记 stale。

英文/拉丁查询采用 PostgreSQL `simple` 全文向量和 GIN 索引；中文采用参数化字面查询，
没有中文分词扩展，长历史中文查询尚未针对大数据量压测。发布时间缺失时使用采集时间排序。
持久化日期有时区，客户端显示本地时间；原始来源日期字段保留在 raw JSON。

## 主题与模型扩展（B1–B8）

本批复用 `sources.config/cursor`、`articles.metrics/technical_topics`、原始记录与关联表，
B1–B7 复用 JSON，B8 当前 schema 为 `7bd38f1a90c2`。30 个主题保留旧八个 ID，
偏好上限取目录长度；`discovery_ready` / `collectors` 标明专项查询能力，不代表已有样本。
`/api/topics`、`/api/publishers` 为前端唯一目录来源；`/api/discovery/coverage` 投影实际扫描游标。

研究偏好存在本地配置，影响推荐；来源 `config.discovery_topics` 独立决定查询范围。
字段缺失表示当前采集器默认范围，空列表非法，PATCH null 恢复默认，其他来源设置保持不变。
每组游标记录最后扫描/成功时间、结果数和错误，旧版整源成功不伪造各组已扫描状态。
缩小采集范围时保留所有仍在目录内的历史扫描组，恢复范围不会擦掉旧证据。
HF 轮换有界，每轮默认 6×5 查询名额、最多 30 个去重候选、6 份 README。同轮重复请求复用，
每 12 个名额分为全站 1、主题 5、常规组织 2、重点账号 4；重点账号先轮换新建/更新，其余保留热门排序补充。
当前 GLM / Meta 三个重点账号在两轮默认预算内覆盖；没有适用重点账号时名额回到主题。
任务按主题先轮换再轮换其子查询；组织只查 author 并按声明的组织方向及用户范围过滤。
模型卡预算优先服务重点账号、常规组织与任务候选，避免全站热门列表一直占用正文预算。TaskManager 注入至多 2000 条
近期模型卡缓存元数据，采集器仍不依赖数据库；正文解析上限为 30,000 字符，截断单独标记。

`metrics.model` 包含稳定 Hub ID、发布者/核验依据、任务、声明版本/许可证、开放方式、
实际链接、Hub 创建/更新时间、官方发布日期、提交 SHA 和模型卡读取状态。
Hub 记录 `published_at=null`；列表按发布时间或首次收录排序，逐条标记实际时间含义。
模型推荐时效使用 Hub 更新时间，缺失时使用创建时间；仍无有效来源日期时不进入近期推荐。
指标观测时间不为旧模型刷新热度。
下载数/喜欢数只展示，不参与跨来源模型评分，不设 Stars 门槛。

相同 SHA 的模型卡复用正文；只拿到元数据时使用 `preserve_existing_content` 保留历史正文和分析。
新正文成功获取且内容确实改变才使旧分析失效。原始 API 与已读取模型卡保存在版本记录，
旧分析仍在调用审计；调整技术标签或提示词版本本身不重跑历史模型结果。
官方 RSS 只有明确模型与发布动作的标题进入模型流，更新日期缺失发布依据时不标为发布日期。

明确 Hub 链接可建立 `model_reference` 候选关联，模型 ID 在首页压缩重复展示；
公告、论文、模型仍是独立记录，关联不等于独立证据或精确版本一致。
前端复用资讯库与详情，添加模型/主题/发布者过滤、模型元数据和首页「模型发布与更新」。
来源页可保存/恢复采集范围、读取扫描证据；所有界面都读取后端 API，不提供演示模型数据。

B3 的 `metrics.model.task_label/modalities` 基于明确 Hub 任务，记录输入/输出和依据，不是本地运行结果。
没有任务标签的已核验 Wan 等模型系列可被归类，但不填充推断的输入输出能力。

## 内容证据与推荐观察

`content_info.py` 在既有 `metrics` 中保存资源类型、作者开发方式声明、宿主/依赖/授权原文、
科研主张/实验/基准/复现线索及明确引用。GitHub 每轮最多两份 README，不获取或执行第三方代码。
正文按 push 时间和 blob SHA 缓存，暂时无法读取时保留原文与分析；README 证据 URL 指向原始 blob。
一般数学、生物或材料内容须有 AI 方法上下文；科学论文元数据不会自动变成独立复现证明。

`identity_refs/reference_refs` 使用明确模型/论文/仓库/数据集 URL；只有直接引用对方身份才能建立
`paper_reference/resource_reference`，两个作品共同依赖某库不能因此合并。既有模型引用规则继续保留。
模型/论文链接可在首页压缩相关重复展示，详情保留独立记录；这是有界证据关联，不是全历史语义事件聚类。

`recommendation_state.py` 保存栏目条数、主题权重、重复观察小时数。推荐 GET 保持只读，前端通过
IntersectionObserver 对至少一半进入视口的卡片提交展示指纹。指纹包含内容哈希与实际模型/README 版本，
不包含 Stars、下载数、采样时间或中文翻译。近期未变内容排在未展示或已更新候选之后，不隐藏有效增长榜。
多主题按已配置方向权重分配；无候选时保留空态，不用其他主题凑齐。条数设为 0 隐藏对应栏目。

迁移新增 `workbench_state`、`recommendation_views`、`runtime_samples` 三表，以及任务来源/创建时间索引。
`observability.py` 每五分钟保存真实运行采样。24 小时覆盖必须具有真实跨度且最大间隔不超过十分钟，
采集失败和模型用量另列；覆盖一个时间窗口不等于零故障或全部查询成功。7 天增长继续按实际快照逐项目检查。
观察数据可跨重启保留；休眠/停止造成的缺口不补造采样。
`specifications` 从最多 30,000 字符正文中提取六类有界原文，保存 text/source_url/revision，
不解析成最大时长、最低显存等数值承诺。排除 YAML 与代码块；前端按原文、URL、提交合并重复展示。
缓存/暂时读取失败时保留历史规格及其原提交；历史重算可以重新提取这些字段，不重跑模型分析。
通用图片编辑、娱乐作品和素材合集不因提到创作词汇自动成为技术模型资讯；真实创作模型无需 LLM 关键词。

## 采集流量计量

迁移 `a291c7e84f60` 仅新增可空 `task_runs.network_usage`，旧任务保持 null。
每个采集任务通过 ContextVar 绑定独立计量器；`Fetcher` 在每次实际 HTTP 尝试和重定向时计数，
读取 aiohttp 的解压前/解压后响应正文计数，在失败或取消时也保留已观测部分，任务结束后持久化。
`total_raw_bytes` 是压缩传输正文大小，`total_bytes` 是解压后大小；客户端版本不支持前者时记录无法计量的响应数。
不会记录 URL、请求头、密钥或正文副本。LLM 客户端不经过此计量器。

`/api/discovery/runtime` 的 `collection_traffic` 按请求开始时的 UTC 日期汇总近七天，区分已记录、无记录与尚在运行的任务。
正常重启保留计量；进程被硬终止、提交失败时可能缺失该任务数据，缺失不填零。跨日任务可以贡献两个日期。
这是来源响应正文接收量，排除请求上传、HTTP/TLS/代理开销、DNS、LLM 和用户打开原文的网络访问，不代表完整网卡或代理账单。
