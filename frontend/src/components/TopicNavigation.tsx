import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronDown, Grid2X2, Search } from "lucide-react";
import type { Topic } from "../lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";

export default function TopicNavigation({ topics }: { topics: Topic[] }) {
  const [params] = useSearchParams();
  const current = params.get("topic") || "";
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const primary = topics.slice(0, 6);
  const selected = topics.find((topic) => topic.id === current);
  if (selected && !primary.some((topic) => topic.id === selected.id))
    primary.push(selected);
  const options = topics.filter((topic) =>
    `${topic.label} ${topic.id} ${topic.group || ""}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  const groups = Array.from(
    new Set(options.map((topic) => topic.group || "技术方向")),
  );
  const destination = (id: string) => {
    const next = new URLSearchParams(params);
    if (id) next.set("topic", id);
    else next.delete("topic");
    return { pathname: "/", search: next.toString() ? `?${next}` : "" };
  };
  const enter = () => {
    setOpen(false);
    setSearch("");
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (!value) setSearch("");
      }}
    >
      <nav className="topic-navigation" aria-label="技术方向">
        <Link
          className="topic-link"
          to={destination("")}
          aria-current={!current ? "page" : undefined}
          onClick={enter}
        >
          全部方向
        </Link>
        {primary.map((topic) => (
          <Link
            key={topic.id}
            className="topic-link"
            to={destination(topic.id)}
            aria-current={current === topic.id ? "page" : undefined}
            onClick={enter}
          >
            {topic.label}
          </Link>
        ))}
        {topics.length > primary.length && (
          <DialogTrigger asChild>
            <button type="button" className="topic-more">
              <Grid2X2 size={15} aria-hidden="true" /> 更多方向{" "}
              <ChevronDown size={14} aria-hidden="true" />
            </button>
          </DialogTrigger>
        )}
      </nav>
      <DialogContent className="topic-directory-dialog">
        <DialogHeader>
          <DialogTitle>选择技术方向</DialogTitle>
          <DialogDescription>{topics.length} 个技术方向</DialogDescription>
        </DialogHeader>
        <label className="search-field topic-directory-search">
          <Search size={17} aria-hidden="true" />
          <input
            aria-label="搜索技术方向"
            placeholder="搜索方向"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="topic-directory-groups">
          {groups.map((group) => (
            <section key={group} aria-label={group}>
              <h3>{group}</h3>
              <div className="topic-directory-options">
                {options
                  .filter((topic) => (topic.group || "技术方向") === group)
                  .map((topic) => (
                    <Link
                      key={topic.id}
                      className="topic-link"
                      to={destination(topic.id)}
                      aria-current={current === topic.id ? "page" : undefined}
                      onClick={enter}
                    >
                      {topic.label}
                      {topic.discovery_ready === false && (
                        <small>待专项接入</small>
                      )}
                    </Link>
                  ))}
              </div>
            </section>
          ))}
          {!options.length && (
            <p className="muted" role="status">
              没有匹配的技术方向
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
