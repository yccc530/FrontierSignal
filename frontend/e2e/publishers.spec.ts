import { test, expect } from "@playwright/test";

test("desktop publisher grid and citation sorting use real API results", async ({
  page,
  request,
}) => {
  const publishers = await (await request.get("/api/publishers")).json();
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/#/feed");
    const panel = page.getByRole("region", { name: "资讯分类面板" });
    await expect(
      panel.locator('.facet-option input[type="radio"]'),
    ).toHaveCount(publishers.length);
    await expect(
      panel.getByRole("radio", { name: "月之暗面 Kimi" }),
    ).toBeVisible();
    await expect(
      panel.getByRole("radio", { name: "xAI · Grok" }),
    ).toBeVisible();
    expect(
      await panel.evaluate((node) => node.scrollWidth <= node.clientWidth),
    ).toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const bounds = await panel.boundingBox();
    expect(bounds!.height).toBeLessThan(650);
    await page.screenshot({
      path: `../.runtime/publisher-grid-${width}.png`,
      animations: "disabled",
    });
  }
  await page.getByRole("radio", { name: "Anthropic · Claude" }).click();
  await expect(
    page.getByRole("radio", { name: "Anthropic · Claude" }),
  ).toBeChecked();
  const records = await (
    await request.get("/api/articles?publisher=anthropic&technical=true")
  ).json();
  expect(records.total).toBeGreaterThan(0);
  await expect(page.getByTestId("article-row")).toHaveCount(
    Math.min(records.total, 20),
  );
  await page.getByLabel("排序方式").selectOption("citations");
  await expect(page.getByLabel("资讯内容类型")).toHaveValue("papers");
  const papers = await (
    await request.get(
      "/api/articles?sort=citations&content_type=papers&technical=true",
    )
  ).json();
  await expect(page.getByTestId("article-row")).toHaveCount(
    Math.min(papers.total, 20),
  );
  expect(
    papers.items.some(
      (item: { metrics: { citations?: { count: number | null } } }) =>
        typeof item.metrics.citations?.count === "number",
    ),
  ).toBe(true);
  const first = page.getByTestId("article-row").first();
  await expect(first.getByRole("link", { name: /被引/ })).toHaveAttribute(
    "href",
    /^https:\/\/openalex.org\/W/,
  );
  await page.getByRole("button", { name: "收起分类面板" }).click();
  await expect(page.getByRole("tabpanel")).toHaveCount(0);
});
