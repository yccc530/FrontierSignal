import { useState, type FormEvent } from "react";
import { ArrowDownToLine, Plus, Radio } from "lucide-react";
import { dateTime, type Source } from "../lib/api";
import { displayError } from "../lib/messages";
import { useAction, useSources } from "../lib/hooks";
import {
  Empty,
  ErrorNotice,
  IconButton,
  SourceMark,
  Status,
  trustNames,
  sourceLabel,
  kindNames,
} from "../components/common";
import { Switch } from "../components/ui/switch";
import DiscoverySettings from "../components/DiscoverySettings";
import CoverageMonitor from "../components/CoverageMonitor";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";

function Frequency({
  source,
  onSave,
}: {
  source: Source;
  onSave: (value: number) => void;
}) {
  const [value, setValue] = useState(String(source.interval_minutes));
  return (
    <input
      className="frequency-input"
      aria-label={`${sourceLabel(source.name)} 采集间隔（分钟）`}
      type="number"
      min={15}
      max={10080}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => {
        const n = Number(value);
        if (
          Number.isInteger(n) &&
          n >= 15 &&
          n <= 10080 &&
          n !== source.interval_minutes
        )
          onSave(n);
        else setValue(String(source.interval_minutes));
      }}
    />
  );
}

export default function Sources() {
  const sources = useSources();
  const patch = useAction("PATCH");
  const collect = useAction();
  const create = useAction();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    kind: "rss",
    url: "",
    repository: "",
    interval_minutes: 120,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { path: "/sources", body: form },
      {
        onSuccess: () => {
          setOpen(false);
          setForm({
            name: "",
            kind: "rss",
            url: "",
            repository: "",
            interval_minutes: 120,
          });
        },
      },
    );
  };
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">订阅与来源管理</div>
          <h1>信息来源</h1>
          <p>
            {sources.data?.filter((s) => s.enabled).length ?? "—"} 个启用 ·{" "}
            {sources.data?.length ?? "—"} 个已配置
          </p>
        </div>
        <div className="heading-actions">
          <button className="secondary-button" onClick={() => setOpen(true)}>
            <Plus size={16} />
            添加来源
          </button>
          <button
            className="primary-button"
            disabled={
              collect.isPending ||
              !sources.data?.some((source) => source.enabled)
            }
            onClick={() => collect.mutate({ path: "/collect" })}
          >
            <ArrowDownToLine size={16} />
            采集全部
          </button>
        </div>
      </section>
      <ErrorNotice error={sources.error || patch.error || collect.error} />
      <CoverageMonitor />
      {collect.isSuccess && (
        <div className="notice" role="status">
          采集请求已提交，可在运行任务中查看结果。
        </div>
      )}
      <div className="content-band">
        {sources.isPending ? (
          <Empty title="正在读取来源" busy />
        ) : sources.isError ? null : sources.data?.length === 0 ? (
          <Empty title="暂无信息来源" detail="尚未配置订阅源或项目。" />
        ) : (
          <div className="table-scroll">
            <table className="data-table source-table">
              <thead>
                <tr>
                  <th>信息来源</th>
                  <th>状态</th>
                  <th>最近成功</th>
                  <th>自动 / 间隔（分钟）</th>
                  <th>启用</th>
                  <th>采集</th>
                </tr>
              </thead>
              <tbody>
                {sources.data?.map((source) => (
                  <tr key={source.id}>
                    <td>
                      <div className="source-cell">
                        <SourceMark name={source.name} kind={source.kind} />
                        <div>
                          <strong>{sourceLabel(source.name)}</strong>
                          <small>
                            {trustNames[source.trust]} ·{" "}
                            {kindNames[source.kind] || source.kind}
                          </small>
                        </div>
                      </div>
                      <p className="source-url">{source.url}</p>
                      {!!source.discovery_topics?.length && (
                        <DiscoverySettings key={source.id} source={source} />
                      )}
                      {source.last_error && (
                        <p className="source-error">
                          {displayError(source.last_error)}
                        </p>
                      )}
                    </td>
                    <td>
                      <Status value={source.last_status} />
                    </td>
                    <td className="muted">
                      {source.last_success_at
                        ? dateTime(source.last_success_at)
                        : "尚未成功"}
                    </td>
                    <td>
                      <div className="schedule-control">
                        <Switch
                          aria-label={`${sourceLabel(source.name)} 自动采集`}
                          checked={source.automatic}
                          disabled={patch.isPending}
                          onCheckedChange={(value) =>
                            patch.mutate({
                              path: `/sources/${source.id}`,
                              body: { automatic: value },
                            })
                          }
                        />
                        <span>{source.automatic ? "自动" : "手动"}</span>
                      </div>
                      {source.automatic && (
                        <Frequency
                          key={`${source.id}-${source.interval_minutes}`}
                          source={source}
                          onSave={(value) =>
                            patch.mutate({
                              path: `/sources/${source.id}`,
                              body: { interval_minutes: value },
                            })
                          }
                        />
                      )}
                    </td>
                    <td>
                      <Switch
                        aria-label={`${sourceLabel(source.name)} 启用状态`}
                        checked={source.enabled}
                        disabled={patch.isPending}
                        onCheckedChange={(value) =>
                          patch.mutate({
                            path: `/sources/${source.id}`,
                            body: { enabled: value },
                          })
                        }
                      />
                    </td>
                    <td>
                      <IconButton
                        label={`采集 ${source.name}`}
                        disabled={
                          !source.enabled ||
                          collect.isPending ||
                          source.last_status === "running"
                        }
                        onClick={() =>
                          collect.mutate({
                            path: `/sources/${source.id}/collect`,
                          })
                        }
                      >
                        <Radio size={17} />
                      </IconButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加信息来源</DialogTitle>
            <DialogDescription>官方订阅、开源项目与研究资源</DialogDescription>
          </DialogHeader>
          <form className="form-stack" onSubmit={submit}>
            <label>
              名称
              <input
                required
                maxLength={160}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              来源类型
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
              >
                <option value="rss">公开订阅（RSS / Atom）</option>
                <option value="github">GitHub 项目版本发布</option>
                <option value="arxiv">arXiv 论文订阅</option>
                <option value="hackernews">Hacker News 科技社区</option>
                <option value="github_discovery">GitHub AI 项目发现</option>
                <option value="hf_models">Hugging Face 模型</option>
                <option value="hf_datasets">Hugging Face 数据集</option>
              </select>
            </label>
            {form.kind === "github" ? (
              <label>
                项目路径
                <input
                  required
                  placeholder="owner/repository"
                  value={form.repository}
                  onChange={(e) =>
                    setForm({ ...form, repository: e.target.value })
                  }
                />
              </label>
            ) : (
              ["rss", "arxiv"].includes(form.kind) && (
                <label>
                  订阅地址
                  <input
                    type="url"
                    required
                    placeholder="https://…"
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                  />
                </label>
              )
            )}
            <label>
              采集间隔（分钟）
              <input
                type="number"
                min={15}
                max={10080}
                value={form.interval_minutes}
                onChange={(e) =>
                  setForm({ ...form, interval_minutes: Number(e.target.value) })
                }
              />
            </label>
            <ErrorNotice error={create.error} />
            <button
              type="submit"
              className="primary-button"
              disabled={create.isPending}
            >
              <Plus size={15} />
              添加来源
            </button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
