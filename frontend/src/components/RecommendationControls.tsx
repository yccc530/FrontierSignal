import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Save, SlidersHorizontal } from "lucide-react";
import { api, type RecommendationPolicy, type Topic } from "../lib/api";
import { useAction } from "../lib/hooks";
import { ErrorNotice } from "./common";

const sectionNames: Record<string, string> = {
  models: "模型",
  tools: "工具与应用",
  workflows: "创作工作流",
  hot: "技术热点",
  papers: "论文",
  official: "官方发布",
  discoveries: "技术发现",
};

export default function RecommendationControls({
  topics,
}: {
  topics: Topic[];
}) {
  const query = useQuery({
    queryKey: ["recommendation-policy"],
    queryFn: () => api<RecommendationPolicy>("/recommendation-policy"),
  });
  const [draft, setDraft] = useState<RecommendationPolicy | null>(null);
  useEffect(() => {
    if (query.data) setDraft(query.data);
  }, [query.data]);
  const save = useAction("PATCH");
  return (
    <details className="interest-panel policy-panel">
      <summary>
        <SlidersHorizontal size={17} /> 推荐份额
      </summary>
      <ErrorNotice error={query.error || save.error} />
      {draft && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate({ path: "/recommendation-policy", body: draft });
          }}
        >
          <fieldset>
            <legend>各栏目展示条数</legend>
            <div className="policy-fields">
              {Object.entries(sectionNames).map(([key, name]) => (
                <label key={key}>
                  {name}
                  <input
                    type="number"
                    min={0}
                    max={12}
                    aria-label={`${name}展示条数`}
                    value={draft.section_limits[key] ?? 6}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        section_limits: {
                          ...draft.section_limits,
                          [key]: Number(event.target.value),
                        },
                      })
                    }
                  />
                </label>
              ))}
              <label>
                重复推荐观察（小时）
                <input
                  aria-label="重复推荐观察小时"
                  type="number"
                  min={1}
                  max={168}
                  value={draft.repeat_hours}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      repeat_hours: Number(event.target.value),
                    })
                  }
                />
              </label>
            </div>
          </fieldset>
          <fieldset>
            <legend>方向相对份额（1–5）</legend>
            <div className="policy-fields">
              {topics.map((topic) => (
                <label key={topic.id}>
                  {topic.label}
                  <input
                    aria-label={`${topic.label}推荐份额`}
                    type="number"
                    min={1}
                    max={5}
                    value={draft.topic_weights[topic.id] || 1}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        topic_weights: {
                          ...draft.topic_weights,
                          [topic.id]: Number(event.target.value),
                        },
                      })
                    }
                  />
                </label>
              ))}
            </div>
          </fieldset>
          <div className="form-actions">
            <button className="secondary-button" disabled={save.isPending}>
              <Save size={14} />
              保存推荐设置
            </button>
            {save.isSuccess && <span role="status">推荐设置已保存</span>}
          </div>
        </form>
      )}
    </details>
  );
}
