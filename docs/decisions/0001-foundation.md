# ADR 0001：模块化单体与保留原始内容

日期：2026-10-22。状态：接受。

技术项目发现、Stars 快照与推荐规则补充见 [ADR 0002](0002-technical-discovery.md)。

现有目录为空。AI News Brief 的原始记录保存时机、全局去重及自动 DDL 与需求冲突，
因此适配边界明确的小模块，建立统一 FastAPI 应用，不复制多套业务存储。

- PostgreSQL 为主库；Alembic 为唯一 schema 迁移入口；pgvector 可选分析用途。
- Collector 只返回原始标准数据，不执行 AI、写数据库或发布通知。
- 资讯在同一来源内精确去重；跨源相同 URL/内容或相似标题建立关联，保留来源。
- 原始版本单独保存；只有内容变化才重置分析状态，已有原始快照不被覆盖。
- APScheduler 定期检查数据库中来源时间；耗时任务通过有界 asyncio 工作任务执行。
  生产限制为单 worker，数据库锁防止第二个调度实例；任务状态保存在数据库。
- LLM 使用最小 Chat Completions 请求，JSON mode 需显式配置；结构化输出在本地校验。
  不对“兼容 API”的模型能力做统一假设，不强制 temperature 或特定 token 参数。
- 默认仅 loopback，校验 Host/Origin，写请求要求自定义请求头，拒绝任意 URL 抓取。
- Windows 优先 Docker Desktop PostgreSQL；当前 WSL 无 Docker 权限时使用用户态
  PostgreSQL 实例，绝不把 SQLite 验收说成 PostgreSQL 验收。
