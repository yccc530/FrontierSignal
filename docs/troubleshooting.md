# 故障排查

## 当前环境验证边界

- WSL2 / Ubuntu：Python 3.11、Node 22、真实 PostgreSQL 18.6、pgvector 0.8.1 已运行验证。
- WSL 的 Docker 29.1.3 socket 无权限，未安装 Compose；没有擅自修改用户组或 socket 权限。
- Windows 已安装 Docker Desktop CLI 29.8.1，但 Linux Engine 管道不存在，守护进程未运行。
- Windows PowerShell 5.1 已实际解析 Start.ps1，语法通过。Windows 侧没有找到 uv，
  因此没有执行完整原生安装启动，不把 WSL 的结果当作 Windows 原生验收。
- Windows Docker Compose v5.5.1 的 `docker compose config --quiet` 已通过；
  pgvector/pgvector:pg18 的 registry manifest 可访问，包含 amd64/arm64。
  这些检查不等于容器已成功启动。
- Windows PowerShell 实际访问 localhost:8000 主页和健康 API 成功，当前 Windows 可访问
  WSL 中的服务；这不等于在 Windows 原生 Python/Node 环境运行后端。

## 数据库无法连接

1. Docker 用户先启动 Docker Desktop，启用对应发行版的 WSL Integration。
2. `docker compose up -d db`，再 `uv run python scripts/wait_db.py`。
3. 当前 WSL 的无 root 备选：`bash scripts/install_user_postgres.sh`，然后
   `uv run python scripts/local_postgres.py`。安装脚本针对本次 Ubuntu 26.04 软件包名，
   不宣称兼容任意 Linux 发行版。
4. 数据库重启会丢失会话调度锁；应用检测后停止派发任务。数据库恢复后重启后端。

更换 `.env` 数据库密码不会自动修改已有 PostgreSQL 用户密码，也不会重建已有数据卷。
本项目不自动重置密码或删除数据卷。

## 采集失败

- 运行任务中查看具体来源和错误。HTTP 401/403 不会触发绕过或浏览器登录。
- WSL 直连外网被重置时，应用支持 HTTPS_PROXY，或在 `.env` 设置 FS_OUTBOUND_PROXY。
  空字符串表示强制直连。代理连接对目标公网 IP 固定，保留原域名 TLS 校验。
- DNS 解析到内网、loopback、链路本地地址时拒绝采集；这是来源访问边界。
- RSS 304 表示远端内容未变化，新增/重复计数均可为 0；不是失败。
- 原始正文为空可能是 feed 仅提供标题。阅读原文链接；不会伪造正文或自动抓任意外链。
- 定时任务仅在应用运行时执行。Windows/WSL 休眠期间不能采集；恢复后检查到期来源，
  RSS 滑动窗口之外的遗漏内容无法保证补齐。

## 项目热度与推荐

- 默认「增长异动」只显示有短期增长证据且达到门槛的项目；没有结果时不回填累计 Stars 高的老项目。
  新创建但尚无异动的项目在「新项目」，旧仓库和已有收藏可在「全部项目」查看。
- 官方「今日/昨日获星 (UTC)」与本地「约 1h/6h/24h 净增」是不同口径。查看统计起止时间；
  加速倍数缺失表示此前基线不足或为零，不等于没有增长。
- Stars 增长显示“待积累”：需要至少两次覆盖对应窗口的真实快照。首次发现只有累计 Stars，
  继续运行定时采集；最新快照过期或窗口基线缺失时也不会猜测增长。
- GitHub 返回 403 / 429：查看任务错误与调用频率，可降低查询/跟踪预算，或在私有 `.env`
  配置可选 GitHub token 后重启。不要将反复手动刷新当作配额限制的解决办法。
- 新项目发现按技术关键词、创建年龄、规模和候选页轮换，跟踪优先照顾年轻/近期活跃项目；不是每轮扫描所有仓库。
  本地榜单也不等于 GitHub 官网 Trending，前端显示实际观测时间与推荐依据。
- 搜索返回 incomplete_results 时任务显示部分失败，但已获取的记录会保留，不伪装为全量覆盖。
- HN 的“评论数”来自帖子元数据，详情仅保存有限顶层评论样本；无样本不代表没有讨论。
- 技术筛选或模型过滤不会删除原文。资讯库的筛选选项可以查看已保留的其他原始记录。
- X / Reddit 已退出当前产品，不需要配置凭据，也不会拖累其他来源任务。

## 模型失败

在 `.env` 填入 FS_LLM_API_KEY，模型地址和名称可在设置页配置。重启以加载新密钥。
运行 `uv run python scripts/probe_llm.py` 或设置页“验证接口”；探测不会制造新闻记录。
未配置或已有模型任务占用时返回退出码 2，失败返回 1，只有真实响应通过结构校验才返回 0。
已经开启自动分析时，可等当前批次完成后再验证；需要独立验证时，先关闭定时调度并重启。

没有强制 temperature、max_tokens、JSON schema。JSON mode 默认关闭，需供应商支持。
模型返回非 JSON、非中文摘要、未知分类或越界评分时记录失败，可逐条重试。
自动处理最多 3 个失败批次，每次内部最多 FS_LLM_MAX_RETRIES 次重试；认证/配置类
失败停止自动重试。成功记录不会在每次启动重复调用，修改模型也不会静默重跑历史记录。
Token 统计只包含服务实际返回且被记录的 usage，不是完整账单，也不估算虚构费用。

## 界面与端口

- 生产入口 `http://localhost:8000`；Vite 开发入口 `http://localhost:5173`。
- 8000 被占用时先确认占用进程，不要杀未知进程。使用其他端口时同步修改 Vite proxy 和
  FS_ALLOWED_ORIGINS。禁止用 `--workers 2`，第二个调度实例会拒绝启动。
- Linux 无中文字体时可在用户字体目录安装 Noto Sans CJK；本次截图已修复并验证。
- 前端路由使用 hash，刷新详情导航不会要求额外 Web 服务器 rewrite。
