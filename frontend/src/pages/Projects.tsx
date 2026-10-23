import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Radar,
  Search,
  TrendingUp,
  Sparkles,
  Library,
} from "lucide-react";
import { api, type Project, type Topic } from "../lib/api";
import { useAction, useSources } from "../lib/hooks";
import { Empty, ErrorNotice, IconButton } from "../components/common";
import { ProjectHistory, ProjectItem } from "../components/Intelligence";
import ArticleDetail from "../components/ArticleDetail";

export default function Projects() {
  const [params, setParams] = useSearchParams();
  const pendingParams = useRef(params);
  useLayoutEffect(() => {
    pendingParams.current = params;
  }, [params]);
  const [draft, setDraft] = useState(params.get("q") || "");
  const [selected, setSelected] = useState<string | null>(null);
  const [history, setHistory] = useState<Project | null>(null);
  const collect = useAction();
  const patch = useAction("PATCH");
  const sources = useSources();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pool = params.get("pool") || "rising";
  const query = new URLSearchParams(params);
  query.set("page", String(page));
  query.set("page_size", "12");
  const projects = useQuery({
    queryKey: ["projects", query.toString()],
    queryFn: () =>
      api<{
        items: Project[];
        total: number;
        truncated: boolean;
        counts: Record<string, number>;
      }>(`/projects?${query}`),
    refetchInterval: 15000,
  });
  const topics = useQuery({
    queryKey: ["topics"],
    queryFn: () => api<Topic[]>("/topics"),
  });
  const change = (key: string, value: string) => {
    // Keep rapid filter changes together while the router is still rendering.
    const next = new URLSearchParams(pendingParams.current);
    value ? next.set(key, value) : next.delete(key);
    if (key !== "page") next.delete("page");
    pendingParams.current = next;
    setParams(next);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    change("q", draft.trim());
  };
  const open = (id: string) => {
    setSelected(id);
    patch.mutate({ path: `/articles/${id}`, body: { is_read: true } });
  };
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">短期增长与新项目发现</div>
          <h1>AI 开源项目</h1>
          <p>
            {projects.data?.total ?? "—"} 个项目 ·{" "}
            {pool === "rising"
              ? "已观测到增长异动"
              : pool === "new"
                ? "近 30 天创建"
                : "全部跟踪记录"}
          </p>
        </div>
        <button
          className="primary-button"
          disabled={
            collect.isPending ||
            !sources.data?.find((source) => source.id === "github-discovery")
              ?.enabled
          }
          onClick={() =>
            collect.mutate({ path: "/sources/github-discovery/collect" })
          }
        >
          <Radar size={16} /> 发现项目
        </button>
      </section>
      <ErrorNotice
        error={projects.error || topics.error || collect.error || patch.error}
      />
      {collect.isSuccess && (
        <div className="notice" role="status">
          发现任务已提交。<Link to="/tasks">查看任务</Link>
        </div>
      )}
      <div className="project-pools" role="group" aria-label="项目范围">
        {[
          { id: "rising", label: "增长异动", icon: TrendingUp },
          { id: "new", label: "新项目", icon: Sparkles },
          { id: "all", label: "全部项目", icon: Library },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            aria-pressed={pool === id}
            onClick={() => change("pool", id)}
          >
            <Icon size={15} /> {label}{" "}
            <span>{projects.data?.counts[id] ?? "—"}</span>
          </button>
        ))}
      </div>
      <div className="search-toolbar">
        <form className="search-field" onSubmit={submit}>
          <Search size={16} />
          <input
            aria-label="搜索项目"
            placeholder="项目名称或简介"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={200}
          />
          <IconButton type="submit" label="搜索项目提交">
            <ArrowRight size={16} />
          </IconButton>
        </form>
        <select
          aria-label="项目技术主题"
          value={params.get("topic") || ""}
          onChange={(event) => change("topic", event.target.value)}
        >
          <option value="">全部方向</option>
          {topics.data?.map((topic) => (
            <option key={topic.id} value={topic.id}>
              {topic.label}
            </option>
          ))}
        </select>
        <select
          aria-label="项目排序"
          value={params.get("sort") || "recommended"}
          onChange={(event) => change("sort", event.target.value)}
        >
          <option value="recommended">增长动量优先</option>
          <option value="growth24">约 24h Stars 净增</option>
          <option value="growth7">约 7d Stars 净增</option>
          <option value="stars">累计 Stars</option>
          <option value="updated">最近代码更新</option>
        </select>
      </div>
      {projects.isPending ? (
        <Empty title="正在读取项目" busy />
      ) : projects.data?.items.length ? (
        <div className="project-grid project-library">
          {projects.data.items.map((project) => (
            <ProjectItem
              key={project.id}
              project={project}
              topics={topics.data || []}
              onOpen={open}
              onHistory={setHistory}
            />
          ))}
        </div>
      ) : (
        !projects.error && (
          <Empty
            title={
              pool === "rising"
                ? "暂未观测到符合条件的增长异动"
                : "没有匹配的项目"
            }
          />
        )
      )}
      <div className="pagination">
        <IconButton
          label="上一页"
          disabled={page <= 1}
          onClick={() => change("page", String(page - 1))}
        >
          <ArrowLeft size={16} />
        </IconButton>
        <span>
          第 {page} / {Math.max(1, Math.ceil((projects.data?.total || 0) / 12))}{" "}
          页
        </span>
        <IconButton
          label="下一页"
          disabled={!projects.data || page * 12 >= projects.data.total}
          onClick={() => change("page", String(page + 1))}
        >
          <ArrowRight size={16} />
        </IconButton>
      </div>
      <ArticleDetail
        id={selected}
        onClose={() => setSelected(null)}
        onSelect={open}
      />
      <ProjectHistory project={history} onClose={() => setHistory(null)} />
    </>
  );
}
