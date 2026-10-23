# 架构

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
  `collectors/huggingface.py` 官方模型/数据集列表；HN 包含有界评论采样。
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
普通条件请求仅在整轮成功后推进游标；GitHub 搜索的游标是轮换主题位置，允许部分失败后
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
迁移 `4f6a329b8102` 是增量新增；`scripts/backfill_technical.py` 回填规则和旧 HN 指标，不调用 LLM。

`articles.title_zh` 保存模型生成的中文标题，`title` 与 `body` 始终保存来源原文。
分析提示词版本 `analysis-3-technical` 要求中文标题、摘要和证据说明，强调技术价值并降低营销/普通商业内容；缺少中文标题的
响应不能被标记为成功。前端优先显示中文内容，原文可展开，查询包含两种标题。
迁移 `e62bc8c7a103` 只增加可空字段并重建全文索引，不批量覆盖原文或生成假翻译。
自动分析按资讯页的时间排序优先处理较新的内容；未配置向量模型时不会发送向量请求。

同源平台 ID / URL / 足够长的正文哈希用于精确去重。不同来源不共享文章行。
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
