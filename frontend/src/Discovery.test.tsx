import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Growth } from "./components/Intelligence";
import { TooltipProvider } from "./components/ui/tooltip";
import Discover from "./pages/Discover";
import type { Dashboard, StarGrowth } from "./lib/api";
import {
  makeDashboard,
  makeProject,
  makeRecommendation,
} from "./test-fixtures";

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
      if (path === "/api/recommendation-policy")
        return Response.json({
          section_limits: {},
          topic_weights: {},
          repeat_hours: 24,
        });
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
  expect(await screen.findByText("当前主题暂无推荐内容")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /讨论/ })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /论文/ })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /官方/ })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /发现/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /项目/ }));
  expect(screen.getByText("暂未发现近 30 天新项目")).toBeInTheDocument();
  expect(screen.queryByTestId("project-item")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /论文/ }));
  expect(screen.getByText("当前主题暂无符合条件的内容")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /精选/ }));
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

function mountDashboard(
  data: Dashboard | ((topic: string) => Dashboard),
  seen?: (init: RequestInit) => Response,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path === "/api/recommendations/seen" && init)
        return seen?.(init) || Response.json({ recorded: 1 });
      if (path.startsWith("/api/recommendations")) {
        const snapshot =
          typeof data === "function"
            ? data(
                new URL(path, "http://localhost").searchParams.get("topic") ||
                  "",
              )
            : data;
        return Response.json(snapshot);
      }
      if (path === "/api/sources" || path === "/api/categories")
        return Response.json([]);
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
  return client;
}

it("opens the selected topic's content without recommendation share controls or policy writes", async () => {
  const catalog = [
    { id: "llm", label: "大模型" },
    { id: "agents", label: "AI Agent" },
    { id: "inference", label: "推理优化" },
    { id: "training", label: "训练与数据" },
    { id: "rag", label: "RAG 与检索" },
    { id: "multimodal", label: "多模态" },
    { id: "image", label: "图像生成与编辑", group: "创作模型" },
  ];
  const client = mountDashboard((topic) => {
    const data = makeDashboard({ topics: catalog });
    data.sections.find((section) => section.id === "papers")!.items = [
      makeRecommendation(topic === "image" ? "image-paper" : "all-paper"),
    ];
    return data;
  });
  await screen.findByText("测试资讯 all-paper");
  expect(
    screen.queryByText("推荐份额", { exact: true }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("高级推荐设置", { exact: true }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /^论文/ }));
  fireEvent.click(screen.getByRole("button", { name: "更多方向" }));
  fireEvent.click(
    within(await screen.findByRole("dialog")).getByRole("link", {
      name: "图像生成与编辑",
    }),
  );
  expect(await screen.findByText("测试资讯 image-paper")).toBeInTheDocument();
  expect(screen.queryByText("测试资讯 all-paper")).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", {
      name: "图像生成与编辑 · 前沿论文",
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /^论文/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([path]) =>
        String(path).includes("/recommendations?topic=image"),
      ),
  ).toBe(true);
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([path]) =>
        String(path).includes("recommendation-policy"),
      ),
  ).toBe(false);
  client.clear();
});

it("renders project-only featured cards with unknown growth and a linked tab panel", async () => {
  const client = mountDashboard(
    makeDashboard({ emerging_projects: [makeProject("only-project")] }),
  );
  const card = await screen.findByTestId("project-item");
  expect(card).toHaveAttribute("data-article-id", "only-project");
  expect(card).toHaveTextContent("短期增长待观测");
  expect(screen.queryByText("当前主题暂无推荐内容")).not.toBeInTheDocument();
  const tab = screen.getByRole("tab", { name: /精选/ });
  const panel = screen.getByRole("tabpanel", { name: /精选/ });
  expect(tab).toHaveAttribute("aria-controls", panel.id);
  expect(panel).toHaveAttribute("aria-labelledby", tab.id);
  client.clear();
});

it("records only half-visible articles once per revision and retries a failed exposure after tab re-entry", async () => {
  const observers: {
    callback: IntersectionObserverCallback;
    targets: Element[];
    disconnect: ReturnType<typeof vi.fn>;
  }[] = [];
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      targets: Element[] = [];
      disconnect = vi.fn();
      constructor(callback: IntersectionObserverCallback) {
        observers.push({
          callback,
          targets: this.targets,
          disconnect: this.disconnect,
        });
      }
      observe(target: Element) {
        this.targets.push(target);
      }
    },
  );
  const data = makeDashboard();
  data.sections[0].items = [makeRecommendation("exposure-article")];
  let attempts = 0;
  const client = mountDashboard(data, () => {
    const failed = attempts++ === 0;
    return Response.json(
      failed ? { detail: "测试曝光写入失败" } : { recorded: 1 },
      { status: failed ? 503 : 200 },
    );
  });
  const card = await screen.findByTestId("recommendation-item");
  const intersect = (ratio: number) => {
    const observer = observers.at(-1)!;
    observer.callback(
      [
        {
          target: observer.targets[0],
          isIntersecting: true,
          intersectionRatio: ratio,
        } as IntersectionObserverEntry,
      ],
      {} as IntersectionObserver,
    );
  };
  expect(observers.at(-1)!.targets).toContain(card);
  intersect(0.25);
  expect(attempts).toBe(0);
  intersect(0.5);
  expect(await screen.findByText("测试曝光写入失败")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /^模型/ }));
  expect(observers[0].disconnect).toHaveBeenCalled();
  const fullCard = screen.getByTestId("recommendation-item");
  expect(fullCard).not.toBe(card);
  expect(observers.at(-1)!.targets).toContain(fullCard);
  intersect(0.5);
  await waitFor(() =>
    expect(screen.queryByText("测试曝光写入失败")).not.toBeInTheDocument(),
  );
  intersect(1);
  expect(attempts).toBe(2);
  fireEvent.click(screen.getByRole("tab", { name: /精选/ }));
  intersect(1);
  expect(attempts).toBe(2);
  client.clear();
});
