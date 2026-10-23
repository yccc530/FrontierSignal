# 备份与恢复

备份只包含数据库，不包含 `.env`。模型密钥和数据库连接配置应单独保存在用户自己的安全位置。
不要提交 `.env`、`.runtime/` 或 `backups/`。

PowerShell / WSL 通用：

```powershell
uv run python scripts/backup.py
uv run python scripts/backup.py --verify
```

工具优先使用 `FS_PG_BIN` 指定的 PostgreSQL 工具目录，其次本次 WSL 用户态安装，
其次 PATH 中的工具，最后使用 `docker compose exec -T db`。客户端主版本不能低于服务端。
Windows 下二进制流由 Python 写入文件，避免 PowerShell 文本重定向破坏 dump。

备份使用导出的 PostgreSQL REPEATABLE READ 快照，pg_dump 和表计数使用同一快照。
每个 `.dump` 附带同名 `.json`，记录 SHA-256、时间和各表记录数。现存输出路径不会被覆盖。
`--verify` 实际创建随机名称测试库、恢复、比较全部业务表计数，然后只清理自己创建的测试库。

恢复到一个**不存在的新数据库**：

```powershell
uv run python scripts/backup.py --restore backups\frontiersignal-<timestamp>.dump --new-database frontiersignal_restored
```

WSL 路径使用 `/`。原始 `.dump` 与 `.json` 必须同时保留。工具拒绝校验和不一致的备份，
拒绝覆盖已有数据库，不使用 `--clean`，不会自动把应用切换到恢复库。
验证新库后，停止后端，手动调整 `.env` 的数据库名，执行 `uv run alembic upgrade head`
升级恢复库到当前结构，再启动后端。旧版 8 表备份仍按其元数据核验；当前备份包含项目与
Stars 快照及推荐设置、展示记录、运行采样，共 13 张业务表。旧备份仍按各自清单校验。
必要时运行 `scripts/backfill_technical.py` 预览技术规则重算，
核对后明确加 `--apply` 才写入；重算不调用 LLM。
命令调用者需要 CREATE DATABASE 权限；本地 Compose 初始化角色具备此权限。

## 已执行的演练

2026-10-23 B4–B8 收尾（文件名使用 UTC）：
`backups/frontiersignal-20261022T211540203373Z.dump`，SHA-256
`a8cedb4b40896a8c9578a0d77f1752196cb2c28d6c0c152a057c8bd59e7ab490`。
独立恢复库的 13 张表全部一致：16 个来源、1303 条资讯、2006 个原始版本、418 个任务、
1397 次分析尝试、7 个分类、258 条关联、0 个向量、179 个仓库、278 个 Stars 快照，
以及 1 份推荐设置、4 条真实视口展示记录、3 个运行状态样本。没有覆盖原库。
该备份在恢复自动调度前生成；运行状态样本不能替代真实 24 小时观察。

迁移前备份 `pre-b4-b8-20261022T203454Z.dump` 保留 1196 条资讯。修复 HF 采集范围历史清理问题时，
仅从其独立恢复库读取原扫描记录，与新记录合并；没有回滚资讯、游标进度或用户设置。

2026-10-22：真实 PostgreSQL 18.6 从 210 条资讯、210 个原始版本、7 个来源、10 个任务
生成备份并在新库中恢复，8 张业务表计数全部一致。测试库清理后原应用库继续使用。
这是实际备份/恢复验证；不等同于 Windows Docker Desktop 上的恢复实测。

同日最终复测：`backups/frontiersignal-20261022T050353813653Z.dump`，
SHA-256 `081e0513c2bc343a58e294ec9db3132173acab687eb18bde4f433fb5b3b258d7`。
包含 8 个来源、244 条资讯、326 个原始版本、24 个任务、7 个分类；分析调用、关联、
向量表均为 0，符合未配置真实模型的实际状态。新库恢复后全部 8 张业务表计数一致。

中文模型接入后再次演练：`backups/frontiersignal-20261022T064930476333Z.dump`，
SHA-256 `9e85a44562c034cb6d54fbd633e2a8adc75fccf6358483de4bcaf75b005cfa87`。
保存 244 条资讯、326 个原始版本、29 个任务、26 次真实分析尝试；新库恢复后 8 张业务表
计数全部一致。密钥仍只在 `.env`，不包含在数据库备份中。

技术推荐优化后演练：`backups/frontiersignal-20261022T093330612669Z.dump`，
SHA-256 `de46e536fc81540a5f4c934a1b8d684f8df2146063a1f2ef2a913f50a5c91037`。
含 13 个来源、509 条资讯、734 个原始版本、99 个任务、307 次分析尝试、38 个候选项目、
48 条 Stars 快照。恢复到新库后 10 张业务表计数一致；没有覆盖主库。

增长动量重构后演练：`backups/frontiersignal-20261022T132708144870Z.dump`，
SHA-256 `477961b9d4220fdadf4f9261e0ed5a5794573935e665f2c42c32704fb2c9daf1`。
含 13 个来源、606 条资讯、914 个原始版本、149 个任务、458 次分析尝试、66 个候选仓库、
98 条本地快照；包含新增官方获星历史字段，恢复到新库后 10 张业务表计数一致。

B1/B2 扩展后演练（2026-10-23，Asia/Shanghai）：
`backups/frontiersignal-20261022T162608083487Z.dump`（文件名采用 UTC），
SHA-256 `0fb7fdd44cc3a7fd183bad6298ea3de93a0dcbe6238fac3a26d37a139025a357`。
包含 15 个来源、849 条资讯、1271 个原始版本、244 个任务、818 次分析尝试、7 个分类、
108 条候选关联、0 个向量、109 个仓库、172 条 Stars 快照。恢复到独立新库后 10 张表计数一致；
原应用数据库未覆盖，发布者和模型字段随既有 JSON 一并备份，无新增迁移。

B3 创作模型扩展及规格摘录修正后演练（2026-10-23，Asia/Shanghai）：
`backups/frontiersignal-20261022T173240673877Z.dump`（文件名采用 UTC），
SHA-256 `494bbc85940a38b0109dad16639b42d37f96a1456e29f366c8f3b2d72471e0e6`。
包含 15 个来源、1149 条资讯、1809 个原始版本、319 个任务、958 次分析尝试、7 个分类、
127 条候选关联、0 个向量、139 个仓库、222 条 Stars 快照。独立恢复库 10 张表计数全部一致，
只清理本次创建的验证库，没有覆盖应用数据库；模型任务、模态和规格原文随 JSON 保存。
