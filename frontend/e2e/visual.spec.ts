import { test, expect, type Page } from "@playwright/test";

const pages = [
  {
    route: "/",
    title: "技术推荐",
    api: "/recommendations",
    ready: ".interest-panel",
  },
  {
    route: "/projects?pool=all",
    title: "AI 开源项目",
    api: "/projects",
    ready: ".project-library",
  },
  { route: "/feed", title: "资讯库", api: "/articles", ready: ".article-row" },
  {
    route: "/feed?content_type=models",
    title: "资讯库",
    api: "/articles",
    ready: ".model-facts",
  },
  {
    route: "/favorites",
    title: "我的收藏",
    api: "/articles",
    ready: ".feed-layout",
  },
  {
    route: "/sources",
    title: "信息来源",
    api: "/sources",
    ready: ".source-table",
  },
  { route: "/tasks", title: "运行任务", api: "/tasks", ready: ".task-table" },
  {
    route: "/settings",
    title: "系统设置",
    api: "/settings",
    ready: ".settings-layout",
  },
];

async function checkReadability(page: Page) {
  const result = await page.evaluate(() => {
    const selectors = {
      h1: 28,
      ".project-name, .article-title, .recommend-title": 17,
      ".project-description, .article-preview, .recommend-summary": 15,
      ".nav-label, .page-heading p, .eyebrow, .muted, .recommend-meta, .article-meta, .technical-tags span, .project-footer > span, .project-numbers dt, .project-reason-preview, .data-table th, .source-cell small, .source-url, .task-id, .status-list dt, .status-list dd, .form-stack label, .key-status small, .interest-preview, .state-badge, .empty-state p, .error-banner, .model-tags span, .model-tags strong, .model-links a, .interest-options small": 13,
    };
    const issues: string[] = [];
    const ratios: number[] = [];
    const rgb = (color: string) => color.match(/[\d.]+/g)?.map(Number) || [];
    const luminance = (channels: number[]) =>
      channels.slice(0, 3).reduce((sum, channel, i) => {
        const value = channel / 255;
        return (
          sum +
          (value <= 0.04045
            ? value / 12.92
            : ((value + 0.055) / 1.055) ** 2.4) *
            [0.2126, 0.7152, 0.0722][i]
        );
      }, 0);
    for (const [selector, minSize] of Object.entries(selectors)) {
      for (const element of document.querySelectorAll<HTMLElement>(selector)) {
        if (!element.checkVisibility() || !element.textContent?.trim())
          continue;
        const style = getComputedStyle(element);
        if (parseFloat(style.fontSize) < minSize)
          issues.push(
            `${element.className || element.tagName}: font ${style.fontSize} < ${minSize}`,
          );
        let ancestor: Element | null = element;
        let background = [255, 255, 255];
        while (ancestor) {
          const color = rgb(getComputedStyle(ancestor).backgroundColor);
          if (color.length === 3 || color[3] === 1) {
            background = color;
            break;
          }
          ancestor = ancestor.parentElement;
        }
        const a = luminance(rgb(style.color));
        const b = luminance(background);
        const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        ratios.push(ratio);
        if (ratio < 4.5)
          issues.push(
            `${element.className || element.tagName}: contrast ${ratio.toFixed(2)}`,
          );
      }
    }
    return {
      issues,
      count: ratios.length,
      minimum: Math.min(...ratios),
      bodySize: getComputedStyle(document.body).fontSize,
    };
  });
  expect(result.bodySize).toBe("16px");
  expect(result.count).toBeGreaterThan(10);
  expect(result.issues).toEqual([]);
  expect(result.minimum).toBeGreaterThanOrEqual(4.5);
}

for (const width of [1024, 1440, 1920]) {
  test(`desktop ${width}: readable typography and usable layouts on every page`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    for (const entry of pages) {
      // A hash navigation can reuse fresh Query data without another HTTP request.
      await page.goto("about:blank");
      const response = page.waitForResponse(
        (value) =>
          new URL(value.url()).pathname === `/api${entry.api}` &&
          value.request().method() === "GET",
      );
      await page.goto(`/#${entry.route}`);
      expect((await response).ok()).toBe(true);
      await expect(
        page.getByRole("heading", { name: entry.title, exact: true, level: 1 }),
      ).toBeVisible();
      await expect(page.locator(entry.ready).first()).toBeVisible();
      await expect(page.locator('.empty-state[aria-busy="true"]')).toHaveCount(
        0,
      );
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      const heading = await page
        .locator(".page-heading")
        .evaluate((element) => {
          if (element.children.length < 2) return true;
          const title = element.firstElementChild!.getBoundingClientRect();
          const actions = element.lastElementChild!.getBoundingClientRect();
          return title.right <= actions.left;
        });
      expect(heading).toBe(true);
      await checkReadability(page);
      if (entry.route === "/") {
        const single = page.locator(".project-grid > .project-item:only-child");
        for (const item of await single.all()) {
          expect(
            await item.evaluate(
              (element) =>
                element.getBoundingClientRect().width /
                element.parentElement!.getBoundingClientRect().width,
            ),
          ).toBeGreaterThan(0.99);
        }
        await page.getByText("研究偏好", { exact: true }).click();
        await expect(page.getByRole("checkbox").first()).toBeVisible();
        await page.screenshot({
          path: `../.runtime/ui-desktop-${width}-recommendations.png`,
          animations: "disabled",
        });
        await page.getByText("研究偏好", { exact: true }).click();
      }
      if (entry.route.startsWith("/projects")) {
        const columns = await page
          .locator(".project-library")
          .evaluate(
            (element) =>
              getComputedStyle(element).gridTemplateColumns.split(" ").length,
          );
        expect(columns).toBe(width === 1920 ? 4 : width === 1440 ? 3 : 2);
        await page.screenshot({
          path: `../.runtime/ui-desktop-${width}-projects.png`,
          animations: "disabled",
        });
      }
      if (width === 1024 && entry.route === "/settings")
        await page.screenshot({
          path: "../.runtime/ui-desktop-1024-settings.png",
          animations: "disabled",
        });
      if (entry.route === "/feed?content_type=models")
        await page.screenshot({
          path: `../.runtime/ui-desktop-${width}-models.png`,
          animations: "disabled",
        });
      if (
        width === 1440 &&
        ["/feed", "/sources", "/tasks"].includes(entry.route)
      )
        await page.screenshot({
          path: `../.runtime/ui-desktop-1440-${entry.route.slice(1)}.png`,
          animations: "disabled",
        });
    }
    expect(errors).toEqual([]);
  });
}

test("recommendations expose loading, empty and request failure states", async ({
  page,
  request,
}) => {
  const response = await request.get("/api/recommendations");
  expect(response.ok()).toBe(true);
  const real = await response.json();
  // Empty/error fixtures are browser-only; the persisted intelligence remains untouched.
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let fail = false;
  await page.route("**/api/recommendations*", async (route) => {
    await gate;
    await route.fulfill({
      status: fail ? 503 : 200,
      json: fail
        ? { detail: "推荐服务暂时不可用，请稍后重试" }
        : {
            ...real,
            projects: [],
            emerging_projects: [],
            counts: { projects: 0, rising: 0, new: 0, growth_pending: 0 },
            sections: real.sections.map((section: object) => ({
              ...section,
              items: [],
            })),
          },
    });
  });
  await page.goto("/");
  try {
    await expect(
      page.getByRole("status").filter({ hasText: "正在读取技术推荐" }),
    ).toHaveAttribute("aria-busy", "true");
  } finally {
    release();
  }
  await expect(
    page.getByRole("heading", { name: "暂未观测到明显增长" }),
  ).toBeVisible();
  await expect(page.getByTestId("project-item")).toHaveCount(0);
  await checkReadability(page);
  fail = true;
  await page.reload();
  await expect(page.getByRole("alert")).toHaveText(
    "推荐服务暂时不可用，请稍后重试",
  );
  await expect(page.getByTestId("project-item")).toHaveCount(0);
  await checkReadability(page);
  await page.unroute("**/api/recommendations*");
  await page.reload();
  await expect(page.locator(".interest-panel")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.route("**/api/sources", (route) => route.fulfill({ json: [] }));
  await page.goto("about:blank");
  await page.goto("/#/sources");
  await expect(
    page.getByRole("heading", { name: "暂无信息来源" }),
  ).toBeVisible();
  await expect(page.locator(".source-table")).toHaveCount(0);
  await page.unroute("**/api/sources");
});
