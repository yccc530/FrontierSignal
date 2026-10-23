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
  const traffic = report?.collection_traffic;
  const publishers =
    coverage.data?.sources
      .filter((source) => source.enabled && source.automatic)
      .flatMap((source) => source.groups)
      .filter((group) => group.priority) || [];
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
      {publishers.length > 0 && (
        <div className="coverage-runtime" aria-label="重点厂商扫描">
          {publishers.map((group) => (
            <p key={group.id}>
              <strong>{group.label}</strong> · 最近成功：
              {group.last_success_at
                ? dateTime(group.last_success_at)
                : "尚未成功扫描"}
              {group.error && (
                <span className="source-error"> · {group.error}</span>
              )}
            </p>
          ))}
        </div>
      )}
      {traffic && (
        <details className="coverage-traffic" aria-label="每日采集接收量">
          <summary>每日采集接收量（UTC）</summary>
          <p>
            任务结束后记录响应正文接收量，含重试与跳转；不含请求上传、协议开销、LLM
            调用和手动打开原文的流量。
          </p>
          <div className="table-scroll">
            <table className="data-table" aria-label="每日采集流量记录">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>请求次数</th>
                  <th>已测接收量</th>
                  <th>记录完整性</th>
                </tr>
              </thead>
              <tbody>
                {traffic.days.map((day) => (
                  <tr key={day.date}>
                    <td>{day.date}</td>
                    <td>{day.measured_tasks ? day.requests : "未记录"}</td>
                    <td>
                      {day.measured_tasks
                        ? `${(day.received_bytes / 1024 / 1024).toFixed(2)} MiB`
                        : "未记录"}
                    </td>
                    <td>
                      {day.measured_tasks} 个已记录任务
                      {day.unmeasured_tasks > 0 &&
                        ` · ${day.unmeasured_tasks} 个任务无记录`}
                      {day.running_tasks > 0 &&
                        ` · ${day.running_tasks} 个任务待结束`}
                      {day.unmeasured_responses > 0 &&
                        ` · ${day.unmeasured_responses} 次响应无法计量`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <div className="table-scroll">
        <table className="data-table" aria-label="技术方向覆盖">
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
