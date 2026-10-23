import { test, expect } from "@playwright/test";
const headers = { "X-FrontierSignal": "1" };

test("real feed, search, filters, pagination and detail", async ({
  page,
  request,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const initial = await (
    await request.get("/api/articles?technical=true&page_size=1")
  ).json();
  expect(initial.total).toBeGreaterThan(20);
  const article = initial.items[0];
  try {
    await page.goto("/#/feed");
    await expect(page.getByTestId("article-row")).toHaveCount(20);
    await expect
      .poll(() =>
        page
          .locator(".source-mark img")
          .evaluateAll((images) =>
            images.every(
              (image) =>
                (image as HTMLImageElement).complete &&
                (image as HTMLImageElement).naturalWidth > 0,
            ),
          ),
      )
      .toBeTruthy();
    await page.screenshot({
      path: `../.runtime/${info.project.name}-feed.png`,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.getByRole("button", { name: "下一页", exact: true }).click();
    await expect(page).toHaveURL(/page=2/);
    await page.getByRole("button", { name: "上一页", exact: true }).click();
    await page.getByLabel("搜索资讯").fill("vllm");
    await page.getByLabel("搜索资讯").press("Enter");
    const matching = await (
      await request.get("/api/articles?q=vllm&technical=true&page_size=1")
    ).json();
    expect(matching.total).toBeGreaterThan(0);
    await expect(page.locator(".feed-toolbar")).toContainText(
      String(matching.total),
    );
    const match = matching.items[0];
    expect(
      [match.title, match.title_zh, match.body, match.summary_zh].join(" "),
    ).toMatch(/vllm/i);
    await expect(
      page.getByTestId("article-row").first().locator(".article-title"),
    ).toHaveText(match.title_zh || match.title);
    await page.getByRole("button", { name: "清除搜索", exact: true }).click();
    await page.getByLabel("按来源筛选").selectOption("arxiv-ai");
    await expect(page.getByTestId("article-row").first()).toContainText(
      "arXiv",
    );
    await page.getByLabel("按来源筛选").selectOption("");
    await expect(page.locator(".article-title").first()).toHaveText(
      article.title_zh || article.title,
    );
    await page.locator(".article-title").first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog")).toContainText(/原始版本 [1-9]/);
    await page.getByText("查看原始标题与正文", { exact: true }).click();
    await expect(
      page
        .getByRole("dialog")
        .getByRole("heading", { name: article.title, exact: true, level: 3 }),
    ).toBeVisible();
    await page.getByText("原始记录（最近 5 个版本）").click();
    await expect(page.locator(".raw-json")).toContainText("payload_hash");
    await page.screenshot({
      path: `../.runtime/${info.project.name}-detail.png`,
    });
    await page.keyboard.press("Escape");
    expect(errors).toEqual([]);
  } finally {
    await request.patch(`/api/articles/${article.id}`, {
      headers,
      data: { is_read: article.is_read },
    });
  }
});

test("favorite and read states survive reload", async ({ page, request }) => {
  const initial = await (
    await request.get("/api/articles?technical=true&page_size=1")
  ).json();
  const article = initial.items[0];
  try {
    await request.patch(`/api/articles/${article.id}`, {
      headers,
      data: { is_favorite: false, is_read: false },
    });
    await page.goto("/#/feed");
    const row = page.getByTestId("article-row").first();
    await row.getByRole("button", { name: "收藏", exact: true }).click();
    await expect(
      row.getByRole("button", { name: "取消收藏", exact: true }),
    ).toBeVisible();
    await row.getByRole("button", { name: "标为已读", exact: true }).click();
    await expect(
      row.getByRole("button", { name: "标为未读", exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      row.getByRole("button", { name: "取消收藏", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("navigation")
      .getByRole("link", { name: /我的收藏/ })
      .click();
    await expect(page.getByTestId("article-row").first()).toContainText(
      article.title_zh || article.title,
    );
    const saved = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/articles/${article.id}`) &&
        response.request().method() === "PATCH",
    );
    await page
      .getByTestId("article-row")
      .first()
      .getByRole("button", { name: "取消收藏", exact: true })
      .click();
    const response = await saved;
    expect(response.ok()).toBeTruthy();
    expect((await response.json()).is_favorite).toBe(false);
    await expect(
      page
        .getByTestId("article-row")
        .filter({ hasText: article.title_zh || article.title }),
    ).toHaveCount(0);
    const updated = await (
      await request.get(`/api/articles/${article.id}`)
    ).json();
    expect(updated.is_favorite).toBe(false);
  } finally {
    await request.patch(`/api/articles/${article.id}`, {
      headers,
      data: { is_read: article.is_read, is_favorite: article.is_favorite },
    });
  }
});

test("sources persist enabled state and expose task history", async ({
  page,
  request,
}, info) => {
  const sources = await (await request.get("/api/sources")).json();
  const source = sources.find((s: { id: string }) => s.id === "huggingface");
  try {
    await page.goto("/#/sources");
    const toggle = page.getByRole("switch", {
      name: "Hugging Face 官方博客 启用状态",
    });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute(
      "aria-checked",
      String(!source.enabled),
    );
    await page.reload();
    await expect(toggle).toHaveAttribute(
      "aria-checked",
      String(!source.enabled),
    );
    await page.screenshot({
      path: `../.runtime/${info.project.name}-sources.png`,
    });
    await page
      .getByRole("navigation")
      .getByRole("link", { name: /运行任务/ })
      .click();
    await expect(page.getByRole("table")).toContainText(
      "Hugging Face 官方博客",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  } finally {
    await request.patch("/api/sources/huggingface", {
      headers,
      data: { enabled: source.enabled },
    });
  }
});

test("settings show real configuration and save non-secret settings", async ({
  page,
  request,
}, info) => {
  const settings = await (await request.get("/api/settings")).json();
  await page.goto("/#/settings");
  await expect(page.getByLabel("模型名称", { exact: true })).toHaveValue(
    settings.llm_model,
  );
  if (!settings.llm_configured)
    await expect(page.getByRole("button", { name: "验证接口" })).toBeDisabled();
  await page.getByRole("button", { name: "保存配置" }).click();
  await expect(page.getByRole("status")).toContainText("配置已保存");
  await page.screenshot({
    path: `../.runtime/${info.project.name}-settings.png`,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
