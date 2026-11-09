import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import Feed from "./pages/Feed";
import { TooltipProvider } from "./components/ui/tooltip";
import { api, type Article, type Source } from "./lib/api";

const source: Source = {
  id: "fixture",
  name: "Fixture source",
  kind: "rss",
  url: "https://example.com/feed",
  enabled: true,
  automatic: true,
  interval_minutes: 120,
  trust: "official",
  last_run_at: null,
  last_success_at: null,
  last_status: "never",
  last_error: null,
};
let item: Article;
let empty = false;
beforeEach(() => {
  empty = false;
  item = {
    id: "fixture-item",
    source_id: source.id,
    source,
    title: "Test AI story",
    body: "Original test content",
    original_url: "https://example.com/story",
    author: null,
    published_at: null,
    collected_at: "2026-10-22T00:00:00Z",
    status: "pending",
    is_read: false,
    is_favorite: false,
    title_zh: null,
    summary_zh: null,
    category: null,
    tags: null,
    score: null,
    is_ai_related: null,
    evidence: null,
    analysis_model: null,
    analyzed_at: null,
    analysis_error: null,
    embedding_error: null,
    metrics: {},
    technical_score: 70,
    technical_topics: ["llm"],
    technical_reasons: ["测试技术主题"],
    technical_eligible: true,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const url = new URL(path, "http://localhost");
      let value: unknown;
      if (
        url.pathname === "/api/articles/fixture-item" &&
        init?.method === "PATCH"
      ) {
        item = { ...item, ...JSON.parse(String(init.body)) };
        value = item;
      } else if (url.pathname === "/api/articles")
        value = {
          items: empty ? [] : [item],
          total: empty ? 0 : 1,
          page: 1,
          page_size: 20,
        };
      else if (url.pathname === "/api/sources")
        value = [
          source,
          ...[
            ["hf-models", "hf_models"],
            ["hf-datasets", "hf_datasets"],
            ["hackernews", "hackernews"],
            ["arxiv-ai", "arxiv"],
          ].map(([id, kind]) => ({ ...source, id, name: id, kind })),
        ];
      else if (url.pathname === "/api/categories")
        value = [{ id: "agents", label: "智能体", description: "测试分类" }];
      else if (url.pathname === "/api/publishers")
        value = [
          {
            id: "kimi",
            label: "月之暗面 Kimi",
            region: "china",
            author: "moonshotai",
          },
          {
            id: "anthropic",
            label: "Anthropic · Claude",
            region: "global",
            author: null,
          },
        ];
      else if (url.pathname === "/api/topics")
        value = [{ id: "llm", label: "大模型" }];
      else if (url.pathname === "/api/settings")
        value = { llm_configured: false };
      else if (url.pathname === "/api/stats")
        value = {
          total: empty ? 0 : 1,
          enabled_sources: 1,
          unread: 1,
          analyzed: 0,
          last_collection: null,
        };
      else throw new Error(`Unexpected fixture request ${path}`);
      return new Response(JSON.stringify(value), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function NavigationProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="route">{location.search}</output>
      <Link to="/feed?topic=llm">测试主题深链</Link>
      <button onClick={() => navigate(-1)}>测试后退</button>
      <button onClick={() => navigate(1)}>测试前进</button>
    </>
  );
}
function mount(entry = "/feed") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <QueryClientProvider client={client}>
        <TooltipProvider>
          <Feed />
          <NavigationProbe />
        </TooltipProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}
describe("feed interactions using isolated fixtures", () => {
  it.each([
    ["downloads", "models", "papers"],
    ["likes", "datasets", "models"],
    ["points", "", "tools"],
    ["comments", "", "models"],
  ])(
    "clears the source scope of %s when changing content from %s to %s",
    async (sort, initial, target) => {
      mount(
        `/feed?content_type=${initial}&topic=llm&q=test&from=2026-10-31&page=3`,
      );
      await screen.findByText("Test AI story");
      fireEvent.change(screen.getByLabelText("排序方式"), {
        target: { value: sort },
      });
      expect(screen.getByLabelText("按来源筛选")).not.toHaveValue("");
      fireEvent.click(
        screen.getByRole("tab", {
          name:
            target === "papers"
              ? /^论文$/
              : target === "tools"
                ? /^工具$/
                : /^模型$/,
        }),
      );
      const route = new URLSearchParams(
        screen.getByTestId("route").textContent!,
      );
      expect(route.get("content_type")).toBe(target);
      expect(route.has("source")).toBe(false);
      expect(route.has("sort")).toBe(false);
      expect(route.has("page")).toBe(false);
      expect(route.get("topic")).toBe("llm");
      expect(route.get("q")).toBe("test");
      expect(route.get("from")).toBe("2026-10-31");
      await waitFor(() =>
        expect(
          vi.mocked(fetch).mock.calls.some(([path]) => {
            const url = new URL(String(path), "http://localhost");
            return (
              url.pathname === "/api/articles" &&
              url.searchParams.get("content_type") === target &&
              !url.searchParams.has("source")
            );
          }),
        ).toBe(true),
      );
    },
  );
  it("keeps an explicitly selected source when no platform sort imposed a scope", async () => {
    mount("/feed?source=fixture&content_type=models");
    await screen.findByText("Test AI story");
    fireEvent.click(screen.getByRole("tab", { name: /^论文$/ }));
    expect(
      new URLSearchParams(screen.getByTestId("route").textContent!).get(
        "source",
      ),
    ).toBe("fixture");
    const tab = screen.getByRole("tab", { name: /^论文$/ });
    const panel = screen.getByRole("tabpanel", { name: /^论文$/ });
    expect(tab).toHaveAttribute("aria-controls", panel.id);
    expect(panel).toHaveAttribute("aria-labelledby", tab.id);
  });
  it("restores category and topic facets from deep links and history without reopening a manually collapsed panel", async () => {
    mount("/feed?category=agents");
    const panel = within(screen.getByRole("region", { name: "资讯分类面板" }));
    expect(await panel.findByRole("radio", { name: "智能体" })).toBeChecked();
    expect(panel.getByRole("tab", { name: /资讯分类/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "收起分类面板" }));
    expect(panel.queryByRole("tabpanel")).not.toBeInTheDocument();
    expect(panel.getByRole("button", { name: "清除资讯分类" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("排序方式"), {
      target: { value: "collected" },
    });
    expect(panel.queryByRole("tabpanel")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "测试主题深链" }));
    expect(await panel.findByRole("radio", { name: "大模型" })).toBeChecked();
    expect(panel.getByRole("tab", { name: /技术方向/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "测试后退" }));
    expect(await panel.findByRole("radio", { name: "智能体" })).toBeChecked();
    expect(panel.getByRole("tab", { name: /资讯分类/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "测试前进" }));
    expect(await panel.findByRole("radio", { name: "大模型" })).toBeChecked();
  });
  it("filters publishers and topics in a grid and clears the selected facet", async () => {
    mount();
    fireEvent.click(await screen.findByRole("tab", { name: /发布团队/ }));
    fireEvent.click(
      await screen.findByRole("radio", { name: "月之暗面 Kimi" }),
    );
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(([path]) => String(path).includes("publisher=kimi")),
      ).toBe(true),
    );
    fireEvent.keyDown(screen.getByRole("tab", { name: /发布团队/ }), {
      key: "ArrowRight",
    });
    expect(screen.getByRole("tab", { name: /技术方向/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.click(screen.getByRole("radio", { name: "大模型" }));
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(([path]) => String(path).includes("topic=llm")),
      ).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "清除发布团队" }));
    expect(
      screen.queryByRole("button", { name: "清除发布团队" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "大模型" })).toBeChecked();
  });
  it("scopes citation and platform popularity sorts to the matching content", async () => {
    mount();
    await screen.findByText("Test AI story");
    fireEvent.change(screen.getByLabelText("排序方式"), {
      target: { value: "citations" },
    });
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([path]) =>
              String(path).includes("sort=citations") &&
              String(path).includes("content_type=papers"),
          ),
      ).toBe(true),
    );
    expect(screen.getByRole("tab", { name: /^论文$/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.change(screen.getByLabelText("排序方式"), {
      target: { value: "points" },
    });
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([path]) =>
              String(path).includes("sort=points") &&
              String(path).includes("source=hackernews"),
          ),
      ).toBe(true),
    );
    expect(screen.getByRole("tab", { name: /^全部$/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
  it("prefers the persisted Chinese title and summary", async () => {
    item.title_zh = "测试模型发布";
    item.summary_zh = "来自真实接口字段的中文摘要测试夹具。";
    mount();
    expect(await screen.findByText("测试模型发布")).toBeInTheDocument();
    expect(screen.getByText(item.summary_zh)).toBeInTheDocument();
    expect(screen.queryByText("Test AI story")).not.toBeInTheDocument();
    expect(screen.queryByText("INTELLIGENCE FEED")).not.toBeInTheDocument();
  });
  it("persists favorite through the API and renders the returned state", async () => {
    mount();
    expect(await screen.findByText("Test AI story")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "收藏" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "取消收藏" })).toHaveAttribute(
        "aria-pressed",
        "true",
      ),
    );
    expect(item.is_favorite).toBe(true);
    expect(screen.getByRole("button", { name: "分析待处理" })).toBeDisabled();
    expect(
      screen.getByTestId("article-row").querySelector(".score-label"),
    ).toBeNull();
  });
  it("updates the reading indicator from persisted state in both directions", async () => {
    item.summary_zh = "阅读状态改变后仍然保留的摘要。";
    mount();
    expect(await screen.findByRole("img", { name: "未读" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "标为已读" }));
    expect(await screen.findByRole("img", { name: "已读" })).toBeVisible();
    expect(item.is_read).toBe(true);
    expect(screen.getByTestId("article-row")).toHaveClass("is-read");
    expect(screen.getByText(item.summary_zh!)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "标为未读" }));
    expect(await screen.findByRole("img", { name: "未读" })).toBeVisible();
    expect(item.is_read).toBe(false);
    expect(screen.getByTestId("article-row")).not.toHaveClass("is-read");
  });
  it("shows a real empty state with no invented articles", async () => {
    empty = true;
    mount();
    expect(await screen.findByText("没有匹配的资讯")).toBeInTheDocument();
    expect(screen.queryByTestId("article-row")).not.toBeInTheDocument();
  });
  it("surfaces non-JSON server failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("Unavailable", { status: 503 })),
    );
    await expect(api("/articles")).rejects.toThrow("503");
  });
});
