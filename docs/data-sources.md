# 信息源

优先公开 HTTPS RSS/Atom 和官方 API，不执行登录、验证码处理、浏览器指纹模拟。

| 来源 | 接口 | 当前情况 |
| --- | --- | --- |
| Hugging Face Blog / OpenAI / DeepMind | 官方 RSS | 已真实采集；HF feed 部分条目只有标题 |
| HN | Firebase 官方 API | top / best / new 及有限公开评论采样；真实 points / 评论总数 |
| GitHub 固定仓库 | 官方 Releases API | 保留 vLLM / LangChain；ETag |
| GitHub AI 项目发现 | 官方 Search / Repositories / Releases / Contents / Star History API | 8 组主题与年龄/规模范围轮换，短期快照、官方日获星和版本跟踪 |
| Hugging Face 模型 / 数据集 | 官方 Hub API | trendingScore 候选、实际下载数/喜欢数、创建和更新时间 |
| arXiv | 官方分类 RSS | cs.AI / cs.LG / cs.CL / cs.CV；360 分钟默认频率 |
| RSSHub | 用户选择的公开 feed | 可选外部适配，不内嵌服务 |

新增采集器：实现 `collectors/base.py` 的 Collector 协议，返回 RawItem 与 Collection。
注册 `COLLECTORS` 后添加来源配置，业务存储/任务/API 不应再针对来源分支。
需要仓库持续跟踪的采集器由任务层注入数据库中待跟踪目标；其余采集器仍不依赖数据库。

RSS content 优先于 summary；日期缺失为 null；有 ETag/Last-Modified 时条件抓取。
无分页的 RSS 是“当前窗口”，不承诺恢复订阅之前或长时间停机期间的历史。
来源失败会记录任务错误，其他来源继续。HTTP 401/403 不使用绕过措施。

## 能力与限制

| 采集器 | 最新窗口 | 增量/游标 | 正文范围 |
| --- | --- | --- | --- |
| RSS / arXiv | 默认前 30 条 | ETag / Last-Modified，304 无变化 | feed 的 content / summary |
| HN | 三种榜单各最多 20 条，详情并发 4 | 榜单候选去重；平台 ID 和讨论链接保留不同讨论 | 原帖 text；最多 5 个优先技术帖各采样 3 条顶层评论，不抓站外正文 |
| GitHub Releases | 指定仓库最近 30 个发布 | ETag；不回溯全量分页历史 | release.body |
| GitHub 发现 | 默认每小时 2 组查询，每组 10 个候选 | 8 组主题与 4 种候选范围轮换；10 个跟踪名额优先年轻/近期活跃项目 | 官方简介、topics、语言、根目录代码；最近 3 个版本；每轮最多 8 个官方获星历史 |
| HF 模型 / 数据集 | 每类最多 20 个官方 trendingScore 候选 | 资源 ID 去重；元数据指标独立更新 | API description / pipeline / tags，不冒充完整模型卡 |

来源频率最小 15 分钟；arXiv 默认 360 分钟。单来源任务默认最多 180 秒，3 个来源任务并行。
GitHub token 可选，仅发往官方 API；无 token 会受公共访问限额影响。
新来源的主机需要在公开域名白名单中，额外域名由本地 FS_EXTRA_FEED_HOSTS 配置。
RSSHub 只消费用户有权使用的公开 HTTPS 订阅，本版不开放内网地址例外。

## 公开接口与限制

2026-10-22 实际调用并获得有效 JSON / feed：

- `https://api.github.com/search/repositories` 及 `/repos/{owner}/{repo}`、`/releases`、`/contents`。
- `/repos/{owner}/{repo}/stargazers/history` 返回按周聚合、按日计数的实际获星历史。
- `https://hacker-news.firebaseio.com/v0/` 下的榜单和 item 接口。
- `https://huggingface.co/api/models`、`https://huggingface.co/api/datasets`。
- `https://rss.arxiv.org/rss/cs.LG`、`cs.CL`、`cs.CV`，以及保留的 `cs.AI`。

GitHub 榜单按短期增长，不是官网 Trending 或累计 Stars 排名。检索覆盖近 7/30/90 天创建
的分组及中小项目新动向，最低 5 Stars；非 fork、未归档，按组要求最近 3/14 天 push。
低于门槛或不在本轮关键词/分页窗口的项目可能遗漏，搜索返回 incomplete_results 会保留部分失败状态。
本地 Stars 快照净增与官方 UTC 日获星分别显示，未知不补零。项目库增大时，跟踪实际间隔可能拉长。
具体窗口与排序见 [技术决策](decisions/0002-technical-discovery.md)。

HN 评论总数来自 descendants，页面明确展示实际保存的采样条数；不宣称完整评论树。
对短标题的判断可能不充分，技术规则和模型摘要都不是独立事实核查。原帖、评论、论文与模型
资源各自保留原始链接。HF 的更新与创建时间分开显示，API 标签不是完整模型性能报告。

Anthropic 本次试探的官方 `https://www.anthropic.com/rss.xml` 返回 404，尚未确认稳定官方订阅。
未创建该来源，不使用未验证的第三方 feed 或登录抓取替代。后续有明确公开接口时通过 Collector 扩展。

X / Reddit 当前均不接入：没有采集器、凭据设置或自动任务，旧库遗留来源在启动时禁用。
本机 X 来源、失败任务和私有凭据已经清理。统一采集协议保留，不影响未来明确授权的扩展。
