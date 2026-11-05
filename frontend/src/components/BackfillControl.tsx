import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CalendarClock, Play, ScanSearch } from "lucide-react";
import {
  api,
  type BackfillPlan,
  type BackfillRequest,
  type CoverageAudit,
} from "../lib/api";
import { useAction } from "../lib/hooks";
import { ErrorNotice } from "./common";

function utcDate(days: number) {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() - days);
  return value.toISOString().slice(0, 10);
}

export default function BackfillControl({
  sources,
}: {
  sources: CoverageAudit["sources"];
}) {
  const available = sources.filter(
    (source) => source.enabled && source.backfill.supported,
  );
  const [selected, setSelected] = useState("");
  const sourceId = selected || available[0]?.source_id || "";
  const [request, setRequest] = useState<BackfillRequest>({
    start_date: utcDate(5),
    end_date: utcDate(1),
    max_pages: 2,
    per_page: 20,
    github_date_field: "both",
  });
  const [previewed, setPreviewed] = useState("");
  const fingerprint = JSON.stringify([sourceId, request]);
  const preview = useMutation({
    mutationFn: () =>
      api<BackfillPlan>(`/sources/${sourceId}/backfill/preview`, {
        method: "POST",
        body: JSON.stringify(request),
      }),
    onSuccess: () => setPreviewed(fingerprint),
  });
  const submit = useAction();
  return (
    <details className="backfill-control">
      <summary>
        <CalendarClock size={16} /> 有界历史补采
      </summary>
      <p className="muted">
        UTC 日期范围 · 分页有上限 · 原始内容入库后暂不自动分析 · 非全量覆盖
      </p>
      {available.length ? (
        <form
          className="form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            preview.mutate();
          }}
        >
          <div className="form-columns">
            <label>
              补采来源
              <select
                aria-label="补采来源"
                value={sourceId}
                onChange={(event) => setSelected(event.target.value)}
              >
                {available.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              日期依据
              {available.find((source) => source.source_id === sourceId)
                ?.kind === "github_discovery" ? (
                <select
                  aria-label="补采日期依据"
                  value={request.github_date_field}
                  onChange={(event) =>
                    setRequest({
                      ...request,
                      github_date_field: event.target
                        .value as BackfillRequest["github_date_field"],
                    })
                  }
                >
                  <option value="both">创建与代码更新</option>
                  <option value="created">创建日期</option>
                  <option value="pushed">代码更新日期</option>
                </select>
              ) : (
                <input
                  aria-label="补采日期依据"
                  value="首次提交日期（UTC）"
                  title="arXiv submittedDate，按首次提交时间查询"
                  readOnly
                />
              )}
            </label>
            <label>
              开始日期（UTC）
              <input
                required
                type="date"
                aria-label="补采开始日期"
                value={request.start_date}
                max={request.end_date}
                onChange={(event) =>
                  setRequest({ ...request, start_date: event.target.value })
                }
              />
            </label>
            <label>
              结束日期（UTC）
              <input
                required
                type="date"
                aria-label="补采结束日期"
                value={request.end_date}
                min={request.start_date}
                max={utcDate(0)}
                onChange={(event) =>
                  setRequest({ ...request, end_date: event.target.value })
                }
              />
            </label>
            <label>
              每组最多页数
              <input
                type="number"
                aria-label="补采最多页数"
                min={1}
                max={5}
                required
                value={request.max_pages}
                onChange={(event) =>
                  setRequest({
                    ...request,
                    max_pages: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              每页最多候选
              <input
                type="number"
                aria-label="补采每页候选"
                min={1}
                max={50}
                required
                value={request.per_page}
                onChange={(event) =>
                  setRequest({
                    ...request,
                    per_page: Number(event.target.value),
                  })
                }
              />
            </label>
          </div>
          <ErrorNotice error={preview.error || submit.error} />
          {previewed === fingerprint && preview.data && (
            <p role="status">
              {preview.data.groups.map((group) => group.label).join("、")} ·
              最多 {preview.data.max_requests} 次查询 /{" "}
              {preview.data.max_candidates} 个候选 · 有界补采
            </p>
          )}
          <div className="form-actions">
            <button
              className="secondary-button"
              disabled={preview.isPending}
              type="submit"
            >
              <ScanSearch size={15} />
              预览范围
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={previewed !== fingerprint || submit.isPending}
              onClick={() =>
                submit.mutate({
                  path: `/sources/${sourceId}/backfill`,
                  body: request,
                })
              }
            >
              <Play size={15} />
              开始有界补采
            </button>
          </div>
          {submit.isSuccess && (
            <p className="inline-notice" role="status">
              有界补采任务已提交。<Link to="/tasks">查看任务与实际结果</Link>
            </p>
          )}
        </form>
      ) : (
        <p className="muted">当前没有启用的可回补来源；RSS 只提供当前窗口。</p>
      )}
    </details>
  );
}
