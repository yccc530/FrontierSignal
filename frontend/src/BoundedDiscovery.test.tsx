import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import BackfillControl from "./components/BackfillControl";
import DiscoveryBudget from "./components/DiscoveryBudget";
import SourceCoverageAudit from "./components/SourceCoverageAudit";
import type { CoverageAudit } from "./lib/api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mount(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </MemoryRouter>,
  );
  return client;
}

const sources: CoverageAudit["sources"] = [
  {
    source_id: "arxiv-ai",
    name: "arXiv AI",
    kind: "arxiv",
    enabled: true,
    last_success_at: null,
    hours_since_success: null,
    totals_7d: {
      tasks: 0,
      added: 0,
      updated: 0,
      duplicates: 0,
      filtered: 0,
      failed: 0,
    },
    days_without_successful_collection: ["2026-10-31", "2026-11-01"],
    backfill: { supported: true, kind: "official-api-bounded" },
    gaps: ["最近7天没有成功采集记录"],
    groups: [],
  },
];

it("requires a matching finite preview and sends no collection or model request automatically", async () => {
  const calls: { path: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      calls.push({ path, body });
      return Response.json(
        path.endsWith("/preview")
          ? {
              ...body,
              bounded: true,
              timezone: "UTC",
              groups: [{ id: "cs.AI", label: "cs.AI" }],
              max_requests: 2,
              max_candidates: 40,
            }
          : { status: "queued" },
      );
    }),
  );
  const client = mount(<BackfillControl sources={sources} />);
  fireEvent.click(screen.getByText("有界历史补采"));
  const start = screen.getByRole("button", { name: "开始有界补采" });
  expect(start).toBeDisabled();
  fireEvent.change(screen.getByLabelText("补采开始日期"), {
    target: { value: "2026-10-31" },
  });
  fireEvent.change(screen.getByLabelText("补采结束日期"), {
    target: { value: "2026-11-04" },
  });
  fireEvent.click(screen.getByRole("button", { name: "预览范围" }));
  await waitFor(() => expect(start).toBeEnabled());
  expect(calls).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("补采最多页数"), {
    target: { value: "3" },
  });
  expect(start).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "预览范围" }));
  await waitFor(() => expect(start).toBeEnabled());
  fireEvent.click(start);
  await waitFor(() =>
    expect(calls.at(-1)).toMatchObject({
      path: "/api/sources/arxiv-ai/backfill",
      body: { start_date: "2026-10-31", end_date: "2026-11-04", max_pages: 3 },
    }),
  );
  expect(calls.every((call) => call.path.includes("/backfill"))).toBe(true);
  client.clear();
});

it("keeps absent coverage visible after a bounded task instead of claiming recovery", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        sources,
        backfills: [
          {
            id: "fixture",
            source_id: "arxiv-ai",
            status: "partial",
            added: 5,
            duplicates: 0,
            failed: 0,
            details: {
              plan: { start_date: "2026-10-31", end_date: "2026-11-04" },
            },
          },
        ],
      }),
    ),
  );
  const client = mount(<SourceCoverageAudit />);
  expect(await screen.findByText("2026-10-31、2026-11-01")).toBeVisible();
  expect(screen.getByText("最近7天没有成功采集记录")).toBeVisible();
  fireEvent.click(screen.getByText("0 组扫描记录"));
  expect(screen.getByText("尚无查询组扫描证据")).toBeVisible();
  fireEvent.click(screen.getByText("最近有界补采记录"));
  expect(screen.getByText(/有界补采.*新增 5/)).toBeVisible();
  expect(
    screen.queryByText("各日均有成功任务；非全量覆盖"),
  ).not.toBeInTheDocument();
  client.clear();
});

it("a Token preset remains a draft until an explicit budget save and contains no credentials", async () => {
  const budget = {
    github_queries_per_run: 2,
    github_candidates_per_query: 10,
    github_track_per_run: 10,
    github_code_checks: 3,
    github_readme_checks: 2,
    github_history_checks: 8,
    github_search_pages: 3,
    github_mature_queries: 0,
    github_organization_queries: 0,
    github_fixed_per_run: 0,
    max_requests: 35,
  };
  const writes: Record<string, number>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path.endsWith("github-catalog"))
        return Response.json({ fixed_repositories: [], organizations: [] });
      if (init?.method === "PATCH") {
        writes.push(JSON.parse(String(init.body)));
        return Response.json({ ...writes.at(-1), max_requests: 54 });
      }
      return Response.json(budget);
    }),
  );
  const client = mount(<DiscoveryBudget tokenConfigured />);
  fireEvent.click(screen.getByText("GitHub 发现预算"));
  fireEvent.click(
    await screen.findByRole("button", { name: "填入 Token 建议值" }),
  );
  expect(writes).toHaveLength(0);
  expect(screen.getByLabelText("每轮查询总组数")).toHaveValue(4);
  expect(screen.getByLabelText("固定仓库名额（含在跟踪内）")).toHaveValue(3);
  fireEvent.click(screen.getByRole("button", { name: "保存发现预算" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({
    github_queries_per_run: 4,
    github_candidates_per_query: 20,
    github_track_per_run: 15,
    github_history_checks: 15,
  });
  expect(
    Object.keys(writes[0]).every(
      (key) => key.startsWith("github_") && !key.includes("token"),
    ),
  ).toBe(true);
  client.clear();
});
