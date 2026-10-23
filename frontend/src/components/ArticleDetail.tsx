import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Bookmark, CheckCheck, RefreshCw } from "lucide-react";
import {
  api,
  articleTime,
  dateTime,
  type ArticleDetail as Detail,
} from "../lib/api";
import ModelFacts from "./ModelFacts";
import ContentFacts from "./ContentFacts";
import { displayError } from "../lib/messages";
import { useAction, useCategories, useSettings } from "../lib/hooks";
import { Metrics } from "./Intelligence";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import {
  Empty,
  ErrorNotice,
  IconButton,
  SourceMark,
  Status,
  trustNames,
  sourceLabel,
} from "./common";
const relationNames: Record<string, string> = {
  same_url: "相同原文链接",
  same_content: "相同内容",
  title_similarity: "标题相近",
  simhash: "正文相近",
  embedding: "语义相近",
  model_reference: "明确模型引用",
  paper_reference: "明确论文引用",
  resource_reference: "代码或数据集引用",
};
export default function ArticleDetail({
  id,
  onClose,
  onSelect,
}: {
  id: string | null;
  onClose: () => void;
  onSelect: (id: string) => void;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const query = useQuery({
    queryKey: ["article", id],
    queryFn: () => api<Detail>(`/articles/${id}`),
    enabled: !!id,
    refetchInterval: 5000,
  });
  const raw = useQuery({
    queryKey: ["raw", id],
    queryFn: () => api<unknown[]>(`/articles/${id}/raw`),
    enabled: !!id && showRaw,
  });
  const categories = useCategories();
  const settings = useSettings();
  const patch = useAction("PATCH");
  const retry = useAction();
  const article = query.data;
  return (
    <Dialog
      open={!!id}
      onOpenChange={(open) => {
        if (!open) {
          setShowRaw(false);
          onClose();
        }
      }}
    >
      <DialogContent className="detail-dialog">
        <DialogHeader>
          <DialogTitle className="detail-title">
            {article?.title_zh || article?.title || "资讯详情"}
          </DialogTitle>
          <DialogDescription>
            {article ? sourceLabel(article.source.name) : "正在读取内容"}
          </DialogDescription>
        </DialogHeader>
        <ErrorNotice error={query.error || patch.error || retry.error} />
        {query.isPending ? (
          <Empty title="正在读取内容" busy />
        ) : (
          article && (
            <div className="detail-scroll">
              <div className="detail-meta">
                <SourceMark
                  name={article.source.name}
                  kind={article.source.kind}
                />
                <span>{trustNames[article.source.trust]}</span>
                <span>{articleTime(article)}</span>
                <Status value={article.status} />
              </div>
              <div className="detail-actions">
                {article.original_url && (
                  <a
                    className="external-button"
                    href={article.original_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开原文
                    <ArrowUpRight size={14} />
                  </a>
                )}
                <IconButton
                  label={article.is_favorite ? "取消收藏" : "收藏"}
                  active={article.is_favorite}
                  disabled={patch.isPending}
                  onClick={() =>
                    patch.mutate({
                      path: `/articles/${id}`,
                      body: { is_favorite: !article.is_favorite },
                    })
                  }
                >
                  <Bookmark
                    size={17}
                    fill={article.is_favorite ? "currentColor" : "none"}
                  />
                </IconButton>
                <IconButton
                  label={article.is_read ? "标为未读" : "标为已读"}
                  active={article.is_read}
                  disabled={patch.isPending}
                  onClick={() =>
                    patch.mutate({
                      path: `/articles/${id}`,
                      body: { is_read: !article.is_read },
                    })
                  }
                >
                  <CheckCheck size={18} />
                </IconButton>
                {["pending", "failed"].includes(article.status) && (
                  <button
                    className="secondary-button"
                    disabled={!settings.data?.llm_configured || retry.isPending}
                    onClick={() =>
                      retry.mutate({ path: `/articles/${id}/retry` })
                    }
                  >
                    <RefreshCw size={14} />
                    {article.status === "failed" ? "重试分析" : "分析此条"}
                  </button>
                )}
              </div>
              <Metrics article={article} />
              <ModelFacts article={article} detailed />
              <ContentFacts article={article} detailed />
              {article.metrics?.authors?.length ? (
                <p className="paper-authors">
                  作者：{article.metrics.authors.join(", ")}
                </p>
              ) : null}
              {article.metrics?.updated_at && !article.metrics.model && (
                <p className="paper-authors">
                  资源更新 {dateTime(article.metrics.updated_at)}
                </p>
              )}
              {article.metrics?.discussion_url && (
                <a
                  className="discussion-link"
                  href={article.metrics.discussion_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  HN 原始讨论 <ArrowUpRight size={14} />
                </a>
              )}
              {article.source.kind === "hackernews" && (
                <details>
                  <summary>
                    评论采样（{article.metrics?.comments_sample?.length ?? 0} 条
                    / 共 {article.metrics?.comments_count ?? "未知"} 条）
                  </summary>
                  {article.metrics?.comments_sample?.length ? (
                    article.metrics.comments_sample.map((comment) => (
                      <div className="comment-sample" key={comment.id}>
                        <a
                          href={`https://news.ycombinator.com/item?id=${comment.id}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {comment.author || "匿名作者"} ·{" "}
                          {comment.time
                            ? dateTime(
                                new Date(comment.time * 1000).toISOString(),
                              )
                            : "时间未提供"}
                        </a>
                        <p>{comment.text}</p>
                      </div>
                    ))
                  ) : (
                    <p className="muted">当前未保存可用评论样本。</p>
                  )}
                </details>
              )}
              <details className="recommendation-reasons">
                <summary>
                  技术筛选：{article.technical_eligible ? "通过" : "未通过"} ·{" "}
                  {article.technical_score} 分
                </summary>
                <ul>
                  {article.technical_reasons?.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </details>
              {retry.isSuccess && (
                <p className="inline-notice">分析任务已提交</p>
              )}
              {article.analysis_error && (
                <div className="inline-error">
                  {displayError(article.analysis_error)}
                </div>
              )}
              {article.summary_zh && (
                <section className="detail-section">
                  <div className="section-label">
                    中文摘要
                    <span>
                      {article.score !== null && `关注度 ${article.score}`}
                    </span>
                  </div>
                  <p className="summary-text">{article.summary_zh}</p>
                  <div className="tag-list">
                    {article.category && (
                      <span className="subtle-tag category-tag">
                        {categories.data?.find((c) => c.id === article.category)
                          ?.label || article.category}
                      </span>
                    )}
                    {article.tags?.map((tag) => (
                      <span key={tag} className="subtle-tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="evidence-text">{article.evidence}</p>
                  <small className="muted">
                    {article.analysis_model} · {dateTime(article.analyzed_at)}
                  </small>
                </section>
              )}
              {!article.summary_zh && (
                <p className="muted">中文解读尚未生成。</p>
              )}
              <details className="detail-section" key={article.id}>
                <summary>查看原始标题与正文</summary>
                <h3>{article.title || "来源未提供标题"}</h3>
                <div className="reading-body">
                  {article.body || "该来源仅提供标题，请通过原文链接阅读。"}
                </div>
                {article.author && (
                  <p className="muted">作者：{article.author}</p>
                )}
              </details>
              {article.related.length > 0 && (
                <section className="detail-section">
                  <div className="section-label">
                    关联报道<span>{article.related.length}</span>
                  </div>
                  {article.related.map((item) => (
                    <button
                      className="related-row"
                      key={item.id}
                      onClick={() => onSelect(item.id)}
                    >
                      <span>{item.title_zh || item.title || "无标题内容"}</span>
                      <small>
                        {sourceLabel(item.source)} ·{" "}
                        {relationNames[item.method] || "相关内容"}
                      </small>
                    </button>
                  ))}
                </section>
              )}
              <section className="detail-section">
                <div className="section-label">处理记录</div>
                <p className="muted">
                  首次采集 {dateTime(article.collected_at)} · 原始版本{" "}
                  {article.raw_versions}
                </p>
                {article.attempts.length === 0 ? (
                  <p className="muted">尚无模型调用记录</p>
                ) : (
                  article.attempts.map((a) => (
                    <div className="attempt-row" key={a.id}>
                      <Status value={a.status} />
                      <span>{a.model}</span>
                      <small>
                        {dateTime(a.created_at)} · 输入 {a.input_tokens ?? "—"}{" "}
                        / 输出 {a.output_tokens ?? "—"} 词元
                      </small>
                      {a.error && (
                        <p className="inline-error">{displayError(a.error)}</p>
                      )}
                    </div>
                  ))
                )}
                {article.embedding_error && (
                  <p className="inline-error">
                    语义关联：{displayError(article.embedding_error)}
                  </p>
                )}
                <details
                  onToggle={(event) => setShowRaw(event.currentTarget.open)}
                >
                  <summary>原始记录（最近 5 个版本）</summary>
                  <ErrorNotice error={raw.error} />
                  <pre className="raw-json">
                    {raw.isPending
                      ? "读取中…"
                      : JSON.stringify(raw.data, null, 2)}
                  </pre>
                </details>
              </section>
            </div>
          )
        )}
      </DialogContent>
    </Dialog>
  );
}
