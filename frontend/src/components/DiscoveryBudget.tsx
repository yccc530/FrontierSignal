import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Save, Settings2 } from "lucide-react";
import { api, type DiscoveryBudget as Budget } from "../lib/api";
import { useAction } from "../lib/hooks";
import { ErrorNotice } from "./common";

const fields: { key: keyof Budget; label: string; min: number; max: number }[] =
  [
    { key: "github_queries_per_run", label: "每轮查询总组数", min: 1, max: 4 },
    {
      key: "github_candidates_per_query",
      label: "每组候选数",
      min: 1,
      max: 30,
    },
    {
      key: "github_mature_queries",
      label: "成熟项目查询组数（含在总数内）",
      min: 0,
      max: 2,
    },
    {
      key: "github_organization_queries",
      label: "官方组织查询组数（含在总数内）",
      min: 0,
      max: 2,
    },
    { key: "github_track_per_run", label: "每轮总跟踪名额", min: 1, max: 15 },
    {
      key: "github_fixed_per_run",
      label: "固定仓库名额（含在跟踪内）",
      min: 0,
      max: 10,
    },
    { key: "github_search_pages", label: "轮换页数上限", min: 1, max: 5 },
    {
      key: "github_history_checks",
      label: "官方获星历史名额",
      min: 0,
      max: 15,
    },
    { key: "github_code_checks", label: "代码目录核验名额", min: 0, max: 10 },
    { key: "github_readme_checks", label: "README 读取名额", min: 0, max: 5 },
  ];
type Catalog = {
  fixed_repositories: { name: string; label: string; evidence_url: string }[];
  organizations: { login: string; label: string; evidence_url: string }[];
};

export default function DiscoveryBudget({
  tokenConfigured,
}: {
  tokenConfigured: boolean;
}) {
  const query = useQuery({
    queryKey: ["discovery-budget"],
    queryFn: () => api<Budget & { max_requests: number }>("/discovery/budget"),
  });
  const catalog = useQuery({
    queryKey: ["github-catalog"],
    queryFn: () => api<Catalog>("/discovery/github-catalog"),
  });
  const [form, setForm] = useState<Budget | null>(null);
  const save = useAction("PATCH");
  useEffect(() => {
    if (query.data)
      setForm(
        Object.fromEntries(
          fields.map(({ key }) => [key, query.data![key]]),
        ) as Budget,
      );
  }, [query.data]);
  return (
    <section className="settings-section discovery-budget">
      <details>
        <summary className="section-label">
          <Settings2 size={16} />
          GitHub 发现预算
          <span>每轮最多 {query.data?.max_requests ?? "—"} 次逻辑调用</span>
        </summary>
        <ErrorNotice error={query.error || catalog.error || save.error} />
        <p className="muted">
          增长、成熟项目与官方组织共用查询总数；固定仓库共用跟踪名额。Token
          不会自动增加预算，重试与重定向另计。
        </p>
        {form && (
          <form
            className="form-stack"
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate({ path: "/discovery/budget", body: form });
            }}
          >
            <div className="form-columns">
              {fields.map(({ key, label, min, max }) => (
                <label key={key}>
                  {label}
                  <input
                    required
                    aria-label={label}
                    type="number"
                    min={min}
                    max={max}
                    value={form[key]}
                    onChange={(event) =>
                      setForm({ ...form, [key]: Number(event.target.value) })
                    }
                  />
                </label>
              ))}
            </div>
            <div className="form-actions">
              <button
                className="primary-button"
                type="submit"
                disabled={save.isPending}
              >
                <Save size={15} />
                保存发现预算
              </button>
              {tokenConfigured && (
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() =>
                    setForm({
                      ...form,
                      github_queries_per_run: 4,
                      github_candidates_per_query: 20,
                      github_track_per_run: 15,
                      github_history_checks: 15,
                      github_search_pages: 5,
                      github_mature_queries: 1,
                      github_organization_queries: 1,
                      github_fixed_per_run: 3,
                    })
                  }
                >
                  <Settings2 size={15} />
                  填入 Token 建议值
                </button>
              )}
            </div>
            {save.isSuccess && (
              <p className="inline-notice" role="status">
                发现预算已保存，下轮生效；至少保留一组增长查询。
              </p>
            )}
          </form>
        )}
        <details className="catalog-details">
          <summary>固定仓库与官方账号依据</summary>
          <p className="muted">
            维护者登记不等于质量认证；官方账号身份不代表性能更好。
          </p>
          <div className="catalog-list">
            {catalog.data?.fixed_repositories?.map((entry) => (
              <a
                href={entry.evidence_url}
                target="_blank"
                rel="noreferrer"
                key={entry.name}
              >
                {entry.name}
                <small>{entry.label}</small>
              </a>
            ))}
          </div>
          <div className="catalog-list">
            {catalog.data?.organizations?.map((entry) => (
              <a
                href={entry.evidence_url}
                target="_blank"
                rel="noreferrer"
                key={entry.login}
              >
                {entry.label}
                <small>{entry.login} · 官网依据</small>
              </a>
            ))}
          </div>
        </details>
      </details>
    </section>
  );
}
