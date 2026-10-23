import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import {
  api,
  dateTime,
  type DiscoveryCoverage,
  type RuntimeReport,
} from "../lib/api";
import { ErrorNotice } from "./common";

export default function CoverageMonitor() {
  const coverage = useQuery({
    queryKey: ["discovery-coverage"],
    queryFn: () => api<DiscoveryCoverage>("/discovery/coverage"),
    refetchInterval: 30000,
  });
  const runtime = useQuery({
    queryKey: ["runtime-report"],
    queryFn: () => api<RuntimeReport>("/discovery/runtime"),
    refetchInterval: 30000,
  });
  const report = runtime.data;
  return (
    <details className="interest-panel coverage-panel">
      <summary>
        <Activity size={17} /> 采集覆盖与持续观察
        {report && (
          <span className="interest-count">
            {report.observation.observed_hours} 小时 ·{" "}
            {report.observation.status === "covered"
              ? "已覆盖 24 小时"
              : report.observation.status === "gaps"
                ? "观察存在间断"
                : "24 小时观察中"}
          </span>
        )}
      </summary>
      <ErrorNotice error={coverage.error || runtime.error} />
      {report && (
        <div className="coverage-runtime">
          <p>
            开始：{dateTime(report.observation.started_at)} ·{" "}
            {report.observation.samples} 次有效采样 · 最大间隔{" "}
            {report.observation.max_gap_minutes ?? "未知"} 分钟
          </p>
          <p>
            并发 {report.concurrency} · 任务超时 {report.task_timeout_seconds}s
            · 调度{report.scheduler_enabled ? "开启" : "关闭"} · 近 24
            小时模型调用 {report.llm_24h.attempts} 次
          </p>
          <p>
            7 天增长：
            {report.observation.seven_day_status === "pending"
              ? "观察窗口尚未形成"
              : "待核验各项目实际增长基线"}
          </p>
        </div>
      )}
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>技术方向</th>
              <th>专项扫描</th>
              <th>最近成功</th>
              <th>缺口</th>
            </tr>
          </thead>
          <tbody>
            {coverage.data?.topics.map((topic) => {
              const groups = coverage.data.sources
                .filter((source) => source.enabled && source.automatic)
                .flatMap((source) => source.groups)
                .filter(
                  (group) =>
                    group.topics.includes(topic.id) &&
                    !group.id.startsWith("global:") &&
                    !group.id.startsWith("publisher:"),
                );
              const success = groups.filter((group) => group.last_success_at);
              const last = success
                .map((group) => group.last_success_at!)
                .sort()
                .at(-1);
              const failed = groups.filter((group) =>
                ["failed", "partial"].includes(group.status),
              ).length;
              return (
                <tr key={topic.id}>
                  <td>{topic.label}</td>
                  <td>
                    {success.length} / {groups.length} 组
                  </td>
                  <td>{dateTime(last || null)}</td>
                  <td>
                    {!groups.length
                      ? "未启用专项自动采集"
                      : failed
                        ? `${failed} 组失败或部分失败`
                        : success.length < groups.length
                          ? "部分查询尚未扫描"
                          : groups.every((group) => group.candidates === 0)
                            ? "本轮返回零候选"
                            : "已留下扫描记录"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}
