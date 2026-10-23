import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  ChevronDown,
  Radar,
  RefreshCw,
  Save,
  SlidersHorizontal,
} from "lucide-react";
import {
  api,
  articleTime,
  dateTime,
  type Dashboard,
  type Project,
  type Topic,
} from "../lib/api";
import { useAction, useSources } from "../lib/hooks";
import {
  Empty,
  ErrorNotice,
  ReadIndicator,
  SourceMark,
  sourceLabel,
} from "../components/common";
import ArticleDetail from "../components/ArticleDetail";
import ModelFacts from "../components/ModelFacts";
import ContentFacts from "../components/ContentFacts";
import RecommendationControls from "../components/RecommendationControls";
import {
  Metrics,
  ProjectHistory,
  ProjectItem,
} from "../components/Intelligence";

function Interests({
  topics,
  initial,
}: {
  topics: Topic[];
  initial: string[];
}) {
  const [selected, setSelected] = useState(initial);
  const initialKey = initial.join(",");
  useEffect(
    () => setSelected(initialKey.split(",").filter(Boolean)),
    [initialKey],
  );
  const save = useAction("PATCH");
  return (
    <details className="interest-panel">
      <summary>
        <SlidersHorizontal size={17} /> <span>研究偏好</span>
        <span className="interest-count">已选 {selected.length} 项</span>
        <span className="interest-preview">
          {topics
            .filter((topic) => selected.includes(topic.id))
            .map((topic) => topic.label)
            .join(" · ")}
        </span>
        <ChevronDown
          size={16}
          className="interest-chevron"
          aria-hidden="true"
        />
      </summary>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate({ path: "/preferences", body: { topics: selected } });
        }}
      >
        <div className="interest-groups">
          {Array.from(
            new Set(topics.map((topic) => topic.group || "技术方向")),
          ).map((group) => (
            <fieldset key={group}>
              <legend>{group}</legend>
              <div className="interest-options">
                {topics
                  .filter((topic) => (topic.group || "技术方向") === group)
                  .map((topic) => (
                    <label key={topic.id}>
                      <input
                        type="checkbox"
                        checked={selected.includes(topic.id)}
                        onChange={(event) =>
                          setSelected(
                            event.target.checked
                              ? [...selected, topic.id]
                              : selected.filter((id) => id !== topic.id),
                          )
                        }
                      />
                      {topic.label}
                      {topic.discovery_ready === false && (
                        <small>待专项接入</small>
                      )}
                    </label>
                  ))}
              </div>
            </fieldset>
          ))}
        </div>
        <div className="form-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => setSelected(topics.map((topic) => topic.id))}
          >
            全选方向
          </button>
          <button
            className="secondary-button"
            disabled={save.isPending || !selected.length}
          >
            <Save size={14} /> 保存偏好
          </button>
          {save.isSuccess && (
            <span role="status" className="inline-notice">
              偏好已保存
            </span>
          )}
        </div>
        <ErrorNotice error={save.error} />
      </form>
    </details>
  );
}

export default function Discover() {
  const [params, setParams] = useSearchParams();
  const topic = params.get("topic") || "";
  const [selected, setSelected] = useState<string | null>(null);
  const [history, setHistory] = useState<Project | null>(null);
  const [exposureError, setExposureError] = useState<Error | null>(null);
  const recorded = useRef(new Set<string>());
  const collect = useAction();
  const patch = useAction("PATCH");
  const sources = useSources();
  const dashboard = useQuery({
    queryKey: ["recommendations", topic],
    queryFn: () =>
      api<Dashboard>(
        `/recommendations${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`,
      ),
    refetchOnWindowFocus: false,
  });
  const data = dashboard.data;
  useEffect(() => {
    if (!data || typeof IntersectionObserver === "undefined") return;
    const candidates = new Map(
      data.sections
        .flatMap((section) => section.items)
        .map((item) => [item.article.id, item.exposure]),
    );
    const observer = new IntersectionObserver(
      (entries) => {
        const items: { article_id: string; revision_hash: string }[] = [];
        for (const entry of entries) {
          const id = (entry.target as HTMLElement).dataset.articleId;
          const exposure = id ? candidates.get(id) : undefined;
          if (!entry.isIntersecting || !id || !exposure) continue;
          const key = `${id}:${exposure.revision_hash}`;
          if (recorded.current.has(key)) continue;
          recorded.current.add(key);
          items.push({ article_id: id, revision_hash: exposure.revision_hash });
        }
        if (items.length)
          void api("/recommendations/seen", {
            method: "POST",
            body: JSON.stringify({ items }),
          })
            .then(() => setExposureError(null))
            .catch((error: Error) => {
              items.forEach((item) =>
                recorded.current.delete(
                  `${item.article_id}:${item.revision_hash}`,
                ),
              );
              setExposureError(error);
            });
      },
      { threshold: 0.5 },
    );
    document
      .querySelectorAll('[data-testid="recommendation-item"]')
      .forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [data]);
  const open = (id: string) => {
    setSelected(id);
    patch.mutate({ path: `/articles/${id}`, body: { is_read: true } });
  };
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">AI 技术研究工作台</div>
          <h1>技术推荐</h1>
          <p>
            {data
              ? `${data.counts.rising} 个增长异动 · ${data.counts.new} 个近 30 天新项目`
              : "正在读取推荐"}
          </p>
        </div>
        <div className="heading-actions">
          <Link className="secondary-button" to="/feed">
            资讯库 <ArrowRight size={15} />
          </Link>
          <button
            className="primary-button"
            disabled={
              collect.isPending ||
              !sources.data?.some((source) => source.enabled)
            }
            onClick={() => collect.mutate({ path: "/collect" })}
          >
            <RefreshCw size={15} /> 更新情报
          </button>
        </div>
      </section>
      <ErrorNotice error={dashboard.error || collect.error || patch.error} />
      {collect.isSuccess && (
        <div className="notice" role="status">
          采集已提交。<Link to="/tasks">查看任务</Link>
        </div>
      )}
      {dashboard.isPending && <Empty title="正在读取技术推荐" busy />}
      {data && (
        <>
          <div className="discovery-toolbar">
            <label>
              技术主题{" "}
              <select
                aria-label="推荐技术主题"
                value={topic}
                onChange={(event) =>
                  setParams(
                    event.target.value ? { topic: event.target.value } : {},
                  )
                }
              >
                <option value="">全部方向</option>
                {data.topics.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <span>更新于 {dateTime(data.generated_at)}</span>
          </div>
          <Interests topics={data.topics} initial={data.interests} />
          <RecommendationControls topics={data.topics} />
          <ErrorNotice error={exposureError} />
          {[
            {
              id: "rising",
              title: "短期增长异动",
              window: "近期获星速度、相对增幅与加速",
              items: data.projects,
              empty: "暂未观测到明显增长",
            },
            {
              id: "new",
              title: "新项目观察",
              window: "近 30 天创建 · 与增长异动分开观察",
              items: data.emerging_projects,
              empty: "暂未发现近 30 天新项目",
            },
          ].map((section) => (
            <section
              className="recommend-section"
              key={section.id}
              aria-labelledby={`projects-${section.id}`}
              data-testid={`projects-${section.id}`}
            >
              <div className="recommend-heading">
                <div>
                  <h2 id={`projects-${section.id}`}>
                    <Radar size={18} /> {section.title}
                  </h2>
                  <span>{section.window}</span>
                </div>
                <Link to={`/projects?pool=${section.id}`}>
                  查看项目 <ArrowRight size={14} />
                </Link>
              </div>
              {section.items.length ? (
                <div className="project-grid">
                  {section.items.map((project) => (
                    <ProjectItem
                      key={project.id}
                      project={project}
                      topics={data.topics}
                      onOpen={open}
                      onHistory={setHistory}
                    />
                  ))}
                </div>
              ) : (
                <Empty title={section.empty} />
              )}
            </section>
          ))}
          <div className="recommend-section-grid">
            {data.sections
              .filter(
                (section) => data.policy?.section_limits[section.id] !== 0,
              )
              .map((section) => (
                <section
                  className="recommend-section"
                  key={section.id}
                  aria-labelledby={`section-${section.id}`}
                >
                  <div className="recommend-heading">
                    <div>
                      <h2 id={`section-${section.id}`}>{section.title}</h2>
                      <span>{section.window}</span>
                    </div>
                    {section.id === "models" ? (
                      <Link to="/feed?content_type=models">
                        全部模型资讯 <ArrowRight size={14} />
                      </Link>
                    ) : (
                      <span className="section-count">
                        {section.items.length}
                      </span>
                    )}
                  </div>
                  {section.items.length ? (
                    section.items.map((item) => (
                      <article
                        className={`recommend-item ${item.article.is_read ? "is-read" : ""}`}
                        key={item.article.id}
                        data-testid="recommendation-item"
                        data-article-id={item.article.id}
                      >
                        <div className="recommend-meta">
                          <SourceMark
                            name={item.article.source.name}
                            kind={item.article.source.kind}
                          />
                          <span>{sourceLabel(item.article.source.name)}</span>
                          <time>{articleTime(item.article)}</time>
                          <ReadIndicator read={item.article.is_read} />
                        </div>
                        <button
                          className="recommend-title"
                          onClick={() => open(item.article.id)}
                        >
                          {item.article.title_zh ||
                            item.article.title ||
                            "无标题"}
                        </button>
                        <p className="recommend-summary">
                          {item.article.summary_zh ||
                            item.article.body.slice(0, 180) ||
                            "原文未提供摘要"}
                        </p>
                        <Metrics article={item.article} />
                        <ModelFacts article={item.article} />
                        <ContentFacts article={item.article} />
                        {item.exposure?.status === "updated" && (
                          <span className="inline-notice">
                            已推荐内容有实质更新
                          </span>
                        )}
                        {item.exposure?.recent && (
                          <span className="muted">近期已展示 · 内容未变</span>
                        )}
                        {item.article.source.kind === "arxiv" && (
                          <p className="paper-authors">
                            {item.article.author ||
                              item.article.metrics.authors?.join(", ") ||
                              "作者未提供"}
                          </p>
                        )}
                        <details className="recommendation-reasons">
                          <summary>
                            推荐依据
                            {item.related_count > 0
                              ? ` · 关联 ${item.related_count} 条报道`
                              : ""}
                          </summary>
                          <ul>
                            {item.reasons.map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        </details>
                        {item.article.original_url && (
                          <a
                            className="original-link"
                            href={item.article.original_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            原始来源 <ArrowUpRight size={12} />
                          </a>
                        )}
                      </article>
                    ))
                  ) : (
                    <Empty title="当前主题暂无符合条件的内容" />
                  )}
                </section>
              ))}
          </div>
          {(data.coverage.project_candidates_truncated ||
            data.coverage.article_candidates_truncated) && (
            <p className="notice">
              推荐基于当前最多 {data.coverage.candidate_limit}{" "}
              条候选；更多历史内容可在资讯库检索。
            </p>
          )}
        </>
      )}
      <ArticleDetail
        id={selected}
        onClose={() => setSelected(null)}
        onSelect={open}
      />
      <ProjectHistory project={history} onClose={() => setHistory(null)} />
    </>
  );
}
