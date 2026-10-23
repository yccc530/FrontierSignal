import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
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
      else if (url.pathname === "/api/sources") value = [source];
      else if (url.pathname === "/api/categories") value = [];
      else if (["/api/topics", "/api/publishers"].includes(url.pathname))
        value = [];
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
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <TooltipProvider>
          <Feed />
        </TooltipProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}
describe("feed interactions using isolated fixtures", () => {
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
