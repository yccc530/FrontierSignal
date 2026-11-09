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
import ChineseSummaries from "./components/ChineseSummaries";
import type { SummaryCoverage } from "./lib/api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows actual coverage and changes policy or retries only on an explicit action", async () => {
  const data: SummaryCoverage = {
    policy: { all_content: false },
    automatic: true,
    batch_size: 5,
    total: 10,
    ready: 3,
    queued: 2,
    processing: 1,
    retrying: 1,
    failed: 1,
    deferred: 1,
    excluded: 1,
    last_success_at: null,
  };
  const writes: { path: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        const body = JSON.parse(String(init.body));
        writes.push({ path, body });
        data.policy = body;
        return Response.json(data);
      }
      if (init?.method === "POST") {
        writes.push({ path, body: JSON.parse(String(init.body)) });
        return Response.json({ queued: 1 });
      }
      return Response.json(data);
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <ChineseSummaries />
    </QueryClientProvider>,
  );
  const toggle = await screen.findByRole("switch", {
    name: "全部资讯生成中文摘要",
  });
  expect(toggle).not.toBeChecked();
  expect(screen.getByLabelText("中文摘要处理进度")).toHaveTextContent(
    "已就绪3",
  );
  expect(writes).toEqual([]);
  fireEvent.click(toggle);
  await waitFor(() => expect(toggle).toBeChecked());
  expect(writes).toEqual([
    { path: "/api/chinese-summaries", body: { all_content: true } },
  ]);
  fireEvent.click(
    screen.getByRole("button", { name: "重试未完成摘要（最多 30 条）" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "已重新排队 1 条",
  );
  expect(writes[1]).toEqual({
    path: "/api/chinese-summaries/retry",
    body: { limit: 30 },
  });
  client.clear();
});
