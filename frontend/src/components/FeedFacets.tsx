import { useState } from "react";
import { ChevronDown, ChevronUp, Search, X } from "lucide-react";
import type { Category, Publisher, Topic } from "../lib/api";
import { IconButton } from "./common";

type Facet = "publisher" | "topic" | "category";
const labels = {
  publisher: "发布团队",
  topic: "技术方向",
  category: "资讯分类",
};

export default function FeedFacets({
  publishers,
  topics,
  categories,
  params,
  onChange,
}: {
  publishers: Publisher[];
  topics: Topic[];
  categories: Category[];
  params: URLSearchParams;
  onChange: (key: string, value: string) => void;
}) {
  const [tab, setTab] = useState<Facet>(
    params.get("publisher")
      ? "publisher"
      : params.get("topic")
        ? "topic"
        : "publisher",
  );
  const [open, setOpen] = useState(true);
  const [search, setSearch] = useState("");
  const catalogs = {
    publisher: publishers,
    topic: topics,
    category: categories,
  };
  const options = catalogs[tab].filter((item) =>
    `${item.label} ${item.id}`.toLowerCase().includes(search.toLowerCase()),
  );
  const groups = tab === "publisher" ? ["china", "global"] : [""];
  return (
    <section className="feed-facets" aria-label="资讯分类面板">
      <div className="facet-header">
        <div className="facet-tabs" role="tablist" aria-label="筛选维度">
          {(Object.keys(labels) as Facet[]).map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              id={`facet-tab-${key}`}
              aria-selected={tab === key}
              aria-controls="facet-options"
              tabIndex={tab === key ? 0 : -1}
              onKeyDown={(event) => {
                const keys = Object.keys(labels) as Facet[];
                const offset =
                  event.key === "ArrowRight"
                    ? 1
                    : event.key === "ArrowLeft"
                      ? -1
                      : 0;
                if (!offset) return;
                event.preventDefault();
                const next =
                  keys[
                    (keys.indexOf(key) + offset + keys.length) % keys.length
                  ];
                setTab(next);
                setSearch("");
                setOpen(true);
                document.getElementById(`facet-tab-${next}`)?.focus();
              }}
              onClick={() => {
                setTab(key);
                setSearch("");
                setOpen(true);
              }}
            >
              {labels[key]} <span>{catalogs[key].length}</span>
            </button>
          ))}
        </div>
        {open && (
          <label className="facet-search">
            <Search size={16} />
            <input
              aria-label={`搜索${labels[tab]}`}
              placeholder={`查找${labels[tab]}`}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        )}
        <IconButton
          label={open ? "收起分类面板" : "展开分类面板"}
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
        </IconButton>
      </div>
      {open && (
        <div
          id="facet-options"
          role="tabpanel"
          aria-labelledby={`facet-tab-${tab}`}
        >
          <label className="facet-all">
            <input
              type="radio"
              name={`facet-${tab}`}
              checked={!params.get(tab)}
              onChange={() => onChange(tab, "")}
            />
            全部{labels[tab]}
          </label>
          {groups.map((group) => {
            const rows = options.filter(
              (item) =>
                !group || ((item as Publisher).region || "global") === group,
            );
            return rows.length ? (
              <fieldset key={group} className="facet-group">
                <legend>
                  {group === "china"
                    ? "国内团队"
                    : group === "global"
                      ? "海外与全球社区"
                      : labels[tab]}
                </legend>
                <div className="facet-grid">
                  {rows.map((item) => (
                    <label
                      key={item.id}
                      className={`facet-option ${params.get(tab) === item.id ? "selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name={`facet-${tab}`}
                        value={item.id}
                        checked={params.get(tab) === item.id}
                        onChange={() => onChange(tab, item.id)}
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null;
          })}
          {!options.length && <p className="muted">没有匹配的{labels[tab]}</p>}
        </div>
      )}
      {Object.entries(labels).some(([key]) => params.has(key)) && (
        <div className="facet-selection" aria-label="已选分类">
          {(Object.keys(labels) as Facet[])
            .filter((key) => params.has(key))
            .map((key) => (
              <span key={key}>
                {labels[key]}：
                {catalogs[key].find((item) => item.id === params.get(key))
                  ?.label || params.get(key)}
                <IconButton
                  label={`清除${labels[key]}`}
                  onClick={() => onChange(key, "")}
                >
                  <X size={14} />
                </IconButton>
              </span>
            ))}
        </div>
      )}
    </section>
  );
}
