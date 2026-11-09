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
import RecommendationControls from "./components/RecommendationControls";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("keeps the advanced recommendation form collapsed and preserves the existing policy API", async () => {
  let policy = {
    section_limits: { models: 6, tools: 6 },
    topic_weights: { llm: 1 },
    repeat_hours: 24,
  };
  const writes: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      expect(path).toBe("/api/recommendation-policy");
      if (init?.method === "PATCH") {
        policy = JSON.parse(String(init.body));
        writes.push(policy);
      }
      return Response.json(policy);
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <RecommendationControls topics={[{ id: "llm", label: "大模型" }]} />
    </QueryClientProvider>,
  );
  const heading = screen.getByText("高级推荐设置", { exact: true });
  expect(heading.closest("details")).not.toHaveAttribute("open");
  expect(writes).toHaveLength(0);
  fireEvent.click(heading);
  const models = await screen.findByLabelText("模型展示条数");
  expect(models).toHaveValue(6);
  fireEvent.change(models, { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "保存推荐设置" }));
  await waitFor(() =>
    expect(writes).toContainEqual({
      section_limits: { models: 3, tools: 6 },
      topic_weights: { llm: 1 },
      repeat_hours: 24,
    }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("推荐设置已保存");
  client.clear();
});
