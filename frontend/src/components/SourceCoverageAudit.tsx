import { useQuery } from "@tanstack/react-query";
import { api, dateTime, type CoverageAudit } from "../lib/api";
import { Empty, ErrorNotice } from "./common";
import BackfillControl from "./BackfillControl";

export default function SourceCoverageAudit() {
  const query = useQuery({
    queryKey: ["coverage-audit"],
    queryFn: () => api<CoverageAudit>("/discovery/audit"),
    refetchInterval: 30000,
  });
  const sources = query.data?.sources ?? [];
  return (
    <section className="source-coverage-audit">
      <h2>来源覆盖审计</h2>
      <ErrorNotice error={query.error} />
      <p className="muted">
        近 7 天新增 / 重复 / 过滤来自真实任务。无成功采集的 UTC
        日期表示活动缺口；成功查询与有界补采均不代表全量覆盖。
      </p>
      {query.isPending ? (
        <Empty title="正在读取覆盖审计" busy />
      ) : sources.length ? (
        <>
          <div className="table-scroll">
            <table className="data-table" aria-label="来源覆盖审计">
              <thead>
                <tr>
                  <th>来源</th>
                  <th>最近成功 / 间隔</th>
                  <th>近 7 天新增 / 重复 / 过滤</th>
                  <th>未留下成功采集的日期（UTC）</th>
                  <th>查询与回补</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.source_id}>
                    <td>
                      <strong>{source.name}</strong>
                      <small>{source.enabled ? "已启用" : "已停用"}</small>
                      {source.gaps.map((gap) => (
                        <p className="muted" key={gap}>
                          {gap}
                        </p>
                      ))}
                    </td>
                    <td>
                      {dateTime(source.last_success_at)}
                      <small>
                        {source.hours_since_success === null
                          ? "暂无成功记录"
                          : `${source.hours_since_success} 小时前`}
                      </small>
                    </td>
                    <td className="numeric">
                      {source.totals_7d.added} / {source.totals_7d.duplicates} /{" "}
                      {source.totals_7d.filtered}
                    </td>
                    <td>
                      {source.days_without_successful_collection === null
                        ? "活动证据截断，覆盖未知"
                        : source.days_without_successful_collection.length
                          ? source.days_without_successful_collection.join("、")
                          : "各日均有成功任务；非全量覆盖"}
                    </td>
                    <td>
                      <span>
                        {source.backfill.supported
                          ? "官方 API 有界回补"
                          : "当前窗口，不可回补"}
                      </span>
                      <details>
                        <summary>{source.groups.length} 组扫描记录</summary>
                        {source.groups.length ? (
                          source.groups.map((group) => (
                            <div className="audit-query" key={group.id}>
                              <strong>{group.label || group.id}</strong>
                              <p>
                                {dateTime(group.last_scan_at)} · 候选{" "}
                                {group.candidates ?? "未知"} · 过滤{" "}
                                {group.filtered ?? "未知"}
                              </p>
                              {group.gaps.map((gap) => (
                                <p key={gap}>{gap}</p>
                              ))}
                              {group.error && (
                                <p className="source-error">{group.error}</p>
                              )}
                            </div>
                          ))
                        ) : (
                          <p>尚无查询组扫描证据</p>
                        )}
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <BackfillControl sources={sources} />
          {!!query.data?.backfills?.length && (
            <details className="backfill-control">
              <summary>最近有界补采记录</summary>
              {query.data.backfills.slice(0, 10).map((task) => (
                <p key={task.id}>
                  {sources.find((source) => source.source_id === task.source_id)
                    ?.name || task.source_id}{" "}
                  · {task.details?.plan.start_date} 至{" "}
                  {task.details?.plan.end_date} UTC ·{" "}
                  {task.status === "partial"
                    ? "有界补采"
                    : task.status === "failed"
                      ? "失败"
                      : task.status === "interrupted"
                        ? "中断"
                        : "执行中"}{" "}
                  · 新增 {task.added} / 重复 {task.duplicates} / 失败{" "}
                  {task.failed}
                </p>
              ))}
            </details>
          )}
        </>
      ) : (
        !query.error && <Empty title="暂无来源覆盖记录" />
      )}
    </section>
  );
}
