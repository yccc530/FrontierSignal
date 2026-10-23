import { useEffect, useState } from "react";
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
  dateTime,
  type Dashboard,
  type Project,
  type Topic,
} from "../lib/api";
import { useAction, useSources } from "../lib/hooks";
import {
  Empty,
  ErrorNotice,
  SourceMark,
  sourceLabel,
} from "../components/common";
import ArticleDetail from "../components/ArticleDetail";
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
        <div className="interest-options">
          {topics.map((topic) => (
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
            </label>
          ))}
        </div>
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
  const collect = useAction();
  const patch = useAction("PATCH");
  const sources = useSources();
  const dashboard = useQuery({
    queryKey: ["recommendations", topic],
    queryFn: () =>
      api<Dashboard>(
        `/recommendations${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`,
      ),
    refetchInterval: 15000,
  });
  const data = dashboard.data;
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
            {data.sections.map((section) => (
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
                  <span className="section-count">{section.items.length}</span>
                </div>
                {section.items.length ? (
                  section.items.map((item) => (
                    <article
                      className="recommend-item"
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
                        <time>{dateTime(item.article.published_at)}</time>
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
