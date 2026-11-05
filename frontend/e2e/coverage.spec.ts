import { test, expect } from "@playwright/test";

for (const width of [1024, 1440]) {
  test(`bounded coverage and infrastructure remain explicit at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    const writes: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (entry) => {
      if (
        ["POST", "PATCH", "DELETE"].includes(entry.method()) &&
        entry.url().includes("/api/") &&
        !entry.url().endsWith("/backfill/preview")
      )
        writes.push(`${entry.method()} ${new URL(entry.url()).pathname}`);
    });
    const projects = await (
      await request.get(
        "/api/projects?pool=infrastructure&sort=stars&page_size=100",
      )
    ).json();
    expect(projects.items.length).toBeGreaterThan(0);
    expect(
      projects.items.every(
        (item: { recommendation_score: number }) =>
          item.recommendation_score === 0,
      ),
    ).toBe(true);
    for (const name of [
      "Comfy-Org/ComfyUI",
      "ggml-org/llama.cpp",
      "huggingface/diffusers",
    ])
      expect(
        projects.items.some((item: { name: string }) => item.name === name),
      ).toBe(true);
    await page.goto("/#/projects?pool=infrastructure");
    await expect(
      page.getByRole("button", { name: /^常用基础设施/ }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("project-item")).toHaveCount(
      Math.min(projects.items.length, 12),
    );
    await expect(
      page.getByText("累计指标，不代表近期增长", { exact: false }).first(),
    ).toBeVisible();
    const first = page.getByTestId("project-item").first();
    await expect(first.locator(".project-name")).toHaveText(
      projects.items[0].name,
    );
    await expect(first.locator(":scope > .project-numbers")).toContainText(
      "累计 Stars",
    );
    await expect(first.locator(":scope > .project-numbers")).toContainText(
      "最近代码维护",
    );
    await expect(first.locator(":scope > .project-numbers")).toContainText(
      "许可证声明",
    );
    await expect(
      page.getByRole("option", { name: "增长动量优先" }),
    ).toHaveCount(0);
    expect(
      await page
        .locator(
          ".project-numbers-infrastructure > div:is(:first-child, :nth-child(2)) dd",
        )
        .evaluateAll((elements) =>
          elements.every((element) => {
            const range = document.createRange();
            range.selectNodeContents(element);
            return (
              range.getBoundingClientRect().height <=
                Number.parseFloat(getComputedStyle(element).lineHeight) + 1 &&
              element.scrollWidth <= element.clientWidth
            );
          }),
        ),
    ).toBe(true);
    await page.screenshot({
      path: `../.runtime/p15-projects-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
    await page.getByLabel("项目排序", { exact: true }).selectOption("updated");
    await expect(page).toHaveURL(/sort=updated/);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);

    const audit = await (await request.get("/api/discovery/audit")).json();
    const source = audit.sources.find(
      (entry: { source_id: string }) => entry.source_id === "arxiv-ai",
    );
    expect(source).toBeTruthy();
    await page.goto("/#/sources");
    await page.locator(".coverage-panel > summary").click();
    const table = page.getByRole("table", {
      name: "来源覆盖审计",
      exact: true,
    });
    await expect(table).toBeVisible();
    if (source.days_without_successful_collection?.length)
      await expect(
        table.getByRole("row").filter({ hasText: "arXiv · cs.AI" }),
      ).toContainText(source.days_without_successful_collection[0]);
    const github = table
      .getByRole("row")
      .filter({ hasText: "GitHub AI 项目发现" });
    await github.locator("summary").click();
    await expect(github).toContainText("尚无扫描证据");
    await github.locator("summary").click();
    await page.getByText("有界历史补采", { exact: true }).click();
    await page.getByLabel("补采来源", { exact: true }).selectOption("arxiv-ai");
    const end = new Date();
    end.setUTCDate(end.getUTCDate() - 1);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 4);
    await page
      .getByLabel("补采开始日期", { exact: true })
      .fill(start.toISOString().slice(0, 10));
    await page
      .getByLabel("补采结束日期", { exact: true })
      .fill(end.toISOString().slice(0, 10));
    const submit = page.getByRole("button", {
      name: "开始有界补采",
      exact: true,
    });
    await expect(submit).toBeDisabled();
    await page.getByRole("button", { name: "预览范围", exact: true }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "最多 2 次查询 / 40 个候选" }),
    ).toBeVisible();
    await expect(submit).toBeEnabled();
    expect(
      await page
        .locator(
          ".backfill-control .form-columns input, .backfill-control .form-columns select",
        )
        .evaluateAll((elements) =>
          elements.every(
            (element) => element.getBoundingClientRect().width >= 160,
          ),
        ),
    ).toBe(true);
    await page.getByLabel("补采最多页数", { exact: true }).fill("1");
    await expect(submit).toBeDisabled();
    await page.screenshot({
      path: `../.runtime/p15-coverage-${width}.png`,
      fullPage: true,
      animations: "disabled",
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);

    const budget = await (await request.get("/api/discovery/budget")).json();
    await page.goto("/#/settings");
    await page.getByText("GitHub 发现预算", { exact: false }).first().click();
    await expect(
      page.getByLabel("每轮查询总组数", { exact: true }),
    ).toHaveValue(String(budget.github_queries_per_run));
    await page.getByLabel("每轮查询总组数", { exact: true }).fill("3");
    await expect(
      page.getByLabel("每轮查询总组数", { exact: true }),
    ).toHaveValue("3");
    expect(
      (await (await request.get("/api/discovery/budget")).json())
        .github_queries_per_run,
    ).toBe(budget.github_queries_per_run);
    await page.reload();
    await page.getByText("GitHub 发现预算", { exact: false }).first().click();
    await expect(
      page.getByLabel("每轮查询总组数", { exact: true }),
    ).toHaveValue(String(budget.github_queries_per_run));
    await page.getByText("固定仓库与官方账号依据", { exact: true }).click();
    expect(
      await page
        .locator(".discovery-budget .form-columns input")
        .evaluateAll((elements) =>
          elements.every(
            (element) => element.getBoundingClientRect().width >= 160,
          ),
        ),
    ).toBe(true);
    await expect(
      page.locator(".catalog-list").first().getByRole("link"),
    ).toHaveCount(17);
    await expect(
      page.locator(".catalog-list").last().getByRole("link"),
    ).toHaveCount(10);
    // Capture the new budget surface without the existing private model endpoint form.
    await page
      .locator(".settings-section")
      .first()
      .screenshot({
        path: `../.runtime/p15-budget-${width}.png`,
        animations: "disabled",
      });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(writes).toEqual([]);
    expect(errors).toEqual([]);
  });
}
