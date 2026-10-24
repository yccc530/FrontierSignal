import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  CheckCheck,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import {
  api,
  articleTime,
  dateTime,
  type Article,
  type ArticlePage,
  type Topic,
  type Publisher,
} from "../lib/api";
import {
  useAction,
  useCategories,
  useSettings,
  useSources,
  useStats,
} from "../lib/hooks";
import {
  Empty,
  ErrorNotice,
  IconButton,
  ReadIndicator,
  SourceMark,
  Status,
  sourceLabel,
} from "../components/common";
import ArticleDetail from "../components/ArticleDetail";
import { Metrics } from "../components/Intelligence";
import ModelFacts from "../components/ModelFacts";
import ContentFacts from "../components/ContentFacts";
import FeedFacets from "../components/FeedFacets";

export default function Feed({ favorite = false }: { favorite?: boolean }) {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const [draft, setDraft] = useState(q);
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => setDraft(q), [q]);
  const sources = useSources();
  const topics = useQuery({
    queryKey: ["topics"],
    queryFn: () => api<Topic[]>("/topics"),
  });
  const publishers = useQuery({
    queryKey: ["publishers"],
    queryFn: () => api<Publisher[]>("/publishers"),
  });
  const categories = useCategories();
  const stats = useStats();
  const settings = useSettings();
  const collect = useAction();
  const analyze = useAction();
  const patch = useAction("PATCH");
  const page = Math.max(1, Number(params.get("page")) || 1);
  const query = new URLSearchParams(params);
  query.set("page", String(page));
  query.set("page_size", "20");
  if (favorite) query.set("favorite", "true");
  if (!favorite && params.get("technical") !== "all")
    query.set("technical", params.get("technical") || "true");
  else query.delete("technical");
  for (const [input, output] of [
    ["from", "after"],
    ["to", "before"],
  ]) {
    const date = params.get(input);
    if (date) {
      const time = new Date(`${date}T00:00:00`);
      if (input === "to") time.setDate(time.getDate() + 1);
      if (Number.isFinite(time.getTime()))
        query.set(output, time.toISOString());
    }
    query.delete(input);
  }
  const articles = useQuery({
    queryKey: ["articles", query.toString()],
    queryFn: () => api<ArticlePage>(`/articles?${query}`),
    refetchInterval: 5000,
  });
  const change = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      value ? next.set(key, value) : next.delete(key);
      if (key !== "page") next.delete("page");
      if (
        ["source", "content_type", "publisher"].includes(key) &&
        ["citations", "downloads", "likes", "points", "comments"].includes(
          next.get("sort") || "",
        )
      )
        next.delete("sort");
      if (key === "sort" && value === "citations") {
        next.set("content_type", "papers");
        if (
          sources.data?.find((source) => source.id === next.get("source"))
            ?.kind !== "arxiv"
        )
          next.delete("source");
        next.delete("publisher");
      } else if (key === "sort" && ["downloads", "likes"].includes(value)) {
        const datasets =
          next.get("content_type") === "datasets" ||
          next.get("source") === "hf-datasets";
        next.set("content_type", datasets ? "datasets" : "models");
        next.set("source", datasets ? "hf-datasets" : "hf-models");
      } else if (key === "sort" && ["points", "comments"].includes(value)) {
        next.set("source", "hackernews");
        next.delete("content_type");
        next.delete("publisher");
      }
      return next;
    });
  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    change("q", draft.trim());
  };
  const open = (article: Article) => {
    setSelected(article.id);
    if (!article.is_read)
      patch.mutate({
        path: `/articles/${article.id}`,
        body: { is_read: true },
      });
  };
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            {favorite ? "个人收藏" : "全球人工智能情报"}
          </div>
          <h1>{favorite ? "我的收藏" : "资讯库"}</h1>
          <p>
            {favorite
              ? `${stats.data?.favorites ?? "—"} 条已收藏资讯`
              : `最近采集 ${stats.data?.last_collection ? dateTime(stats.data.last_collection) : "尚未运行"}`}
          </p>
        </div>
        <div className="heading-actions">
          <button
            className="secondary-button"
            disabled={!settings.data?.llm_configured || analyze.isPending}
            onClick={() => analyze.mutate({ path: "/analyze" })}
          >
            <Sparkles size={15} />
            分析待处理
          </button>
          <button
            className="primary-button"
            disabled={collect.isPending || !stats.data?.enabled_sources}
            onClick={() => collect.mutate({ path: "/collect" })}
          >
            <ArrowDownToLine size={15} />
            {collect.isPending ? "正在提交" : "采集最新资讯"}
          </button>
        </div>
      </section>
      <ErrorNotice
        error={
          articles.error ||
          collect.error ||
          analyze.error ||
          patch.error ||
          sources.error ||
          topics.error ||
          publishers.error ||
          categories.error
        }
      />
      {(collect.isSuccess || analyze.isSuccess) && (
        <div className="notice" role="status">
          任务已提交。
          <Link to="/tasks">
            查看运行状态 <ArrowUpRight size={12} />
          </Link>
        </div>
      )}
      <div className="search-toolbar">
        <form className="search-field" onSubmit={submitSearch}>
          <Search size={16} />
          <input
            aria-label="搜索资讯"
            value={draft}
            maxLength={200}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="搜索模型、论文、项目…"
          />
          {draft && (
            <IconButton
              label="清除搜索"
              type="button"
              onClick={() => {
                setDraft("");
                change("q", "");
              }}
            >
              <X size={14} />
            </IconButton>
          )}
          <IconButton label="搜索" type="submit">
            <ArrowRight size={16} />
          </IconButton>
        </form>
        <select
          aria-label="按来源筛选"
          value={params.get("source") || ""}
          onChange={(event) => change("source", event.target.value)}
        >
          <option value="">全部来源</option>
          {sources.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {sourceLabel(s.name)}
            </option>
          ))}
        </select>
        <IconButton
          label="更多筛选"
          active={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          <SlidersHorizontal size={17} />
        </IconButton>
      </div>
      <div className="model-filter-toolbar">
        <label>
          内容
          <select
            aria-label="资讯内容类型"
            value={params.get("content_type") || ""}
            onChange={(event) => change("content_type", event.target.value)}
          >
            <option value="">全部资讯</option>
            <option value="models">模型资讯</option>
            <option value="tools">工具与应用</option>
            <option value="projects">项目案例</option>
            <option value="workflows">创作工作流</option>
            <option value="papers">研究论文</option>
            <option value="datasets">数据集</option>
          </select>
        </label>
        <label>
          排序
          <select
            aria-label="排序方式"
            value={params.get("sort") || "published"}
            onChange={(e) => change("sort", e.target.value)}
          >
            <option value="published">最新发布 / 来源时间</option>
            <option value="oldest">最早发布 / 来源时间</option>
            <option value="collected">最近收录</option>
            <option value="score">重要性优先</option>
            <option value="technical">技术相关性</option>
            <option value="citations">论文 · 被引次数</option>
            <option value="downloads">Hub 资源 · 下载量</option>
            <option value="likes">Hub 资源 · 喜欢数</option>
            <option value="points">HN 讨论 · Points</option>
            <option value="comments">HN 讨论 · 评论数</option>
          </select>
        </label>
      </div>
      <FeedFacets
        publishers={publishers.data || []}
        topics={topics.data || []}
        categories={categories.data || []}
        params={params}
        onChange={change}
      />
      {publishers.data?.find((team) => team.id === params.get("publisher"))
        ?.author && (
        <button
          className="secondary-button"
          disabled={
            collect.isPending ||
            !sources.data?.some(
              (source) => source.id === "hf-models" && source.enabled,
            )
          }
          onClick={() =>
            collect.mutate({
              path: `/sources/hf-models/collect?publisher=${encodeURIComponent(params.get("publisher") || "")}`,
            })
          }
        >
          <ArrowDownToLine size={16} />
          采集该团队模型
        </button>
      )}
      {expanded && (
        <div className="filter-panel">
          <label>
            技术筛选
            <select
              aria-label="技术筛选"
              value={params.get("technical") || "true"}
              onChange={(event) => change("technical", event.target.value)}
            >
              <option value="true">技术内容</option>
              <option value="all">全部原始资讯</option>
              <option value="false">未通过技术筛选</option>
            </select>
          </label>
          <label>
            开始日期
            <input
              type="date"
              value={params.get("from") || ""}
              onChange={(e) => change("from", e.target.value)}
            />
          </label>
          <label>
            结束日期
            <input
              type="date"
              value={params.get("to") || ""}
              onChange={(e) => change("to", e.target.value)}
            />
          </label>
          <label>
            阅读状态
            <select
              value={params.get("read") || ""}
              onChange={(e) => change("read", e.target.value)}
            >
              <option value="">全部</option>
              <option value="false">未读</option>
              <option value="true">已读</option>
            </select>
          </label>
          <label>
            处理状态
            <select
              value={params.get("status") || ""}
              onChange={(e) => change("status", e.target.value)}
            >
              <option value="">全部</option>
              <option value="pending">待分析</option>
              <option value="analyzed">已分析</option>
              <option value="failed">分析失败</option>
              <option value="filtered">已过滤</option>
            </select>
          </label>
          <button
            className="text-button"
            onClick={() => {
              setParams({});
              setDraft("");
            }}
          >
            重置筛选
          </button>
        </div>
      )}
      <div className="feed-toolbar">
        <strong>
          {favorite ? "收藏资讯" : "全部资讯"}
          <span>{articles.data?.total ?? "—"}</span>
        </strong>
      </div>
      <div className="feed-layout">
        <section className="feed-list" aria-label="资讯列表">
          {articles.isPending && <Empty title="正在读取资讯" busy />}
          {articles.isError && (
            <Empty
              title="暂时无法读取资讯"
              detail="请检查本地服务，或稍后重试。"
            />
          )}
          {articles.data?.total === 0 && (
            <Empty
              title={favorite ? "暂无收藏" : "没有匹配的资讯"}
              detail={
                favorite
                  ? "收藏的内容会保留在这里。"
                  : "调整筛选条件，或采集新的资讯。"
              }
            />
          )}
          {articles.data?.items.map((article) => (
            <article
              key={article.id}
              className={`article-row ${article.is_read ? "is-read" : ""}`}
              data-testid="article-row"
            >
              <div className="article-meta">
                <SourceMark
                  name={article.source.name}
                  kind={article.source.kind}
                />
                <span>{sourceLabel(article.source.name)}</span>
                <span className="meta-dot">·</span>
                <time>{articleTime(article)}</time>
                <ReadIndicator read={article.is_read} />
              </div>
              <button className="article-title" onClick={() => open(article)}>
                {article.title_zh || article.title || "无标题内容"}
              </button>
              <p className="article-preview">
                {article.summary_zh || "中文摘要尚未生成，来源原文已保留。"}
              </p>
              <Metrics article={article} />
              <ModelFacts article={article} />
              <ContentFacts article={article} />
              <div className="article-footer">
                <div className="tag-list">
                  {article.category ? (
                    <span className="subtle-tag category-tag">
                      {categories.data?.find((c) => c.id === article.category)
                        ?.label || article.category}
                    </span>
                  ) : (
                    <Status value={article.status} />
                  )}
                  {article.summary_zh && (
                    <span className="subtle-tag">AI 摘要</span>
                  )}
                  {article.score !== null && (
                    <span className="score-label">
                      关注度 <b>{article.score}</b>
                    </span>
                  )}
                </div>
                <div className="row-actions">
                  <IconButton
                    label={article.is_read ? "标为未读" : "标为已读"}
                    active={article.is_read}
                    disabled={patch.isPending}
                    onClick={() =>
                      patch.mutate({
                        path: `/articles/${article.id}`,
                        body: { is_read: !article.is_read },
                      })
                    }
                  >
                    <CheckCheck size={16} />
                  </IconButton>
                  <IconButton
                    label={article.is_favorite ? "取消收藏" : "收藏"}
                    active={article.is_favorite}
                    disabled={patch.isPending}
                    onClick={() =>
                      patch.mutate({
                        path: `/articles/${article.id}`,
                        body: { is_favorite: !article.is_favorite },
                      })
                    }
                  >
                    <Bookmark
                      size={16}
                      fill={article.is_favorite ? "currentColor" : "none"}
                    />
                  </IconButton>
                  {article.original_url && (
                    <a
                      className="original-link"
                      href={article.original_url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label="查看原文"
                    >
                      原文
                      <ArrowUpRight size={13} />
                    </a>
                  )}
                </div>
              </div>
            </article>
          ))}
          <div className="pagination">
            <IconButton
              label="上一页"
              disabled={page <= 1}
              onClick={() => change("page", String(page - 1))}
            >
              <ArrowLeft size={16} />
            </IconButton>
            <span>
              第 {page} /{" "}
              {Math.max(1, Math.ceil((articles.data?.total || 0) / 20))} 页
            </span>
            <IconButton
              label="下一页"
              disabled={!articles.data || page * 20 >= articles.data.total}
              onClick={() => change("page", String(page + 1))}
            >
              <ArrowRight size={16} />
            </IconButton>
          </div>
        </section>
        <aside className="reading-panel">
          <div className="panel-label">当前观察</div>
          <div className="metric-grid">
            <div>
              <strong>{stats.data?.total ?? "—"}</strong>
              <span>收录资讯</span>
            </div>
            <div>
              <strong>{stats.data?.enabled_sources ?? "—"}</strong>
              <span>启用信源</span>
            </div>
            <div>
              <strong>{stats.data?.analyzed ?? "—"}</strong>
              <span>已分析</span>
            </div>
            <div>
              <strong>{stats.data?.unread ?? "—"}</strong>
              <span>待读资讯</span>
            </div>
          </div>
          <div className="section-label">
            信源概况
            <Link to="/sources">
              管理
              <ArrowUpRight size={12} />
            </Link>
          </div>
          {sources.data
            ?.filter((s) => s.enabled)
            .map((source) => (
              <Link className="source-summary" key={source.id} to={`/sources`}>
                <SourceMark name={source.name} kind={source.kind} />
                <div>
                  <strong>{sourceLabel(source.name)}</strong>
                  <small>
                    {source.last_success_at
                      ? dateTime(source.last_success_at)
                      : "尚无成功记录"}
                  </small>
                </div>
                <span
                  className={`status-dot ${source.last_status === "success" ? "online" : source.last_status === "failed" ? "error" : ""}`}
                />
              </Link>
            ))}
          <div className="note-block">
            <span
              className={`subtle-tag ${settings.data?.llm_configured ? "category-tag" : "warning-tag"}`}
            >
              <Sparkles size={11} />
              {settings.data?.llm_configured
                ? "AI 服务已配置"
                : "AI 服务待配置"}
            </span>
            <p>
              {settings.data?.llm_configured
                ? settings.data.llm_model
                : "配置模型后，可生成中文摘要和关注度评分。"}
            </p>
            <Link className="text-link" to="/settings">
              模型设置
              <ArrowUpRight size={13} />
            </Link>
          </div>
        </aside>
      </div>
      <ArticleDetail
        id={selected}
        onClose={() => setSelected(null)}
        onSelect={setSelected}
      />
    </>
  );
}
