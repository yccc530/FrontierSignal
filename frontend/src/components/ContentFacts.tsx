import { ArrowUpRight } from "lucide-react";
import type { Article } from "../lib/api";

const labels: Record<string, string> = {
  purpose: "用途",
  dependencies: "依赖与环境",
  input_output: "输入 / 输出",
  run: "运行说明",
  host: "宿主声明",
  authorization: "授权条件",
  claim: "作者主张",
  experiment: "实验设定",
  benchmark: "基准条件",
  reproduction: "复现线索",
};

export default function ContentFacts({
  article,
  detailed = false,
}: {
  article: Article;
  detailed?: boolean;
}) {
  const resource = article.metrics.resource;
  const research = article.metrics.research;
  const references = article.metrics.references || [];
  if (research)
    return detailed ? (
      <div className="model-facts">
        <p className="muted">作者原文声明 · 独立复现情况未核实</p>
        {research.quotes.map((quote) => (
          <div className="model-specification" key={quote.kind}>
            <strong>{labels[quote.kind]}</strong>
            <blockquote>{quote.text}</blockquote>
          </div>
        ))}
        {!!references.length && (
          <div className="model-links">
            {references.map((ref) => (
              <a key={ref.id} href={ref.url} target="_blank" rel="noreferrer">
                {ref.id} <ArrowUpRight size={14} />
              </a>
            ))}
          </div>
        )}
      </div>
    ) : null;
  if (!resource) return null;
  return (
    <div className="model-facts" data-testid="content-facts">
      <div className="model-tags">
        <strong>{resource.label}</strong>
        {resource.vibe_status === "author_declared" && (
          <span>作者声明 AI 辅助开发</span>
        )}
        {detailed && <span>运行情况未验证</span>}
      </div>
      {detailed && (
        <>
          {resource.vibe_evidence && (
            <div className="model-specification">
              <strong>开发方式 · 作者原文</strong>
              <blockquote>{resource.vibe_evidence.text}</blockquote>
              <a
                className="text-link"
                href={resource.vibe_evidence.source_url}
                target="_blank"
                rel="noreferrer"
              >
                查看依据 <ArrowUpRight size={14} />
              </a>
            </div>
          )}
          {resource.vibe_status !== "author_declared" && (
            <p className="muted">开发方式未核实。</p>
          )}
          {!!resource.quotes?.length && (
            <details className="model-specifications">
              <summary>用途、依赖与运行 · 原文摘录</summary>
              {resource.quotes.map((quote) => (
                <div className="model-specification" key={quote.kind}>
                  <strong>{labels[quote.kind] || quote.kind}</strong>
                  <blockquote>{quote.text}</blockquote>
                  <a
                    className="text-link"
                    href={quote.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看依据 <ArrowUpRight size={14} />
                  </a>
                </div>
              ))}
            </details>
          )}
        </>
      )}
    </div>
  );
}
