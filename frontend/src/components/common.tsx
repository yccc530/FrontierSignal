import type { ButtonHTMLAttributes, ReactNode } from "react";
import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { displayError } from "../lib/messages";
export const statusNames: Record<string, string> = {
  never: "尚未采集",
  queued: "排队中",
  running: "运行中",
  success: "成功",
  partial: "部分失败",
  failed: "失败",
  interrupted: "已中断",
  pending: "待中文解读",
  processing: "正在解读",
  analyzed: "已分析",
  filtered: "已过滤",
  stale: "原文已更新",
};
export const trustNames: Record<string, string> = {
  official: "官方发布",
  maintainer: "项目维护者",
  community: "社区讨论",
  preprint: "研究预印本",
  unreviewed: "未评级来源",
};
const sourceNames: Record<string, string> = {
  "Hugging Face Blog": "Hugging Face 官方博客",
  "OpenAI News": "OpenAI 官方动态",
  "Google DeepMind": "Google DeepMind 官方博客",
  "Hacker News": "Hacker News 科技社区",
  "vLLM Releases": "vLLM 版本发布",
  "LangChain Releases": "LangChain 版本发布",
  "arXiv · cs.AI": "arXiv 人工智能论文",
};
export const sourceLabel = (name: string) => sourceNames[name] || name;
export const kindNames: Record<string, string> = {
  rss: "订阅源",
  arxiv: "论文订阅",
  github: "项目发布",
  hackernews: "科技社区",
  github_discovery: "项目发现",
  hf_models: "模型资源",
  hf_datasets: "数据资源",
};
export function Status({ value }: { value: string }) {
  return (
    <Badge variant="outline" className={`state-badge state-${value}`}>
      {["running", "processing", "queued"].includes(value) && (
        <LoaderCircle size={14} className="spinning" />
      )}
      {statusNames[value] || value}
    </Badge>
  );
}
export function IconButton({
  label,
  active,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="icon-wrap">
          <Button
            variant="ghost"
            size="icon"
            className={`icon-button ${active ? "is-active" : ""}`}
            aria-label={label}
            aria-pressed={active}
            {...props}
          >
            {children}
          </Button>
        </span>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
export function ErrorNotice({ error }: { error: Error | null | undefined }) {
  return error ? (
    <div className="error-banner" role="alert">
      <AlertCircle size={16} />
      <span>{displayError(error.message)}</span>
    </div>
  ) : null;
}
export function Empty({
  title,
  detail,
  busy = false,
}: {
  title: string;
  detail?: string;
  busy?: boolean;
}) {
  return (
    <div
      className="empty-state"
      role={busy ? "status" : undefined}
      aria-busy={busy}
    >
      <span className="state-icon" aria-hidden="true">
        {busy ? (
          <LoaderCircle className="spinning" size={24} />
        ) : (
          <Inbox size={24} />
        )}
      </span>
      <h2>{title}</h2>
      {detail && <p>{detail}</p>}
    </div>
  );
}
export function SourceMark({ name, kind }: { name: string; kind: string }) {
  const images: Record<string, string> = {
    "Hugging Face Blog": "huggingface",
    "OpenAI News": "openai",
    "Google DeepMind": "deepmind",
    "Hugging Face 热门模型": "huggingface",
    "Hugging Face 技术数据集": "huggingface",
  };
  if (images[name])
    return (
      <span className={`source-mark source-${kind}`}>
        <img
          src={`/sources/${images[name]}.png`}
          width={21}
          height={21}
          alt=""
        />
      </span>
    );
  return (
    <span className={`source-mark source-${kind}`}>
      {kind === "arxiv"
        ? "aX"
        : kind === "github" || kind === "github_discovery"
          ? "GH"
          : kind === "hackernews"
            ? "Y"
            : name.startsWith("Hugging")
              ? "HF"
              : name.charAt(0)}
    </span>
  );
}
