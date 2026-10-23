import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CoverageMonitor from "./components/CoverageMonitor";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows measured transfer, missing history and official account scan gaps separately", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      const value = path.endsWith("/coverage")
        ? {
            topics: [],
            sources: [
              {
                enabled: true,
                automatic: true,
                groups: [
                  {
                    id: "publisher:zai",
                    label: "智谱 / Z.ai",
                    priority: true,
                    last_success_at: null,
                    error: "HTTP 429",
                  },
                  {
                    id: "publisher:meta",
                    label: "Meta · meta-llama",
                    priority: true,
                    last_success_at: "2026-10-23T01:00:00Z",
                    error: null,
                  },
                ],
              },
            ],
          }
        : {
            observation: {
              observed_hours: 1,
              samples: 12,
              max_gap_minutes: 5,
              status: "pending",
              seven_day_status: "pending",
            },
            concurrency: 3,
            task_timeout_seconds: 180,
            scheduler_enabled: true,
            llm_24h: { attempts: 0 },
            collection_traffic: {
              timezone: "UTC",
              basis: "http_response_body",
              days: [
                {
                  date: "2026-10-23",
                  requests: 12,
                  received_bytes: 1048576,
                  measured_tasks: 1,
                  unmeasured_tasks: 2,
                  running_tasks: 1,
                  unmeasured_responses: 0,
                },
                {
                  date: "2026-10-22",
                  requests: 0,
                  received_bytes: 0,
                  measured_tasks: 0,
                  unmeasured_tasks: 7,
                  running_tasks: 0,
                  unmeasured_responses: 0,
                },
              ],
            },
          };
      return new Response(JSON.stringify(value), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <CoverageMonitor />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("采集覆盖与持续观察"));
  expect(await screen.findByText("智谱 / Z.ai")).toBeVisible();
  expect(screen.getByText(/尚未成功扫描/)).toBeVisible();
  expect(screen.getByText(/HTTP 429/)).toBeVisible();
  fireEvent.click(screen.getByText("每日采集接收量（UTC）"));
  const table = screen.getByRole("table", { name: "每日采集流量记录" });
  expect(within(table).getByText("1.00 MiB")).toBeVisible();
  expect(within(table).getAllByText("未记录")).toHaveLength(2);
  expect(within(table).getByText(/2 个任务无记录/)).toBeVisible();
  expect(screen.getByText(/不含请求上传、协议开销、LLM/)).toBeVisible();
  client.clear();
});
