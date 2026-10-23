import { useEffect, useState, type FormEvent } from "react";
import { Check, FlaskConical, KeyRound, Plus, Save } from "lucide-react";
import { type LLMConfig, type SystemSettings } from "../lib/api";
import { useAction, useCategories, useSettings, useStats } from "../lib/hooks";
import { Empty, ErrorNotice } from "../components/common";
import { Switch } from "../components/ui/switch";

function editable(value: SystemSettings): LLMConfig {
  return {
    llm_base_url: value.llm_base_url,
    llm_model: value.llm_model,
    llm_timeout: value.llm_timeout,
    llm_max_retries: value.llm_max_retries,
    llm_batch_size: value.llm_batch_size,
    llm_json_mode: value.llm_json_mode,
    embedding_model: value.embedding_model,
  };
}
export default function Settings() {
  const query = useSettings();
  const categories = useCategories();
  const stats = useStats();
  const save = useAction("PATCH");
  const probe = useAction();
  const categorySave = useAction();
  const [form, setForm] = useState<LLMConfig | null>(null);
  const [category, setCategory] = useState({
    id: "",
    label: "",
    description: "",
  });
  useEffect(() => {
    if (query.data) setForm(editable(query.data));
  }, [query.data]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (form) save.mutate({ path: "/settings", body: form });
  };
  if (query.isPending) return <Empty title="正在读取设置" busy />;
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">工作台配置</div>
          <h1>系统设置</h1>
          <p>模型服务、分类与本地运行状态</p>
        </div>
      </section>
      <ErrorNotice error={query.error || save.error || probe.error} />
      {save.isSuccess && (
        <div className="notice" role="status">
          <Check size={14} /> 配置已保存到本地 .env
        </div>
      )}
      {probe.isSuccess && (
        <div className="notice" role="status">
          验证任务已提交，结果请查看运行任务中的「模型接口验证」。
        </div>
      )}
      <div className="settings-layout content-band">
        <div>
          <section className="settings-section">
            <div className="section-label">
              模型服务<span>OpenAI 兼容接口</span>
            </div>
            {form && (
              <form className="form-stack" onSubmit={submit}>
                <label>
                  模型接口地址
                  <input
                    type="url"
                    aria-label="模型接口地址"
                    placeholder="https://api.example.com/v1"
                    value={form.llm_base_url}
                    onChange={(e) =>
                      setForm({ ...form, llm_base_url: e.target.value })
                    }
                  />
                </label>
                <label>
                  模型名称
                  <input
                    aria-label="模型名称"
                    maxLength={200}
                    value={form.llm_model}
                    onChange={(e) =>
                      setForm({ ...form, llm_model: e.target.value })
                    }
                    placeholder="服务商提供的模型 ID"
                  />
                </label>
                <div className="key-status">
                  <KeyRound size={16} />
                  <span>接口密钥</span>
                  <strong>
                    {query.data?.llm_key_configured ? "已配置" : "未配置"}
                  </strong>
                  <small>在本地 .env 设置 FS_LLM_API_KEY 后重启</small>
                </div>
                <div className="form-columns">
                  <label>
                    请求超时 / 秒
                    <input
                      aria-label="请求超时"
                      type="number"
                      min={5}
                      max={180}
                      value={form.llm_timeout}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          llm_timeout: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label>
                    最大重试次数
                    <input
                      aria-label="最大重试次数"
                      type="number"
                      min={0}
                      max={5}
                      value={form.llm_max_retries}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          llm_max_retries: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label>
                    单批处理条数
                    <input
                      aria-label="单批处理条数"
                      type="number"
                      min={1}
                      max={30}
                      value={form.llm_batch_size}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          llm_batch_size: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                </div>
                <div className="switch-line">
                  <label htmlFor="json-mode">
                    结构化输出模式<small>仅在服务商支持时开启</small>
                  </label>
                  <Switch
                    id="json-mode"
                    checked={form.llm_json_mode}
                    onCheckedChange={(value) =>
                      setForm({ ...form, llm_json_mode: value })
                    }
                  />
                </div>
                <label>
                  向量模型（可选）
                  <input
                    aria-label="向量模型"
                    maxLength={200}
                    value={form.embedding_model}
                    onChange={(e) =>
                      setForm({ ...form, embedding_model: e.target.value })
                    }
                    placeholder="留空则不进行向量关联"
                  />
                </label>
                <div className="form-actions">
                  <button
                    className="primary-button"
                    type="submit"
                    disabled={save.isPending}
                  >
                    <Save size={15} />
                    保存配置
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!query.data?.llm_configured || probe.isPending}
                    onClick={() => probe.mutate({ path: "/settings/probe" })}
                  >
                    <FlaskConical size={15} />
                    验证接口
                  </button>
                </div>
              </form>
            )}
          </section>
          <section className="settings-section">
            <div className="section-label">
              情报分类<span>{categories.data?.length ?? "—"} 个</span>
            </div>
            <div className="category-list">
              {categories.data?.map((c) => (
                <button
                  key={c.id}
                  className="category-edit"
                  onClick={() => setCategory(c)}
                >
                  <span>{c.label}</span>
                  <code>{c.id}</code>
                </button>
              ))}
            </div>
            <form
              className="form-stack category-form"
              onSubmit={(e) => {
                e.preventDefault();
                categorySave.mutate(
                  { path: "/categories", body: category },
                  {
                    onSuccess: () =>
                      setCategory({ id: "", label: "", description: "" }),
                  },
                );
              }}
            >
              <div className="form-columns">
                <label>
                  分类标识
                  <input
                    aria-label="分类标识"
                    required
                    pattern="[a-z][a-z0-9_-]{0,79}"
                    value={category.id}
                    onChange={(e) =>
                      setCategory({ ...category, id: e.target.value })
                    }
                  />
                </label>
                <label>
                  分类名称
                  <input
                    aria-label="分类名称"
                    required
                    maxLength={100}
                    value={category.label}
                    onChange={(e) =>
                      setCategory({ ...category, label: e.target.value })
                    }
                  />
                </label>
              </div>
              <label>
                分类说明
                <input
                  aria-label="分类说明"
                  maxLength={400}
                  value={category.description}
                  onChange={(e) =>
                    setCategory({ ...category, description: e.target.value })
                  }
                />
              </label>
              <ErrorNotice error={categorySave.error} />
              <div>
                <button
                  className="secondary-button"
                  disabled={categorySave.isPending}
                >
                  <Plus size={14} />
                  保存分类
                </button>
              </div>
              {categorySave.isSuccess && (
                <span className="inline-notice">分类已保存</span>
              )}
            </form>
          </section>
        </div>
        <aside className="settings-aside">
          <div className="section-label">运行状态</div>
          <dl className="status-list">
            <div>
              <dt>数据库</dt>
              <dd>PostgreSQL</dd>
            </div>
            <div>
              <dt>定时采集</dt>
              <dd>{query.data?.scheduler_enabled ? "已开启" : "已关闭"}</dd>
            </div>
            <div>
              <dt>网络代理</dt>
              <dd>{query.data?.proxy_configured ? "已配置" : "直连"}</dd>
            </div>
            <div>
              <dt>GitHub 令牌</dt>
              <dd>
                {query.data?.github_token_configured ? "已配置" : "公共访问"}
              </dd>
            </div>
            <div>
              <dt>GitHub 每轮搜索</dt>
              <dd>{query.data?.github_queries_per_run ?? "—"} 组</dd>
            </div>
            <div>
              <dt>GitHub 每轮跟踪</dt>
              <dd>{query.data?.github_track_per_run ?? "—"} 个项目</dd>
            </div>
          </dl>
          <div className="section-label">模型用量</div>
          <dl className="status-list">
            <div>
              <dt>输入用量（词元）</dt>
              <dd>{stats.data?.input_tokens?.toLocaleString() ?? "—"}</dd>
            </div>
            <div>
              <dt>输出用量（词元）</dt>
              <dd>{stats.data?.output_tokens?.toLocaleString() ?? "—"}</dd>
            </div>
            <div>
              <dt>已分析资讯</dt>
              <dd>{stats.data?.analyzed ?? "—"}</dd>
            </div>
          </dl>
          <div className="note-block">
            <span className="subtle-tag">本地配置</span>
            <p>
              密钥只从本地文件或环境变量读取，不会返回完整值。环境变量优先于
              .env。
            </p>
            <p>启用模型后，待处理资讯会按单批数量自动分析并产生服务商用量。</p>
          </div>
        </aside>
      </div>
    </>
  );
}
