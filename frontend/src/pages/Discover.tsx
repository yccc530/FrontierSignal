import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Box,
  ChevronDown,
  FileText,
  Megaphone,
  MessageSquare,
  Radar,
  RefreshCw,
  Save,
  SlidersHorizontal,
  Sparkles,
  Star,
  Wrench,
  Workflow,
} from "lucide-react";
import {
  api,
  articleTime,
  dateTime,
  type Dashboard,
  type Project,
  type Recommendation,
  type Topic,
} from "../lib/api";
import { selectFeatured } from "../lib/featured";
import { summaryText } from "../lib/chineseSummary";
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
import TopicNavigation from "../components/TopicNavigation";
import SectionTabs, {
  sectionTabId,
  type SectionTab,
} from "../components/SectionTabs";
import {
  Metrics,
  ProjectHistory,
  ProjectItem,
} from "../components/Intelligence";

const sectionLabels: Record<string, string> = {
  models: "模型",
  tools: "工具",
  workflows: "工作流",
  hot: "讨论",
  papers: "论文",
  official: "官方",
  discoveries: "发现",
};

const sectionIcons = {
  models: Box,
  tools: Wrench,
  workflows: Workflow,
  hot: MessageSquare,
  papers: FileText,
  official: Megaphone,
  discoveries: Sparkles,
};

function RecommendationItem({
  item,
  sectionId,
  sectionTitle,
  compact,
  onOpen,
}: {
  item: Recommendation;
  sectionId: string;
  sectionTitle: string;
  compact: boolean;
  onOpen: (id: string) => void;
}) {
  const article = item.article;
  return (
    <article
      className={`${compact ? "featured-item" : "recommend-item"} ${article.is_read ? "is-read" : ""}`}
      data-testid="recommendation-item"
      data-article-id={article.id}
    >
      <div className={compact ? "featured-meta" : "recommend-meta"}>
        <SourceMark name={article.source.name} kind={article.source.kind} />
        <span>{sourceLabel(article.source.name)}</span>
        {compact && (
          <span className="featured-category">
            {sectionLabels[sectionId] || sectionTitle}
          </span>
        )}
        {compact ? (
          <span className="featured-time">
            <time>{articleTime(article)}</time>
            <ReadIndicator read={article.is_read} />
          </span>
        ) : (
          <>
            <time>{articleTime(article)}</time>
            <ReadIndicator read={article.is_read} />
          </>
        )}
      </div>
      <button
        className={compact ? "featured-title" : "recommend-title"}
        onClick={() => onOpen(article.id)}
      >
        {article.title_zh || article.title || "无标题"}
      </button>
      <p className={compact ? "featured-summary" : "recommend-summary"}>
        {summaryText(
          article.summary_zh,
          article.status,
          article.analysis_error,
        )}
      </p>
      <Metrics article={article} />
      {!compact && (
        <>
          <ModelFacts article={article} />
          <ContentFacts article={article} />
        </>
      )}
      {item.exposure?.status === "updated" && (
        <span className="inline-notice">已推荐内容有实质更新</span>
      )}
      {item.exposure?.recent && (
        <span className="muted">近期已展示 · 内容未变</span>
      )}
      {compact && item.reasons[0] && (
        <p className="featured-reason">
          <strong>推荐依据</strong>
          {item.reasons[0]}
        </p>
      )}
      {!compact && article.source.kind === "arxiv" && (
        <p className="paper-authors">
          {article.author ||
            article.metrics.authors?.join(", ") ||
            "作者未提供"}
        </p>
      )}
      {!compact && (
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
      )}
      {article.original_url && (
        <a
          className="original-link"
          href={article.original_url}
          target="_blank"
          rel="noreferrer"
        >
          原始来源 <ArrowUpRight size={12} />
        </a>
      )}
    </article>
  );
}

function FeaturedProject({
  project,
  onOpen,
}: {
  project: Project;
  onOpen: (id: string) => void;
}) {
  const signal = project.momentum.signal;
  return (
    <article
      className={`featured-item ${project.is_read ? "is-read" : ""}`}
      data-testid="project-item"
      data-article-id={project.article_id}
      data-momentum={project.momentum.status}
    >
      <div className="featured-meta">
        <SourceMark name="GitHub" kind="github" />
        <span>GitHub</span>
        <span className="featured-category">
          {project.momentum.is_rising ? "增长异动" : "新项目观察"}
        </span>
        <span className="featured-time">
          <time dateTime={project.observed_at}>
            观测 {dateTime(project.observed_at)}
          </time>
          <ReadIndicator read={project.is_read} />
        </span>
      </div>
      <button
        className="featured-title"
        onClick={() => onOpen(project.article_id)}
      >
        {project.name}
      </button>
      <p className="featured-summary">
        {summaryText(
          project.summary_zh,
          project.analysis_status,
          project.analysis_error,
        )}
      </p>
      <div className="intelligence-metrics">
        <span title="累计指标，不代表近期增长">
          <Star size={14} /> 累计 Stars {project.stars.toLocaleString()}
        </span>
        <span
          title={
            signal
              ? `${dateTime(signal.start_at)} 至 ${dateTime(signal.end_at)}`
              : "暂无有效增长证据"
          }
        >
          {signal
            ? `${signal.label} ${signal.value > 0 ? "+" : ""}${signal.value.toLocaleString()}`
            : "短期增长待观测"}
        </span>
      </div>
      {project.reasons[0] && (
        <p className="featured-reason">
          <strong>推荐依据</strong>
          {project.reasons[0]}
        </p>
      )}
      <a
        className="original-link"
        href={project.url}
        target="_blank"
        rel="noreferrer"
      >
        GitHub 原仓库 <ArrowUpRight size={12} />
      </a>
    </article>
  );
}

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
  const activeTopic = data?.topics.find((item) => item.id === topic);
  const requestedTab = params.get("tab") || "featured";
  const visibleSections =
    data?.sections.filter(
      (section) => data.policy?.section_limits[section.id] !== 0,
    ) ?? [];
  const featured = data ? selectFeatured(data) : [];
  const tabItems: SectionTab[] = data
    ? [
        {
          id: "featured",
          label: "精选",
          count: featured.length,
          icon: Sparkles,
        },
        {
          id: "projects",
          label: "项目",
          count: data.projects.length + data.emerging_projects.length,
          icon: Radar,
        },
        ...visibleSections.map((section) => ({
          id: section.id,
          label: sectionLabels[section.id] || section.title,
          count: section.items.length,
          icon:
            sectionIcons[section.id as keyof typeof sectionIcons] || Sparkles,
        })),
      ]
    : [];
  const activeTab = tabItems.some((item) => item.id === requestedTab)
    ? requestedTab
    : "featured";
  const selectedSection = visibleSections.find(
    (section) => section.id === activeTab,
  );
  const changeTab = (id: string) => {
    const next = new URLSearchParams(params);
    if (id === "featured") next.delete("tab");
    else next.set("tab", id);
    setParams(next);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  };
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
          if (
            !entry.isIntersecting ||
            entry.intersectionRatio < 0.5 ||
            !id ||
            !exposure
          )
            continue;
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
      .getElementById("recommendation-panel")
      ?.querySelectorAll('[data-testid="recommendation-item"]')
      .forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [data, activeTab]);
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
          <Link
            className="secondary-button"
            to={topic ? `/feed?topic=${encodeURIComponent(topic)}` : "/feed"}
          >
            {topic ? "该方向资讯" : "资讯库"} <ArrowRight size={15} />
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
            <TopicNavigation topics={data.topics} />
            <span>更新于 {dateTime(data.generated_at)}</span>
          </div>
          <SectionTabs
            label="推荐栏目"
            panelId="recommendation-panel"
            items={tabItems}
            value={activeTab}
            onChange={changeTab}
          />
          <Interests topics={data.topics} initial={data.interests} />
          <ErrorNotice error={exposureError} />
          <div
            id="recommendation-panel"
            role="tabpanel"
            aria-labelledby={sectionTabId("recommendation-panel", activeTab)}
            tabIndex={0}
          >
            {activeTab === "featured" && (
              <section
                className="recommend-section featured-section"
                aria-labelledby="featured-heading"
              >
                <div className="recommend-heading">
                  <div>
                    <h2 id="featured-heading">
                      <Sparkles size={18} />
                      {activeTopic
                        ? `${activeTopic.label} · 精选推荐`
                        : "精选推荐"}
                    </h2>
                    <span>项目与资讯 · 跨栏目去重</span>
                  </div>
                  <span className="section-count">{featured.length} 条</span>
                </div>
                {featured.length ? (
                  <div className="featured-list">
                    {featured.map((entry) =>
                      entry.kind === "project" ? (
                        <FeaturedProject
                          key={entry.project.article_id}
                          project={entry.project}
                          onOpen={open}
                        />
                      ) : (
                        <RecommendationItem
                          key={entry.item.article.id}
                          item={entry.item}
                          sectionId={entry.section.id}
                          sectionTitle={entry.section.title}
                          compact
                          onOpen={open}
                        />
                      ),
                    )}
                  </div>
                ) : (
                  <Empty
                    title="当前主题暂无推荐内容"
                    detail="当前主题暂无符合条件的内容。"
                  />
                )}
              </section>
            )}
            {activeTab === "projects" &&
              [
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
                        <Radar size={18} />
                        {activeTopic
                          ? `${activeTopic.label} · ${section.title}`
                          : section.title}
                      </h2>
                      <span>{section.window}</span>
                    </div>
                    <Link
                      to={`/projects?pool=${section.id}${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`}
                    >
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
            {selectedSection && (
              <section
                className="recommend-section"
                aria-labelledby={`section-${selectedSection.id}`}
              >
                <div className="recommend-heading">
                  <div>
                    <h2 id={`section-${selectedSection.id}`}>
                      {activeTopic
                        ? `${activeTopic.label} · ${selectedSection.title}`
                        : selectedSection.title}
                    </h2>
                    <span>{selectedSection.window}</span>
                  </div>
                  {selectedSection.id === "models" ? (
                    <Link
                      to={`/feed?content_type=models${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`}
                    >
                      全部模型资讯 <ArrowRight size={14} />
                    </Link>
                  ) : (
                    <span className="section-count">
                      {selectedSection.items.length}
                    </span>
                  )}
                </div>
                {selectedSection.items.length ? (
                  <div className="recommend-section-grid single-section">
                    {selectedSection.items.map((item) => (
                      <RecommendationItem
                        key={item.article.id}
                        item={item}
                        sectionId={selectedSection.id}
                        sectionTitle={selectedSection.title}
                        compact={false}
                        onOpen={open}
                      />
                    ))}
                  </div>
                ) : (
                  <Empty title="当前主题暂无符合条件的内容" />
                )}
              </section>
            )}
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
