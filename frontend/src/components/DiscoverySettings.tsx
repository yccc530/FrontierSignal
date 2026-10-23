import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RotateCcw, Save } from "lucide-react";
import { api, dateTime, type DiscoveryCoverage, type Source } from "../lib/api";
import { useAction } from "../lib/hooks";
import { ErrorNotice, Status } from "./common";

export default function DiscoverySettings({ source }: { source: Source }) {
  const [selected, setSelected] = useState(source.discovery_topics || []);
  const savedTopics = (source.discovery_topics || []).join(",");
  useEffect(
    () => setSelected(savedTopics.split(",").filter(Boolean)),
    [savedTopics],
  );
  const patch = useAction("PATCH");
  const coverage = useQuery({
    queryKey: ["discovery-coverage"],
    queryFn: () => api<DiscoveryCoverage>("/discovery/coverage"),
    refetchInterval: 15000,
  });
  const topics =
    coverage.data?.topics.filter((topic) =>
      topic.collectors?.includes(source.kind),
    ) || [];
  const scans =
    coverage.data?.sources.find((item) => item.source_id === source.id)
      ?.groups || [];
  const sourceCoverage = coverage.data?.sources.find(
    (item) => item.source_id === source.id,
  );
  return (
    <details className="source-discovery">
      <summary>采集方向与扫描记录</summary>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          patch.mutate({
            path: `/sources/${source.id}`,
            body: { discovery_topics: selected },
          });
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
          disabled={patch.isPending || !selected.length}
        >
          <Save size={14} />
          保存采集范围
        </button>
        <button
          type="button"
          className="text-button"
          disabled={patch.isPending || !source.discovery_scope_customized}
          onClick={() =>
            patch.mutate({
              path: `/sources/${source.id}`,
              body: { discovery_topics: null },
            })
          }
        >
          <RotateCcw size={14} /> 恢复默认范围
        </button>
        {patch.isSuccess && (
          <span className="inline-notice" role="status">
            采集范围已保存
          </span>
        )}
        <ErrorNotice error={coverage.error || patch.error} />
      </form>
      <ul className="scan-list">
        {sourceCoverage && (
          <li>
            每轮请求预算 {sourceCoverage.request_budget} · 全部子查询轮换约{" "}
            {sourceCoverage.scan_cycle_hours} 小时（不含失败重试）
            {sourceCoverage.priority_scan_hours != null && (
              <span>
                {" "}
                · 下一轮重点厂商覆盖约 {sourceCoverage.priority_scan_hours} 小时
              </span>
            )}
          </li>
        )}
        {scans.map((scan) => (
          <li key={scan.id}>
            <strong>{scan.label}</strong>
            {scan.priority && <span className="tag">优先跟踪</span>}
            <Status value={scan.status === "pending" ? "never" : scan.status} />
            <span>
              {scan.last_scan_at ? dateTime(scan.last_scan_at) : "尚未扫描"}
              {scan.candidates !== null ? ` · ${scan.candidates} 个候选` : ""}
              {scan.added !== undefined
                ? ` · 新增 ${scan.added} / 更新 ${scan.updated ?? 0} / 重复 ${scan.duplicates ?? 0}`
                : ""}
            </span>
            {scan.error && <span className="source-error">{scan.error}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}
