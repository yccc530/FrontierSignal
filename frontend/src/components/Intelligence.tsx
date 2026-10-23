import {
  ArrowUpRight,
  Bookmark,
  Eye,
  GitFork,
  History,
  MessageSquare,
  Sparkles,
  Star,
  TrendingUp,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  api,
  dateTime,
  type Article,
  type Project,
  type StarGrowth,
  type Topic,
} from "../lib/api";
import { useAction } from "../lib/hooks";
import { Empty, ErrorNotice, IconButton, ReadIndicator } from "./common";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";

export function Metrics({ article }: { article: Article }) {
  const metrics = article.metrics || {};
  return (
    <div className="intelligence-metrics">
      {typeof metrics.points === "number" && (
        <span>{metrics.points.toLocaleString()} points</span>
      )}
      {typeof metrics.comments_count === "number" && (
        <span>
          <MessageSquare size={14} /> {metrics.comments_count.toLocaleString()}{" "}
          条评论
        </span>
      )}
      {typeof metrics.downloads === "number" && (
        <span>下载 {metrics.downloads.toLocaleString()}</span>
      )}
      {typeof metrics.likes === "number" && (
        <span>喜欢 {metrics.likes.toLocaleString()}</span>
      )}
      {metrics.categories?.slice(0, 4).map((category) => (
        <span key={category}>{category}</span>
      ))}
    </div>
  );
}

export function Growth({
  label,
  growth,
}: {
  label: string;
  growth: StarGrowth;
}) {
  const value = growth.value;
  return (
    <div
      title={`${growth.reason}${growth.window_hours !== null ? `；实际跨度 ${growth.window_hours} 小时` : ""}`}
    >
      <dt>{label}净增</dt>
      <dd className={value !== null && value > 0 ? "growth-positive" : ""}>
        {value === null ? (
          <span className="unknown-growth">待积累</span>
        ) : (
          `${value > 0 ? "+" : ""}${value.toLocaleString()}`
        )}
      </dd>
    </div>
  );
}

export function ProjectItem({
  project,
  topics,
  onOpen,
  onHistory,
}: {
  project: Project;
  topics: Topic[];
  onOpen: (id: string) => void;
  onHistory: (project: Project) => void;
}) {
  const patch = useAction("PATCH");
  const { momentum } = project;
  const signal = momentum.signal;
  const { label, icon: MomentumIcon } = {
    surging: { label: "加速上升", icon: TrendingUp },
    rising: { label: "快速增长", icon: ArrowUpRight },
    new: { label: "新项目观察", icon: Sparkles },
    watching: { label: "持续跟踪", icon: Eye },
  }[momentum.status];
  return (
    <article
      className={`project-item ${project.is_read ? "is-read" : ""}`}
      data-testid="project-item"
      data-momentum={momentum.status}
    >
      <div className="project-heading">
        <span className="source-mark source-github">GH</span>
        <button
          className="project-name"
          onClick={() => onOpen(project.article_id)}
        >
          {project.name.includes("/") ? (
            <>
              {project.name.slice(0, project.name.indexOf("/") + 1)}
              <wbr />
              {project.name.slice(project.name.indexOf("/") + 1)}
            </>
          ) : (
            project.name
          )}
        </button>
        <ReadIndicator read={project.is_read} />
        <Tooltip>
          <TooltipTrigger asChild>
            <a
              className="icon-button"
              href={project.url}
              target="_blank"
              rel="noreferrer"
              aria-label={`打开 ${project.name} GitHub`}
            >
              <ArrowUpRight size={17} />
            </a>
          </TooltipTrigger>
          <TooltipContent>打开 GitHub</TooltipContent>
        </Tooltip>
      </div>
      <div className="momentum-meta">
        <span className={`momentum-state momentum-${momentum.status}`}>
          <MomentumIcon size={14} aria-hidden="true" />
          {label}
        </span>
        {momentum.acceleration !== null && (
          <span>速度 {momentum.acceleration.toFixed(2)} 倍</span>
        )}
        {momentum.is_new && <span>创建 {momentum.age_days} 天</span>}
      </div>
      <p className="project-description">
        {project.summary_zh || project.description || "项目未提供简介"}
      </p>
      <div className="technical-tags">
        {project.topics.slice(0, 3).map((id) => (
          <span key={id}>
            {topics.find((topic) => topic.id === id)?.label || id}
          </span>
        ))}
        {project.language && (
          <span className="language-tag">{project.language}</span>
        )}
      </div>
      <dl className="project-numbers">
        <div
          className="project-metric-primary"
          title={
            signal
              ? `${dateTime(signal.start_at)} 至 ${dateTime(signal.end_at)}`
              : "暂无有效增长证据"
          }
        >
          <dt>{signal?.label || "短期增长"}</dt>
          <dd className={signal && signal.value > 0 ? "growth-positive" : ""}>
            {signal ? (
              `${signal.value > 0 ? "+" : ""}${signal.value.toLocaleString()}`
            ) : (
              <span className="unknown-growth">待观测</span>
            )}
          </dd>
        </div>
        <div>
          <dt title="观测窗口内每小时平均 Stars 变化">平均 / 小时</dt>
          <dd>
            {signal ? (
              signal.rate_per_hour.toFixed(2)
            ) : (
              <span className="unknown-growth">未知</span>
            )}
          </dd>
        </div>
        <div>
          <dt>
            <Star size={14} /> 累计 Stars
          </dt>
          <dd>{project.stars.toLocaleString()}</dd>
        </div>
      </dl>
      {project.reasons.length > 0 && (
        <p className="project-reason-preview">
          <strong>关注理由</strong>
          {project.reasons[0]}
        </p>
      )}
      <details className="recommendation-reasons">
        <summary>
          增长依据 · {project.recommendation_score.toFixed(0)} 分
        </summary>
        <ul>
          {project.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        {project.code_evidence.map((value) => (
          <p key={value}>{value}</p>
        ))}
        {signal && (
          <p>
            统计窗口 {dateTime(signal.start_at)} 至 {dateTime(signal.end_at)}
            {signal.relative_percent !== null &&
              ` · ${signal.relative_label} ${signal.relative_percent}%`}
          </p>
        )}
        <dl className="project-numbers project-numbers-detail">
          <Growth label="约24h " growth={project.growth_24h} />
          <Growth label="约7d " growth={project.growth_7d} />
        </dl>
        <p>
          创建 {dateTime(project.created_at)} · 采样{" "}
          {dateTime(project.observed_at)}
        </p>
        <p>
          <GitFork size={12} /> {project.forks.toLocaleString()} forks ·{" "}
          {project.license || "未声明许可证"}
        </p>
        {project.latest_release && (
          <a
            href={project.latest_release.html_url}
            target="_blank"
            rel="noreferrer"
          >
            版本 {project.latest_release.tag_name} ·{" "}
            {dateTime(project.latest_release.published_at)}
          </a>
        )}
      </details>
      <div className="project-footer">
        <span>代码更新 {dateTime(project.pushed_at)}</span>
        <div>
          <IconButton
            label={`${project.name} Stars 历史`}
            onClick={() => onHistory(project)}
          >
            <History size={16} />
          </IconButton>
          <IconButton
            label={`${project.is_favorite ? "取消收藏" : "收藏"} ${project.name}`}
            active={project.is_favorite}
            disabled={patch.isPending}
            onClick={() =>
              patch.mutate({
                path: `/articles/${project.article_id}`,
                body: { is_favorite: !project.is_favorite },
              })
            }
          >
            <Bookmark
              size={16}
              fill={project.is_favorite ? "currentColor" : "none"}
            />
          </IconButton>
        </div>
      </div>
      <ErrorNotice error={patch.error} />
    </article>
  );
}

export function ProjectHistory({
  project,
  onClose,
}: {
  project: Project | null;
  onClose: () => void;
}) {
  const history = useQuery({
    queryKey: ["project-history", project?.id],
    queryFn: () =>
      api<{ observed_at: string; stars: number; forks: number }[]>(
        `/projects/${project?.id}/history`,
      ),
    enabled: !!project,
  });
  return (
    <Dialog
      open={!!project}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent className="history-dialog">
        <DialogHeader>
          <DialogTitle>{project?.name} · Stars 历史</DialogTitle>
          <DialogDescription>最近 30 天的实际观测</DialogDescription>
        </DialogHeader>
        <ErrorNotice error={history.error} />
        {history.isPending ? (
          <Empty title="正在读取快照" busy />
        ) : history.data?.length ? (
          <div className="history-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>采样时间</th>
                  <th>累计 Stars</th>
                  <th>Forks</th>
                </tr>
              </thead>
              <tbody>
                {[...history.data].reverse().map((row) => (
                  <tr key={row.observed_at}>
                    <td>{dateTime(row.observed_at)}</td>
                    <td>{row.stars.toLocaleString()}</td>
                    <td>{row.forks.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="尚无快照" />
        )}
        {history.data?.length === 1 && (
          <p className="muted">仅有首次观测，暂不能计算 24 小时或 7 天增长。</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
