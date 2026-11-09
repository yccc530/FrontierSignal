import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { api, dateTime, type SummaryCoverage } from "../lib/api";
import { useAction } from "../lib/hooks";
import { ErrorNotice } from "./common";
import { Switch } from "./ui/switch";

export default function ChineseSummaries() {
  const query = useQuery({
    queryKey: ["chinese-summaries"],
    queryFn: () => api<SummaryCoverage>("/chinese-summaries"),
    refetchInterval: 5000,
  });
  const save = useAction("PATCH");
  const retry = useAction<{ queued: number }>();
  const data = query.data;
  return (
    <section className="settings-section" aria-label="中文摘要">
      <div className="section-label">
        中文摘要
        <span>
          {data
            ? data.automatic
              ? "后台自动处理"
              : "自动处理未启用"
            : "正在读取进度"}
        </span>
      </div>
      <ErrorNotice error={query.error || save.error || retry.error} />
      {data && (
        <>
          <div className="switch-line">
            <label htmlFor="all-chinese-summaries">全部资讯生成中文摘要</label>
            <Switch
              id="all-chinese-summaries"
              checked={data.policy.all_content}
              disabled={save.isPending}
              onCheckedChange={(all_content) =>
                save.mutate({
                  path: "/chinese-summaries",
                  body: { all_content },
                })
              }
            />
          </div>
          <p className="muted">
            包含历史补采和已筛除内容，使用已配置模型并产生调用用量。
          </p>
          <dl className="summary-counts" aria-label="中文摘要处理进度">
            {(
              [
                ["已就绪", data.ready],
                ["待生成", data.queued],
                ["处理中", data.processing],
                ["等待重试", data.retrying],
                ["失败待重试", data.failed],
                ["暂缓", data.deferred + data.excluded],
              ] as const
            ).map(([label, count]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{count.toLocaleString()}</dd>
              </div>
            ))}
          </dl>
          <p className="muted">
            共 {data.total.toLocaleString()} 条 · 每批最多 {data.batch_size} 条
            {data.last_success_at &&
              ` · 最近成功 ${dateTime(data.last_success_at)}`}
          </p>
          {data.failed > 0 && (
            <button
              className="secondary-button"
              disabled={retry.isPending}
              onClick={() =>
                retry.mutate({
                  path: "/chinese-summaries/retry",
                  body: { limit: 30 },
                })
              }
            >
              <RefreshCw size={14} /> 重试未完成摘要（最多 30 条）
            </button>
          )}
          {retry.isSuccess && (
            <p role="status">
              已重新排队 {retry.data.queued} 条，等待后台处理。
            </p>
          )}
        </>
      )}
    </section>
  );
}
