# 发现覆盖、有界补采与常用项目

[返回项目首页](../README.zh-CN.md) · [使用指南](usage.md) · [配置预算](configuration.md) · [真实验收](validation-history.md)

**有界覆盖，不是全量**。来源成功、查询完成、某天有采集活动和整个内容窗口被覆盖是不同概念。
热门论文来源和更多 arXiv 分类属于后续批次，本批没有自动订阅这些来源。

## 补采日期窗口

「信息来源 → 采集覆盖与持续观察 → 来源覆盖审计 → 有界历史补采」可以预览并提交任务。
日期按 UTC、包含起止日期，最近 90 天内每次最多 31 个日期。每组最多 5 页、每页最多 50 个候选；
专项最多选择两个已登记主题，省略时使用来源当前范围的前两个，不改写日常轮换位置。

| 来源                | 补采依据                                       | 限制                                                 |
| ------------------- | ---------------------------------------------- | ---------------------------------------------------- |
| arXiv 四个分类      | 官方 Atom API、`submittedDate`、提交时间倒序   | 复用原来源；查询及重试共享串行门，至少间隔 3 秒      |
| arXiv 专项          | 已登记的 `arxiv_query` 加日期条件              | 不自动扩展主题或分类                                 |
| GitHub 项目发现     | 官方 Search API，`created` / `pushed` 分开查询 | 创建时间保留，Stars 只记录本次实际观测               |
| 普通 RSS / 其他来源 | 当前窗口                                       | 不支持历史回补，不把当前 feed 当成停机期间的完整历史 |

任务种类为 `backfill`。即使已执行分页无错误，也只标记 `partial`，界面显示「有界补采」；全部请求失败时为 `failed`。
每页记录候选、新增、更新、重复、过滤、日期匹配与错误，前一页已提交的原文不随后续失败或超时回滚。
规则未通过的有效内容仍保留；同来源精确去重，arXiv 协议 / 版本 URL 变化按论文 ID 兼容旧记录，不合并跨来源独立行。
日期缺失或超出请求范围的有效内容保留，但不计为窗口内证据，并明确记错。
补采不推进普通 ETag、扫描游标或来源最近完整成功时间。“最多请求数”指逻辑查询页数，网络有界重试和受限跳转另计。

## 命令行

服务已运行时，以下命令只预览最近五个完整 UTC 日期，不采集、不写业务记录：

```text
uv run python scripts/backfill.py --sources arxiv-ai arxiv-lg --days 5
```

明确添加 `--apply` 才提交真实任务，例如有限日期窗口：

```text
uv run python scripts/backfill.py --sources arxiv-ai arxiv-lg arxiv-cl arxiv-cv github-discovery --start-date 2026-10-31 --end-date 2026-11-04 --pages 2 --per-page 20 --apply
```

日期是本次停机缺口的操作示例，不是新安装自动执行的补采，也不保证始终处于最近 90 天内。
GitHub 默认分别查询创建和代码更新时间，可用 `--github-date-field created` 或 `pushed` 限定。
`--topics` 接受最多两个目录主题 ID，普通分类订阅不接受专项主题参数。
只重试失败的第二页，可保留前一页成果并缩小请求范围：

```text
uv run python scripts/backfill.py --sources arxiv-ai --start-date 2026-10-31 --end-date 2026-11-04 --start-page 2 --pages 1 --per-page 20 --apply
```

起始页加页数不能超出第 5 页。重复条目不重复建行；不要反复提交绕过限额。
报告保存在忽略的 `.runtime/backfill-<UTC时间>.json`，失败、部分失败和零候选保持原样。

## 分析边界

补采新增或实质更新的内容在 `metrics.analysis_deferred_hash` 保存当前指纹，自动分析队列跳过该版本。
重复命中的已有正常内容不因此冻结。用户在单条详情明确重试分析时释放指纹；
以后普通采集取得真正的新正文版本，也可按原规则进入分析队列。
补采本身不调用 LLM / Embedding，原有普通自动分析是否运行仍由原模型配置和调度决定。

## 常用基础设施

项目页保留增长异动、新项目和全部项目，增加独立「常用基础设施」。它默认按累计 Stars、最近维护时间、稳定 ID 排序，
可切换最近代码更新，明确标注「累计指标，不代表近期增长」。许可证、官方身份、代码目录分开保存，不合成跨来源质量分。
成熟查询使用当前主题、`stars:>=10000 fork:false archived:false pushed:>=近30天`，不限制创建时间，
在累计 Stars / 最近更新和有限页码间轮换，使用显式分配的名额。
仅从常用通道收录的项目不进入增长榜、动量得分为 0；已有或以后独立命中原增长通道的项目仍须通过真实增长和技术规则。
旧项目已有的发现候选资格继续保留，不因同时归入常用范围而被抹去；旧原始记录证明曾被收录，不证明已经增长。
常用页排序始终不使用动量分。
累计 Stars 本身不加分，大项目不会用来填空榜。

`github_catalog.py` 登记 17 个固定入口：ComfyUI、llama.cpp、diffusers、transformers、vLLM、SGLang、
LangChain、LlamaIndex、AutoGen、CrewAI、Triton、DeepSpeed、Megatron-LM、Ray、MLflow、OpenAI Python SDK、Anthropic Python SDK。
复用 `github-discovery`，不新增十几个来源，也不删除已有 vLLM / LangChain release 来源。
每项有仓库链接、用途和明确别名；如 ComfyUI 原路径与 `Comfy-Org/ComfyUI` 对应同一人工登记。
固定入口在总跟踪名额内轮换，记录实际元数据、Stars 和 Releases；仓库 / 发布保留 ETag，304 复用已保存表示，
不下载相同发布正文、不伪造新版本。缓存上限为 64 个条目 / 约 2 MB，优先保留固定入口。
首次发现不倒填 Stars，代码目录 / README 仍受各自预算限制，不下载或执行第三方代码。

## 官方组织依据

以下官网页面于 2026-11-05 实际读取并有对应账号的明确 GitHub 链接；设置页和 API 公开逐账号依据。
账号身份不代表仓库质量、性能、许可证或全部渠道已核验，同名 / 社区账号不继承身份。

| GitHub 账号        | 官网依据                                                             |
| ------------------ | -------------------------------------------------------------------- |
| `openai`           | [官方开发库](https://platform.openai.com/docs/libraries)             |
| `anthropics`       | [客户端文档](https://docs.anthropic.com/en/api/client-sdks)          |
| `google-deepmind`  | [DeepMind](https://deepmind.google/)                                 |
| `facebookresearch` | [Meta 模型与库](https://ai.meta.com/resources/models-and-libraries/) |
| `QwenLM`           | [Qwen 文档](https://qwen.readthedocs.io/en/latest/)                  |
| `deepseek-ai`      | [DeepSeek](https://www.deepseek.com/)                                |
| `huggingface`      | [Transformers 文档](https://huggingface.co/docs/transformers/index)  |
| `microsoft`        | [Microsoft 开源入口](https://opensource.microsoft.com/)              |
| `mistralai`        | [Mistral 文档](https://docs.mistral.ai/)                             |
| `NVIDIA`           | [TensorRT](https://developer.nvidia.com/tensorrt)                    |

组织发现使用官方 Search API 的精确 `org:` 查询，按最近更新和页码轮换，技术筛选继续独立运行。

## 预算与覆盖审计

「系统设置 → GitHub 发现预算」显示查询总数、候选、页数、总跟踪、固定仓库、获星历史、目录与 README 名额。
成熟 / 组织查询含在总数内，固定仓库含在跟踪内，至少给普通增长保留一组。
默认保持 2 组 × 10 候选、10 跟踪、8 历史、3 页，新通道默认名额为 0。
Token 建议值只是待保存表单，不因检测到凭据自动增加请求。具体数值和持久化位置见 [配置说明](configuration.md#github-与采集预算)。

来源审计显示最近成功距今时长、近七天任务计数、启用查询组及旧范围记录的扫描时间 / 候选 / 过滤 / 错误、
无成功采集活动的 UTC 日期和独立补采记录。历史缺失值保持未知，未扫描、零候选、不完整分别展示。
活动缺口不会因后来补到几条内容变成“完整覆盖”；明细截断时明确标记，不据截断结果宣称缺失。
24 小时运行仍依赖真实采样，7 天增长仍逐项目检验实际窗口，补采不能修复过去没有进行过的 Stars 观测。

## 官方接口参考

- [arXiv API 手册](https://info.arxiv.org/help/api/user-manual.html)
- [GitHub 仓库搜索](https://docs.github.com/en/rest/search/search#search-repositories)
- [GitHub 条件请求](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests-if-appropriate)

离线测试与本机结果分别记录在 [开发与测试](testing.md) 和 [历史验收](validation-history.md)。
