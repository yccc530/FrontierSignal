import { expect, test } from "@playwright/test";
import {
  makeDashboard,
  makeProject,
  makeRecommendation,
} from "../src/test-fixtures";

test("fixture: Chinese summaries persist, placeholders stay honest and policy writes are explicit", async ({
  page,
}) => {
  const recommendation = makeRecommendation("paper");
  recommendation.article.title = "Original paper title";
  recommendation.article.body =
    "This is the English abstract retained in the original record.";
  const project = makeProject("repository");
  project.description = "An original English project description.";
  const dashboard = makeDashboard({
    emerging_projects: [project],
    sections: [
      {
        id: "papers",
        title: "前沿论文",
        window: "近 14 天",
        items: [recommendation],
      },
    ],
  });
  let allContent = false;
  const writes: string[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/recommendations/seen")
      return route.fulfill({ json: { recorded: 1 } });
    if (request.method() !== "GET") {
      writes.push(`${request.method()} ${path}`);
      if (path === "/api/chinese-summaries" && request.method() === "PATCH") {
        expect(request.postDataJSON()).toEqual({ all_content: true });
        allContent = true;
      } else if (path === "/api/chinese-summaries/retry") {
        expect(request.postDataJSON()).toEqual({ limit: 30 });
        return route.fulfill({ json: { queued: 1 } });
      } else return route.abort();
    }
    if (path === "/api/chinese-summaries")
      return route.fulfill({
        json: {
          policy: { all_content: allContent },
          automatic: true,
          batch_size: 5,
          total: 10,
          ready: 3,
          queued: allContent ? 4 : 3,
          processing: 1,
          retrying: 1,
          failed: 1,
          deferred: allContent ? 0 : 1,
          excluded: 0,
          last_success_at: null,
        },
      });
    if (path === "/api/recommendations")
      return route.fulfill({ json: dashboard });
    if (path === "/api/topics")
      return route.fulfill({ json: dashboard.topics });
    if (path === "/api/recommendation-policy")
      return route.fulfill({ json: dashboard.policy });
    if (path === "/api/settings")
      return route.fulfill({
        json: {
          llm_configured: true,
          llm_key_configured: true,
          llm_model: "fixture",
          llm_base_url: "https://example.com/v1",
          llm_timeout: 60,
          llm_max_retries: 2,
          llm_batch_size: 5,
          llm_json_mode: false,
          embedding_model: "",
          scheduler_enabled: true,
        },
      });
    if (["/api/sources", "/api/categories"].includes(path))
      return route.fulfill({ json: [] });
    if (["/api/stats", "/api/health"].includes(path))
      return route.fulfill({ json: {} });
    return route.continue();
  });
  await page.goto("/");
  await expect(
    page.getByText("Original paper title", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("中文摘要待生成，原文已保留。", { exact: true }),
  ).toHaveCount(2);
  await expect(
    page.getByText(recommendation.article.body, { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText(project.description, { exact: true }),
  ).toHaveCount(0);
  expect(writes).toEqual([]);
  await page.goto("/#/settings");
  const panel = page.getByRole("region", { name: "中文摘要", exact: true });
  const toggle = panel.getByRole("switch", { name: "全部资讯生成中文摘要" });
  await expect(toggle).not.toBeChecked();
  await toggle.click();
  await expect(toggle).toBeChecked();
  await panel
    .getByRole("button", { name: "重试未完成摘要（最多 30 条）" })
    .click();
  await expect(panel.getByRole("status")).toContainText("已重新排队 1 条");
  for (const width of [1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    await panel.scrollIntoViewIfNeeded();
    expect(
      await panel.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `../.runtime/chinese-summaries-${width}.png`,
    });
  }
  await page.reload();
  await expect(toggle).toBeChecked();
  expect(writes).toEqual([
    "PATCH /api/chinese-summaries",
    "POST /api/chinese-summaries/retry",
  ]);
  recommendation.article.title_zh = "论文中文标题";
  recommendation.article.summary_zh = "基于来源内容保存的中文摘要。";
  project.summary_zh = "已保存的项目中文简介。";
  await page.goto("/");
  await expect(page.getByText("论文中文标题", { exact: true })).toBeVisible();
  await expect(
    page.getByText("基于来源内容保存的中文摘要。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("已保存的项目中文简介。", { exact: true }),
  ).toBeVisible();
  expect(writes).toHaveLength(2);
});
