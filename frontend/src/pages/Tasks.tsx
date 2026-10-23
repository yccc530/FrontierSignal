import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { dateTime } from "../lib/api";
import { useAction, useSources, useTasks } from "../lib/hooks";
import { displayError } from "../lib/messages";
import {
  Empty,
  ErrorNotice,
  IconButton,
  Status,
  sourceLabel,
} from "../components/common";
export default function Tasks() {
  const tasks = useTasks();
  const sources = useSources();
  const retry = useAction();
  const [status, setStatus] = useState("");
  const rows = tasks.data?.filter(
    (t) =>
      !status ||
      (status === "active"
        ? ["running", "queued"].includes(t.status)
        : t.status === status),
  );
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">采集与分析记录</div>
          <h1>运行任务</h1>
          <p>最近 100 次采集、分析与接口验证</p>
        </div>
        <IconButton
          label="刷新任务"
          disabled={tasks.isFetching}
          onClick={() => tasks.refetch()}
        >
          <RefreshCw size={18} />
        </IconButton>
      </section>
      <ErrorNotice error={tasks.error || retry.error} />
      <div className="content-band">
        <div className="table-toolbar">
          <strong>任务记录</strong>
          <select
            aria-label="任务状态"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">全部状态</option>
            <option value="active">运行中 / 排队</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
            <option value="partial">部分失败</option>
            <option value="interrupted">中断</option>
          </select>
        </div>
        {tasks.isPending ? (
          <Empty title="正在读取任务" busy />
        ) : rows?.length === 0 ? (
          <Empty title="暂无任务记录" />
        ) : (
          <div className="table-scroll">
            <table className="data-table task-table">
              <thead>
                <tr>
                  <th>任务 / 来源</th>
                  <th>状态</th>
                  <th>新增</th>
                  <th>更新</th>
                  <th>重复</th>
                  <th>过滤</th>
                  <th>失败</th>
                  <th>开始 / 耗时</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows?.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <strong>
                        {task.kind === "analyze"
                          ? "AI 情报分析"
                          : task.kind === "probe"
                            ? "模型接口验证"
                            : sourceLabel(
                                sources.data?.find(
                                  (s) => s.id === task.source_id,
                                )?.name ||
                                  task.source_id ||
                                  "未知来源",
                              )}
                      </strong>
                      <small className="task-id">{task.id.slice(0, 8)}</small>
                      {task.error && (
                        <p className="source-error">
                          {displayError(task.error)}
                        </p>
                      )}
                    </td>
                    <td>
                      <Status value={task.status} />
                    </td>
                    {[
                      task.added,
                      task.updated,
                      task.duplicates,
                      task.filtered,
                      task.failed,
                    ].map((count, index) => (
                      <td
                        key={index}
                        className={
                          index === 4 && count ? "failed-count" : "numeric"
                        }
                      >
                        {count}
                      </td>
                    ))}
                    <td>
                      <span className="muted">
                        {dateTime(task.started_at || task.created_at)}
                      </span>
                      <small className="task-id">
                        {task.finished_at && task.started_at
                          ? `${Math.max(0, (new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()) / 1000).toFixed(1)} 秒`
                          : "—"}
                      </small>
                    </td>
                    <td>
                      {task.source_id &&
                        ["failed", "partial", "interrupted"].includes(
                          task.status,
                        ) && (
                          <IconButton
                            label="重试采集"
                            disabled={
                              retry.isPending ||
                              !sources.data?.find(
                                (s) => s.id === task.source_id,
                              )?.enabled
                            }
                            onClick={() =>
                              retry.mutate({
                                path: `/sources/${task.source_id}/collect`,
                              })
                            }
                          >
                            <RefreshCw size={15} />
                          </IconButton>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
