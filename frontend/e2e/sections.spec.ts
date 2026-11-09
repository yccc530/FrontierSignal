import { expect, test, type Page } from "@playwright/test";
import type { Dashboard } from "../src/lib/api";
import {
  makeArticle,
  makeDashboard,
  makeProject,
  makeRecommendation,
} from "../src/test-fixtures";

async function fixtures(page: Page, dashboard: Dashboard) {
  const writes: string[] = [];
  const articleQueries: URLSearchParams[] = [];
  const policyReads: string[] = [];
  const article = makeArticle("browser-fixture");
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/api/recommendations/seen")
      return route.fulfill({
        json: { recorded: request.postDataJSON().items.length },
      });
    if (request.method() !== "GET") {
      writes.push(`${request.method()} ${url.pathname}`);
      return route.abort();
    }
    if (url.pathname === "/api/articles") {
      articleQueries.push(url.searchParams);
      return route.fulfill({
        json: { items: [article], total: 1, page: 1, page_size: 20 },
      });
    }
    if (
      url.pathname === "/api/recommendations" &&
      url.searchParams.has("topic")
    ) {
      const filtered = structuredClone(dashboard);
      const topic = url.searchParams.get("topic")!;
      filtered.projects = filtered.projects.filter((project) =>
        project.topics.includes(topic),
      );
      filtered.emerging_projects = filtered.emerging_projects.filter(
        (project) => project.topics.includes(topic),
      );
      filtered.sections.forEach((section) => {
        section.items = section.items.filter((item) =>
          item.article.technical_topics.includes(topic),
        );
      });
      return route.fulfill({ json: filtered });
    }
    if (url.pathname === "/api/recommendation-policy")
      policyReads.push(url.href);
    const responses: Record<string, unknown> = {
      "/api/chinese-summaries": {
        policy: { all_content: false },
        automatic: false,
        batch_size: 5,
        total: 0,
        ready: 0,
        queued: 0,
        processing: 0,
        retrying: 0,
        failed: 0,
        deferred: 0,
        excluded: 0,
        last_success_at: null,
      },
      "/api/recommendations": dashboard,
      "/api/recommendation-policy": dashboard.policy,
      "/api/preferences": { topics: dashboard.interests },
      "/api/health": { status: "ok" },
      "/api/settings": {
        llm_configured: false,
        llm_key_configured: false,
        llm_base_url: "https://example.com/v1",
        llm_model: "fixture",
        llm_timeout: 60,
        llm_max_retries: 2,
        llm_batch_size: 5,
        llm_json_mode: false,
        embedding_model: "",
        scheduler_enabled: false,
        github_queries_per_run: 2,
        github_track_per_run: 10,
      },
      "/api/discovery/budget": {
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
      },
      "/api/discovery/github-catalog": {
        fixed_repositories: [],
        organizations: [],
      },
      "/api/stats": {
        total: 1,
        unread: 1,
        analyzed: 0,
        favorites: 0,
        active_tasks: 0,
        enabled_sources: 0,
        last_collection: null,
      },
      "/api/sources": [
        {
          ...article.source,
          id: "hf-models",
          name: "HF Models",
          kind: "hf_models",
        },
        {
          ...article.source,
          id: "hf-datasets",
          name: "HF Datasets",
          kind: "hf_datasets",
        },
        {
          ...article.source,
          id: "hackernews",
          name: "Hacker News",
          kind: "hackernews",
        },
      ],
      "/api/topics": dashboard.topics,
      "/api/publishers": [],
      "/api/categories": [
        { id: "agents", label: "智能体", description: "测试分类" },
      ],
    };
    expect(url.pathname in responses).toBe(true);
    return route.fulfill({ json: responses[url.pathname] });
  });
  return { writes, articleQueries, policyReads };
}

test("fixture: topic directory opens dedicated content at desktop widths and restores deep links", async ({
  page,
}) => {
  const data = makeDashboard();
  data.topics = [
    { id: "llm", label: "大模型", group: "基础模型" },
    { id: "agents", label: "AI Agent", group: "工具与应用" },
    { id: "inference", label: "推理优化", group: "工程与研究" },
    { id: "training", label: "训练与数据", group: "工程与研究" },
    { id: "rag", label: "RAG 与检索", group: "工程与研究" },
    { id: "multimodal", label: "多模态", group: "基础模型" },
    { id: "image", label: "图像生成与编辑", group: "创作模型" },
    { id: "3d", label: "3D 资产生成", group: "空间模型" },
  ];
  const image = makeRecommendation("image-paper");
  image.article.technical_topics = ["image"];
  data.sections.find((section) => section.id === "papers")!.items = [
    makeRecommendation("llm-paper"),
    image,
  ];
  const { writes, policyReads } = await fixtures(page, data);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const width of [1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("about:blank");
    await page.goto("/#/?tab=papers");
    await expect(page.getByTestId("recommendation-item")).toHaveCount(2);
    await expect(page.locator(".policy-panel")).toHaveCount(0);
    await expect(page.getByRole("spinbutton")).toHaveCount(0);
    const more = page.getByRole("button", { name: "更多方向", exact: true });
    await more.click();
    let directory = page.getByRole("dialog", {
      name: "选择技术方向",
      exact: true,
    });
    await expect(directory.getByRole("link")).toHaveCount(data.topics.length);
    await expect(
      directory.getByRole("textbox", { name: "搜索技术方向" }),
    ).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(more).toBeFocused();
    await more.click();
    directory = page.getByRole("dialog", { name: "选择技术方向", exact: true });
    await directory.getByRole("textbox", { name: "搜索技术方向" }).fill("图像");
    const choice = directory.getByRole("link", {
      name: "图像生成与编辑",
      exact: true,
    });
    await choice.focus();
    await page.keyboard.press("Enter");
    await expect(directory).toHaveCount(0);
    await expect(page).toHaveURL(/topic=image/);
    await expect(page).toHaveURL(/tab=papers/);
    await expect(
      page.getByRole("heading", {
        name: "图像生成与编辑 · 前沿论文",
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByTestId("recommendation-item")).toHaveCount(1);
    await expect(page.getByTestId("recommendation-item")).toHaveAttribute(
      "data-article-id",
      "image-paper",
    );
    const nav = page.getByRole("navigation", { name: "技术方向" });
    await expect(
      nav.getByRole("link", { name: "图像生成与编辑", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.reload();
    await expect(
      page.getByRole("heading", {
        name: "图像生成与编辑 · 前沿论文",
        exact: true,
      }),
    ).toBeVisible();
    await page.goBack();
    await expect(
      nav.getByRole("link", { name: "全部方向", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.goForward();
    await expect(
      nav.getByRole("link", { name: "图像生成与编辑", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.getByRole("tab", { name: /^模型/ }).click();
    await expect(
      page.getByRole("link", { name: "全部模型资讯", exact: true }),
    ).toHaveAttribute("href", /content_type=models&topic=image/);
    await page.getByRole("tab", { name: /^项目/ }).click();
    for (const link of await page
      .getByRole("link", { name: "查看项目", exact: true })
      .all())
      await expect(link).toHaveAttribute("href", /topic=image/);
    await nav.getByRole("link", { name: "全部方向", exact: true }).click();
    await expect(page).not.toHaveURL(/topic=/);
    await expect(page).toHaveURL(/tab=projects/);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  expect(policyReads).toEqual([]);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});

test("fixture: numeric recommendation options are optional settings rather than homepage navigation", async ({
  page,
}) => {
  const { writes, policyReads } = await fixtures(page, makeDashboard());
  await page.goto("/#/");
  await expect(
    page.getByRole("heading", { name: "精选推荐", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".policy-panel")).toHaveCount(0);
  expect(policyReads).toEqual([]);
  await page
    .getByRole("navigation", { name: "主导航" })
    .getByRole("link", { name: "系统设置", exact: true })
    .click();
  const panel = page.locator(".policy-panel");
  await expect(panel).toBeVisible();
  await expect(panel).not.toHaveAttribute("open");
  await expect(
    panel.getByLabel("模型展示条数", { exact: true }),
  ).not.toBeVisible();
  await panel.getByText("高级推荐设置", { exact: true }).click();
  await expect(panel.getByLabel("模型展示条数", { exact: true })).toHaveValue(
    "6",
  );
  await expect(panel.getByLabel("大模型推荐份额", { exact: true })).toHaveValue(
    "1",
  );
  expect(policyReads.length).toBeGreaterThan(0);
  expect(writes).toEqual([]);
});

test("fixture: recommendation tabs preserve topic, history, keyboard focus and panel associations", async ({
  page,
}) => {
  const data = makeDashboard({
    emerging_projects: [makeProject("featured-project")],
  });
  data.sections.find((section) => section.id === "hot")!.items = [
    makeRecommendation("seen-high-score", {
      recommendation_score: 95,
      exposure: { revision_hash: "seen", status: "unchanged", recent: true },
    }),
  ];
  data.sections.find((section) => section.id === "papers")!.items = [
    makeRecommendation("unseen-paper"),
  ];
  const { writes } = await fixtures(page, data);
  await page.goto("/#/?topic=llm");
  const cards = page.locator(".featured-list > [data-article-id]");
  await expect(cards).toHaveCount(3);
  expect(
    await cards.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-article-id")),
    ),
  ).toEqual(["featured-project", "unseen-paper", "seen-high-score"]);
  const panel = page.getByRole("tabpanel");
  for (const tab of await page.getByRole("tab").all())
    await expect(tab).toHaveAttribute("aria-controls", "recommendation-panel");
  await expect(panel).toHaveAttribute(
    "aria-labelledby",
    (await page
      .getByRole("tab", { name: /^精选/ })
      .getAttribute("id")) as string,
  );
  await page.getByRole("tab", { name: /^论文/ }).click();
  await page.getByRole("tab", { name: /^模型/ }).click();
  await page.reload();
  await expect(page.getByRole("tab", { name: /^模型/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page).toHaveURL(/topic=llm/);
  await page.goBack();
  await expect(page.getByRole("tab", { name: /^论文/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.goForward();
  await expect(page.getByRole("tab", { name: /^模型/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: /^模型/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /^工具/ })).toBeFocused();
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: /^论文/ })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /^精选/ })).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: /^论文/ })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(page.getByRole("tab", { name: /^精选/ })).toBeFocused();
  await page.getByRole("tab", { name: /^项目/ }).click();
  await page
    .getByRole("navigation", { name: "技术方向" })
    .getByRole("link", { name: "推理优化", exact: true })
    .click();
  await expect(page).toHaveURL(/topic=inference/);
  await expect(page.getByRole("tab", { name: /^项目/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(writes).toEqual([]);
});

test("fixture: a project-only featured view shows real candidates rather than a growth empty state", async ({
  page,
}) => {
  const { writes } = await fixtures(
    page,
    makeDashboard({ emerging_projects: [makeProject("only-project")] }),
  );
  await page.goto("/#/");
  await expect(page.getByTestId("project-item")).toContainText(
    "fixture/only-project",
  );
  await expect(page.getByTestId("project-item")).toContainText(
    "短期增长待观测",
  );
  await expect(
    page.getByText("暂未观测到明显增长", { exact: true }),
  ).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("fixture: feed sort scopes and facet deep links recover through browser history", async ({
  page,
}) => {
  const { writes, articleQueries } = await fixtures(page, makeDashboard());
  await page.goto("/#/feed?category=agents");
  const facets = page.getByRole("region", { name: "资讯分类面板" });
  await expect(facets.getByRole("tab", { name: /^资讯分类/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    facets.getByRole("radio", { name: "智能体", exact: true }),
  ).toBeChecked();
  await page.getByRole("button", { name: "收起分类面板" }).click();
  await expect(
    facets.getByRole("button", { name: "清除资讯分类" }),
  ).toBeVisible();
  await page.getByLabel("排序方式").selectOption("collected");
  await expect(facets.getByRole("tabpanel")).toHaveCount(0);
  await page.evaluate(() => {
    location.hash = "#/feed?topic=llm";
  });
  await expect(
    facets.getByRole("radio", { name: "大模型", exact: true }),
  ).toBeChecked();
  await page.goBack();
  await expect(
    facets.getByRole("radio", { name: "智能体", exact: true }),
  ).toBeChecked();
  await page.goForward();
  await expect(
    facets.getByRole("radio", { name: "大模型", exact: true }),
  ).toBeChecked();
  await page.getByLabel("排序方式").selectOption("downloads");
  await expect(page).toHaveURL(/source=hf-models/);
  await page.getByRole("tab", { name: "论文", exact: true }).click();
  await expect(page).not.toHaveURL(/source=|sort=/);
  await expect(page).toHaveURL(/topic=llm/);
  await expect
    .poll(() =>
      articleQueries.some(
        (query) =>
          query.get("content_type") === "papers" &&
          !query.has("source") &&
          !query.has("sort"),
      ),
    )
    .toBe(true);
  const tab = page.getByRole("tab", { name: "论文", exact: true });
  await expect(tab).toHaveAttribute("aria-controls", "feed-content-panel");
  await expect(
    page.getByRole("tabpanel", { name: "论文", exact: true }),
  ).toHaveAttribute(
    "aria-labelledby",
    (await tab.getAttribute("id")) as string,
  );
  await page.getByLabel("排序方式").selectOption("points");
  await expect(page).toHaveURL(/source=hackernews/);
  await page.getByRole("tab", { name: "模型", exact: true }).click();
  await expect(page).not.toHaveURL(/source=|sort=/);
  expect(writes).toEqual([]);
});
