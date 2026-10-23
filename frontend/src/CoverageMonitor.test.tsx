import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CoverageMonitor from "./components/CoverageMonitor";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows official account scan successes and gaps", async () => {
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
  expect(screen.getByText("Meta · meta-llama")).toBeVisible();
  client.clear();
});
