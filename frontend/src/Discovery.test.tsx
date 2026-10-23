import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Growth } from "./components/Intelligence";
import { TooltipProvider } from "./components/ui/tooltip";
import Discover from "./pages/Discover";
import type { Dashboard, StarGrowth } from "./lib/api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const missing: StarGrowth = {
  value: null,
  baseline_at: null,
  observed_at: "2026-10-22T00:00:00Z",
  window_hours: null,
  reason: "历史快照不足",
};

it("renders unknown growth without inventing zero", () => {
  const { rerender } = render(
    <dl>
      <Growth label="24h " growth={missing} />
    </dl>,
  );
  expect(screen.getByText("待积累")).toBeInTheDocument();
  expect(screen.queryByText("0")).not.toBeInTheDocument();
  rerender(
    <dl>
      <Growth
        label="24h "
        growth={{ ...missing, value: 0, window_hours: 24 }}
      />
    </dl>,
  );
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(screen.queryByText("待积累")).not.toBeInTheDocument();
});

it("preserves observed star decreases", () => {
  render(
    <dl>
      <Growth
        label="24h "
        growth={{ ...missing, value: -4, window_hours: 25 }}
      />
    </dl>,
  );
  expect(screen.getByText("-4")).toBeInTheDocument();
});

it("shows real empty sections and saves interests through the API", async () => {
  let interests = ["llm", "inference"];
  const patches: unknown[] = [];
  const dashboard: Dashboard = {
    generated_at: "2026-10-22T00:00:00Z",
    topics: [
      { id: "llm", label: "大模型" },
      { id: "inference", label: "推理优化" },
    ],
    interests,
    projects: [],
    emerging_projects: [],
    sections: [
      { id: "hot", title: "今日 AI 技术热点", window: "近 72 小时", items: [] },
      { id: "papers", title: "最新前沿论文", window: "近 14 天", items: [] },
      {
        id: "official",
        title: "官方模型与技术发布",
        window: "近 30 天",
        items: [],
      },
      {
        id: "discoveries",
        title: "高价值技术发现",
        window: "近 30 天",
        items: [],
      },
    ],
    counts: { projects: 0, growth_pending: 0, rising: 0, new: 0 },
    coverage: {
      project_candidates_truncated: false,
      article_candidates_truncated: false,
      candidate_limit: 1000,
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path.startsWith("/api/recommendations"))
        return Response.json({ ...dashboard, interests });
      if (path === "/api/preferences" && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body));
        patches.push(body);
        interests = body.topics;
        return Response.json({ topics: interests });
      }
      if (path === "/api/sources" || path === "/api/categories")
        return Response.json([]);
      if (path === "/api/settings")
        return Response.json({ llm_configured: false });
      throw new Error(`Unexpected fixture request ${path}`);
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <TooltipProvider>
          <Discover />
        </TooltipProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
  expect(await screen.findByText("暂未观测到明显增长")).toBeInTheDocument();
  expect(screen.getByText("暂未发现近 30 天新项目")).toBeInTheDocument();
  expect(screen.getAllByText("当前主题暂无符合条件的内容")).toHaveLength(4);
  expect(screen.queryByTestId("project-item")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText("研究偏好"));
  fireEvent.click(screen.getByRole("checkbox", { name: "大模型" }));
  fireEvent.click(screen.getByRole("button", { name: "保存偏好" }));
  await waitFor(() =>
    expect(patches).toContainEqual({ topics: ["inference"] }),
  );
  expect(await screen.findByText("偏好已保存")).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "大模型" })).not.toBeChecked();
  client.clear();
});
