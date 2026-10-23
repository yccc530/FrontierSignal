# 信息来源与采集范围

[返回项目首页](../README.zh-CN.md) · [管理来源](usage.md#管理来源) · [配置预算与代理](configuration.md)

优先公开 HTTPS RSS/Atom 和官方 API，不执行登录、验证码处理、浏览器指纹模拟。

## 默认来源

新数据库首次启动时初始化下列 16 个来源配置。它们是可编辑的采集配置，不是预置资讯数据。
同一个模型来源会轮换多个任务与组织，不需要为每个主题再添加一个来源。

| 默认来源                                          | 配置数 | 默认间隔 | 主要内容                       |
| ------------------------------------------------- | ------ | -------- | ------------------------------ |
| GitHub AI 项目发现                                | 1      | 60 分钟  | 新项目、持续跟踪、Stars 与版本 |
| vLLM / LangChain Releases                         | 2      | 120 分钟 | 固定仓库发布说明               |
| Hugging Face 模型发现                             | 1      | 60 分钟  | 模型元数据与有界模型卡         |
| Hugging Face 技术数据集                           | 1      | 360 分钟 | 热门及主题数据集               |
| Hugging Face Blog / OpenAI News / Google DeepMind | 3      | 120 分钟 | 官方发布、研究与工程文章       |
| Google AI / NVIDIA 技术博客                       | 2      | 120 分钟 | 官方技术动态                   |
| Hacker News                                       | 1      | 120 分钟 | 技术讨论及有限评论采样         |
| arXiv cs.AI / cs.LG / cs.CL / cs.CV               | 4      | 360 分钟 | 分类订阅中的近期论文           |
| arXiv 专项工程与科学研究                          | 1      | 120 分钟 | 12 个工程、空间与科学研究方向  |

可在「信息来源」修改频率、启停和自动状态。GitHub 发现、HF 模型、HF 数据集和 arXiv 专项支持独立主题范围；普通分类 RSS 使用订阅本身的范围。关闭来源不删除历史数据。

默认未配置 Anthropic 的自动来源；X、Reddit 当前不接入。RSSHub 仅作为可选外部公开订阅消费方式，不包含在上述 16 个来源中，也不内嵌运行 RSSHub 服务。

## 接口与采集器

| 来源                                  | 接口                                                                         | 当前情况                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Hugging Face Blog / OpenAI / DeepMind | 官方 RSS                                                                     | 已真实采集；HF feed 部分条目只有标题                           |
| Google AI / NVIDIA 技术博客           | 官方 RSS                                                                     | B2 新增；已真实采集，技术筛选后推荐                            |
| HN                                    | Firebase 官方 API                                                            | top / best / new 及有限公开评论采样；真实 points / 评论总数    |
| GitHub 固定仓库                       | 官方 Releases API                                                            | 保留 vLLM / LangChain；ETag                                    |
| GitHub AI 项目发现                    | 官方 Search / Repositories / Releases / Contents / README / Star History API | 30 组主题及补充关键词，年龄/规模、短期增长与版本跟踪           |
| Hugging Face 模型                     | 官方 Hub API / README                                                        | 全站补充、任务和组织轮换，模型卡按提交缓存，指标独立记录       |
| Hugging Face 数据集                   | 官方 Hub API                                                                 | 热门补充与八组技术关键词，实际下载数/喜欢数、创建和更新时间    |
| arXiv                                 | 官方分类 RSS                                                                 | cs.AI / cs.LG / cs.CL / cs.CV；360 分钟默认频率                |
| arXiv 专项工程与科学                  | 官方 Atom 查询 API                                                           | 12 个方向，默认 120 分钟；查询间至少三秒，独立任务不影响原 RSS |
| RSSHub                                | 用户选择的公开 feed                                                          | 可选外部适配，不内嵌服务                                       |

新增来源的操作见 [使用指南](usage.md#管理来源)。新增代码级采集器：实现 `collectors/base.py` 的 Collector 协议，返回 RawItem 与 Collection。
注册 `COLLECTORS` 后添加来源配置，业务存储/任务/API 不应再针对来源分支。
需要仓库持续跟踪的采集器由任务层注入数据库中待跟踪目标；其余采集器仍不依赖数据库。

RSS content 优先于 summary；日期缺失为 null；有 ETag/Last-Modified 时条件抓取。
无分页的 RSS 是“当前窗口”，不承诺恢复订阅之前或长时间停机期间的历史。
来源失败会记录任务错误，其他来源继续。HTTP 401/403 不使用绕过措施。

## 能力与限制

| 采集器          | 最新窗口                                                     | 增量/游标                                               | 正文范围                                                                      |
| --------------- | ------------------------------------------------------------ | ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| RSS / arXiv     | 默认前 30 条                                                 | ETag / Last-Modified，304 无变化                        | feed 的 content / summary                                                     |
| HN              | 三种榜单各最多 20 条，详情并发 4                             | 榜单候选去重；平台 ID 和讨论链接保留不同讨论            | 原帖 text；最多 5 个优先技术帖各采样 3 条顶层评论，不抓站外正文               |
| GitHub Releases | 指定仓库最近 30 个发布                                       | ETag；不回溯全量分页历史                                | release.body                                                                  |
| GitHub 发现     | 默认每小时 2 组查询，每组 10 个候选                          | 30 组主题与 4 种候选范围、关键词变体轮换；10 个跟踪名额 | 官方简介、目录、最近 3 个版本；每轮最多 8 个获星历史、2 份 24,000 字符 README |
| HF 模型         | 默认每小时 6 个查询名额，每次 5 个候选；合并同轮重复全站请求 | 全站/主题/组织轮换；来源范围独立保存；资源 ID 去重      | full/cardData 元数据；每轮最多 6 份模型卡，每份保存前 30,000 字符并记录截断   |
| HF 数据集       | 每轮最多三组、每组十个候选                                   | 热门与主题轮换；资源 ID 去重、指标更新                  | API description / pipeline / tags，不冒充完整数据集卡                         |

来源频率最小 15 分钟；arXiv 默认 360 分钟。单来源任务默认最多 180 秒，3 个来源任务并行。
GitHub token 可选，仅发往官方 API；无 token 会受公共访问限额影响。
新来源的主机需要在公开域名白名单中，额外域名由本地 FS_EXTRA_FEED_HOSTS 配置。
RSSHub 只消费用户有权使用的公开 HTTPS 订阅，本版不开放内网地址例外。

## 主题与轮换

`topics.py` 注册 30 个分组主题，全部具备 GitHub 查询。HF 专项 15 个方向，包含基础与创作模型、
3D/CAD、世界模型、机器人、科学计算、数学、材料和生物。注册/启用查询不等于获得该方向全部样本。
首页研究偏好只影响推荐；来源页保存的是独立 `discovery_topics`，可恢复默认范围。
每组显示最后扫描/成功时间、候选数和错误；查询成功但零候选不等于失败，也不等于全量覆盖。
每组新增/更新/重复按其命中记录计数，跨组可能重叠；来源任务总数按入库记录去重。

HF 默认共 61 个扫描组：全站 1 组、任务/关键词 46 组、组织 14 组。每轮六个查询名额，
全站 1、主题 4、组织 1；模型卡优先分配给组织和主题候选。主题先按 15 个方向公平轮换，
再轮换该方向的子查询；避免因某一方向查询数量多而挤占其他方向。一次最多保留 30 个不同候选。
默认 60 分钟间隔下，约四轮触及全部主题，十四轮触及全部组织，最多约 27 轮覆盖全部子查询。
这是成功连续运行的轮换上界估计，不是内容延迟保证；停机、访问失败和自定义预算会改变周期。
主题/组织排序在创建时间、更新时间和趋势间轮换；组织查询只指定 author，在本地按组织方向和用户范围
筛选实际返回模型，不给所有组织强加 text-generation。扫描组完成不代表每个排序或全部分页都已扫完。
当前每组只取有界首页，不承诺穷尽所有模型；用户保存的自定义范围不会被升级覆盖。
新建 HF 模型来源默认 60 分钟；旧数据库可能仍保留早期的 360 分钟设置，可在页面调整。启动种子不会覆盖已有频率或范围。

## B4–B7 新增入口与限制

- 3D：Hub text-to-3d/image-to-3d、Hunyuan3D/TRELLIS；CAD：Text2CAD/text-to-cad。
- 世界模型：world-model/Cosmos-Predict；具身：robotics/OpenVLA/diffusion-policy。
  腾讯 Hub 认证组织已核验；OpenVLA 官方仓库 README 明确指向同名 Hub。Microsoft TRELLIS 官方代码链接也已核对。
- Vibe：coding agent/AI code editor、vibe-coding 及作者声明关键词；设计：screenshot-to-code/design-to-code/AI UI；工作流：ComfyUI。
  第一轮 GitHub 设计查询零候选；作品开发方式没有可用 README 作者声明时不贴 Vibe 作品标签。
- 工具链：browser agent/computer use、MCP/agent skills/claude skills、LLM observability/AI code review、local-llm、AI knowledge/research assistant。
  关键词变体随主题轮换，不声称本次已逐个验证所有变体；source 扫描组以主题为单位。
- 科学模型：neural-operator/physics-informed、DeepSeek-Prover/Qwen-Math、MatterGen/MatterSim、ESM2/protein。
  关键词命中还须通过实际任务/标签检查，不能因搜索接口返回就强制归类。
- 专项论文结合 cs.LG/AI/CL/LO/CV/GR/RO、physics.comp-ph、cond-mat.mtrl-sci、q-bio.BM 与 AI 方法关键词。
  原文摘要没有匹配技术证据的候选被计为过滤，不把整个自然科学分类都视为 AI。
- 数据集保留热门补充，加入 fine-tuning/retrieval/benchmark/lerobot/physics/math/materials/protein。
  当前仅保存 API 元数据，不下载数据集文件或模型权重。

默认 GitHub 主题轮换约 15 小时（关键词、年龄、页码组合需更多轮），专项论文约 12 小时，数据集约 18 小时。
来源页显示当前预算/估计及真实扫描结果；关闭自动采集、停机或限额时不会补写成功状态。
完整请求、首轮计数与缺口见 [历史验收记录](validation-history.md)；开发环境原始报告位于未提交的 `.runtime/b4-b8-live.json`。

下表身份依据于 2026-10-22 实际核对；B2 查询与持久化在 10 月 22–23 日验证。
统一台账为 `publishers.py`，`/api/publishers` 返回公开依据，不包含任何凭据。

| 发布者     | 已接入入口                                                          | 身份核验与范围                                                                           |
| ---------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| OpenAI     | HF `openai`；原 OpenAI RSS                                          | Hub 组织 overview 返回已认证；模型名称含 GPT 不自动判为官方                              |
| Google     | HF `google`；DeepMind RSS；`https://blog.google/technology/ai/rss/` | Hub 已认证组织；Google AI RSS HTTP 200，20 条真实入库                                    |
| 阿里 Qwen  | HF `Qwen`                                                           | `https://qwen.readthedocs.io/en/latest/` 链接至该 Hub 组织；不宣称其 Hub 认证字段为 true |
| DeepSeek   | HF `deepseek-ai`                                                    | Hub 已认证组织；其他用户名下同名/衍生模型保持社区来源                                    |
| Mistral AI | HF `mistralai`                                                      | Hub 已认证组织                                                                           |
| Microsoft  | HF `microsoft`                                                      | Hub 已认证组织；`https://blogs.microsoft.com/ai/feed/` 返回 410，未启用该 RSS            |
| NVIDIA     | `https://developer.nvidia.com/blog/feed/`                           | 官方技术 RSS HTTP 200；限窗口前 30 条，本轮全部入库；未增加 NVIDIA Hub 专项              |

Hub 认证依据来自 `https://huggingface.co/api/organizations/{author}/overview`。
六个 Hub 组织查询均真实成功且已存模型记录；这些组织仍可发布无关任务，入库按实际主题筛选。
组织身份不等于独立性能评测；不自动把模型卡里引用的仓库当作官方实现。
`publisher_verified` 表示台账中的身份依据已核对，不等于 Hub 的 `isVerified` 徽标；具体方法保存在公开依据中。

## 模型厂商第一批：GLM 与 Meta（2026-10-23）

在原 `hf-models` 中新增三个账号查询，不重复创建来源或下载权重：

| 发布团队 | Hub author | 身份依据 |
| --- | --- | --- |
| 智谱 / Z.ai | `zai-org` | 官方 `zai-org/GLM-4.5` 仓库 README 交叉链接；本次 overview 的 `isVerified=false`，不标为 Hub 徽标认证 |
| Meta Llama | `meta-llama` | 组织 overview 返回 `isVerified=true` |
| Meta 研究模型 | `facebook` | 组织 overview 返回 `isVerified=true`，归入同一 Meta 筛选，保留该账号独立核验链接 |

GLM、ChatGLM、Llama 及明确的创作/视觉系列可提供分类线索，但不根据名称猜测任务模态、性能或开放权限。
未将整个 THUDM 组织归为智谱，也不把社区同名/量化版本自动认作官方。原始模型 ID 是去重键。

当前 17 个厂商登记对应 17 个 Hub 账号、64 个模型查询组；NVIDIA 仍仅博客入口，Meta 有两个账号。
每轮保持默认 6 次列表查询、每次最多 5 个候选、最多 6 份模型卡。每 12 个名额按全站 1、主题 5、常规账号 2、重点账号 4 分配；
三个重点账号在任意连续两轮默认采集中均获一次扫描机会。重点账号只轮换新建/更新排序，其他主题和组织仍持续轮换。
默认一小时一次，因此无停机、失败或自定义范围限制时，两个轮次约两小时；这不是完整目录扫描或零漏报承诺。
如自定义范围与厂商方向无交集，该厂商不参与查询。减少每轮查询数或拉长来源间隔会相应拉长检查周期。

同一 SHA 的模型卡继续复用缓存，旧扫描历史与原文保持。来源页面显示优先账号、最后成功时间和实际错误。
第一批两轮真实任务均成功，新增 24、重复 23、失败 0，三个账号都有扫描和入库记录；
此为历史验收结果，不代表每次运行的新增数量。

历史登记修正可先运行 `uv run python scripts/backfill_technical.py --publisher zai` 或 `--publisher meta`，
核对预览后追加 `--apply`；只处理对应已保存 Hub 原始记录，不重新调用 LLM。
本批没有新增 GLM/Meta 官网新闻爬取或闭源模型发布接口；这些入口需后续独立核验。

## B3 创作模型入口（2026-10-23）

复用同一 `hf-models` 来源，不为三个方向重复建库或重复创建源；全站、任务与组织候选按模型 ID 合并。
以下 11 种任务参数都实际返回了与任务匹配的 Hub 记录：

| 方向       | Hub pipeline_tag                                                            | 补充名称检索                                      |
| ---------- | --------------------------------------------------------------------------- | ------------------------------------------------- |
| 图像       | text-to-image、image-to-image、image-text-to-image                          | inpainting、super-resolution、subject-consistency |
| 视频       | text-to-video、image-to-video、image-text-to-video、video-to-video          | video-editing、camera-control                     |
| 语音与音频 | automatic-speech-recognition、text-to-speech、text-to-audio、audio-to-audio | musicgen、realtime-speech、sound-effects          |

共 19 个新增任务/关键词组，连续 25 轮真实采集均成功。`subject-consistency` 的本轮候选为 0，
不宣称这一关键词已得到真实样本；其余 18 组有返回。名称检索只覆盖名称匹配范围，不等于搜索完整 README。
音乐、语音与音效共享 audio 主题，细分任务在模型卡中展示；实时能力须有原文，不能仅由模型名推断。
GitHub 增加 text-to-image、video-generation、text-to-speech 主题发现，沿用原年龄/规模与增长排序。

新增六个组织的身份依据如下；代码仓库交叉链接与 Hub 认证分开记录，不混淆为同一种验证。

| 发布者 / Hub author                   | 方向       | 本轮身份依据                                                                                                               |
| ------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------- |
| Black Forest Labs / black-forest-labs | 图像       | Hub organization overview 的 isVerified=true                                                                               |
| Stability AI / stabilityai            | 图像、音频 | `https://github.com/Stability-AI/stable-audio-tools` README 链接至 stabilityai；generative-models 仓库亦提供同组织模型链接 |
| 阿里 Wan / Wan-AI                     | 视频       | `https://github.com/Wan-Video/Wan2.2` README 链接至 Wan-AI                                                                 |
| Lightricks / Lightricks               | 视频       | `https://github.com/Lightricks/LTX-Video` README 链接至同名 Hub 模型                                                       |
| FunAudioLLM / FunAudioLLM             | 音频       | `https://github.com/FunAudioLLM/CosyVoice` README 链接至同名 Hub 模型；不宣称拥有 Hub 认证徽标                             |
| ACE-Step / ACE-Step                   | 音频、音乐 | `https://github.com/ACE-Step/ACE-Step` README 链接至同名 Hub 模型；不宣称拥有 Hub 认证徽标                                 |

部分 Wan 最新模型没有 pipeline_tag；仅对已核验组织的明确模型系列补充主题归类，
任务与输入输出模态仍保持未知。社区使用相同名字不会因此获得官方身份。
新增组织 API 和模型卡均已进入实际轮换。前期部分探测因 DNS 返回非公网地址被拒绝，后续复测恢复；
没有关闭 DNS/TLS 校验或改用登录抓取。GitHub 第二轮部分历史/代码核验被限额阻止，已保存 partial。

模型卡只从实际提交 SHA 对应的官方 Hub README 读取，相同提交复用缓存。
读取失败、配额不足或没有 README 时仍保存元数据，保留已有正文和中文分析；
若正文发生变化再进入现有分析队列。不下载权重、不执行仓库代码、不购买模型厂商 API。
权重权限由文件与 gated 字段判断；许可证只保留来源声明。提交 SHA、模型版本分别保存，
缺少明确版本/发布日期/API 可用性时保持未知。Hub 创建/更新时间不能作为官方发布日期。
官方 RSS 的公告/预览/可用/更新标签来自标题中的明确措辞，只表示来源声明。
详情保留模型卡、实际权重目录、代码引用和论文引用；不存在的链接不生成。
规格摘录最多六类，每类保留一段原文并绑定源 URL/模型卡提交；跳过 YAML、代码块及媒体标签，
相同原文在界面合并。它们是来源线索，可能是训练设置、示例或带否定的说明，不转换为最大能力。

## 已验证接口与限制

以下为带日期的历史接口验证，不能保证第三方服务始终可用；你本机的最新结果以运行任务和扫描覆盖为准。

2026-10-22 至 2026-10-23 实际调用并获得有效 JSON / feed：

- `https://api.github.com/search/repositories` 及 `/repos/{owner}/{repo}`、`/releases`、`/contents`。
- `/repos/{owner}/{repo}/stargazers/history` 返回按周聚合、按日计数的实际获星历史。
- `https://hacker-news.firebaseio.com/v0/` 下的榜单和 item 接口。
- `https://huggingface.co/api/models` 的 `pipeline_tag` / `search` / `author`、`full` / `cardData`
  及 `createdAt` / `lastModified` / `trendingScore` 排序；`https://huggingface.co/api/datasets`。
- `https://huggingface.co/{namespace}/{model}/resolve/{commit}/README.md` 的实际公开模型卡。
- `https://blog.google/technology/ai/rss/`、`https://developer.nvidia.com/blog/feed/`。
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
统一采集协议保留，不影响未来明确授权的扩展。
