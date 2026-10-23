import { test, expect } from "@playwright/test";

const headers = { "X-FrontierSignal": "1" };

test("project reading state persists without fading metrics or descriptions", async ({
  page,
  request,
}) => {
  const response = await request.get("/api/projects?pool=all&page_size=1");
  expect(response.ok()).toBe(true);
  const project = (await response.json()).items[0];
  expect(project).toBeTruthy();
  const articlePath = `/api/articles/${project.article_id}`;
  try {
    expect(
      (
        await request.patch(articlePath, { headers, data: { is_read: false } })
      ).ok(),
    ).toBe(true);
    await page.goto(
      `/#/projects?pool=all&q=${encodeURIComponent(project.name)}`,
    );
    const card = page
      .getByTestId("project-item")
      .filter({ hasText: project.name });
    const title = card.locator(".project-name");
    await expect(card.getByRole("img", { name: "未读" })).toBeVisible();
    const descriptionColor = await card
      .locator(".project-description")
      .evaluate((element) => getComputedStyle(element).color);
    const metrics = card.locator(":scope > .project-numbers");
    const metricsText = await metrics.innerText();
    const link = card.getByRole("link", {
      name: `打开 ${project.name} GitHub`,
    });
    await expect(link).toHaveAttribute("href", project.url);
    for (const icon of [
      link,
      card.getByRole("button", { name: `${project.name} Stars 历史` }),
    ]) {
      await expect(icon).toHaveCSS("width", "34px");
      await expect(icon).toHaveCSS("height", "34px");
      await expect(icon).toHaveCSS("border-radius", "6px");
    }
    await link.hover();
    await expect(page.getByRole("tooltip")).toHaveText("打开 GitHub");
    await title.focus();
    await page.keyboard.press("Tab");
    await expect(link).toBeFocused();
    await expect(link).toHaveCSS("outline-style", "solid");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(link).toHaveCSS("transition-duration", "0s");
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await title.click();
    await expect(
      page.getByRole("dialog").getByRole("button", { name: "标为未读" }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("dialog")
        .getByRole("button", { name: "关闭", exact: true }),
    ).toHaveCSS("width", "34px");
    await page.keyboard.press("Escape");
    await page.mouse.move(0, 0);
    // Closing the dialog restores focus to the title; move it to inspect the resting color.
    await page.getByRole("textbox", { name: "搜索项目", exact: true }).focus();
    await expect(card.getByRole("img", { name: "已读" })).toBeVisible();
    await expect(title).toHaveCSS("color", "rgb(70, 87, 76)");
    await expect(card).toHaveCSS("opacity", "1");
    await expect(card.locator(".project-description")).toHaveCSS(
      "color",
      descriptionColor,
    );
    expect(await metrics.innerText()).toBe(metricsText);
    expect((await (await request.get(articlePath)).json()).is_read).toBe(true);
    await page.reload();
    await expect(card.getByRole("img", { name: "已读" })).toBeVisible();
    await expect(title).toHaveCSS("color", "rgb(70, 87, 76)");
    await title.hover();
    await expect(title).toHaveCSS("color", "rgb(32, 91, 66)");
    await title.click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "标为未读" }).click();
    await expect(
      dialog.getByRole("button", { name: "标为已读" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(card.getByRole("img", { name: "未读" })).toBeVisible();
    await expect(card).not.toHaveClass(/is-read/);
    await page.reload();
    await expect(card.getByRole("img", { name: "未读" })).toBeVisible();
  } finally {
    expect(
      (
        await request.patch(articlePath, {
          headers,
          data: { is_read: project.is_read },
        })
      ).ok(),
    ).toBe(true);
  }
});

test("real recommendations separate observed momentum from new project candidates", async ({
  page,
  request,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const data = await (await request.get("/api/recommendations")).json();
  expect(data.projects.length + data.emerging_projects.length).toBeGreaterThan(
    0,
  );
  expect(
    data.projects.every(
      (project: { momentum: { is_rising: boolean } }) =>
        project.momentum.is_rising,
    ),
  ).toBe(true);
  expect(
    data.emerging_projects.every(
      (project: { momentum: { is_new: boolean } }) => project.momentum.is_new,
    ),
  ).toBe(true);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "技术推荐", exact: true }),
  ).toBeVisible();
  for (const title of [
    "短期增长异动",
    "新项目观察",
    "今日 AI 技术热点",
    "最新前沿论文",
    "官方模型与技术发布",
    "高价值技术发现",
  ])
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
  await expect(page.getByTestId("project-item")).toHaveCount(
    data.projects.length + data.emerging_projects.length,
  );
  const firstProject = data.projects[0] || data.emerging_projects[0];
  const first = page.getByTestId("project-item").first();
  await expect(first).toContainText(firstProject.name);
  await expect(first).toContainText(firstProject.stars.toLocaleString());
  if (firstProject.momentum.signal === null)
    await expect(first).toContainText("待观测");
  else await expect(first).toContainText(firstProject.momentum.signal.label);
  await first.getByText(/增长依据/).click();
  await expect(first).toContainText(firstProject.reasons[0]);
  await first.getByText(/增长依据/).click();
  const ids = await page
    .getByTestId("recommendation-item")
    .evaluateAll((elements) =>
      elements.map((element) => element.getAttribute("data-article-id")),
    );
  expect(new Set(ids).size).toBe(ids.length);
  await page.screenshot({
    path: `../.runtime/${info.project.name}-recommendations.png`,
    animations: "disabled",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByLabel("推荐技术主题").selectOption("inference");
  await expect(page).toHaveURL(/topic=inference/);
  const filtered = await (
    await request.get("/api/recommendations?topic=inference")
  ).json();
  await expect(page.getByTestId("project-item")).toHaveCount(
    filtered.projects.length + filtered.emerging_projects.length,
  );
  expect(errors).toEqual([]);
});

test("projects search, sort, history and favorite use persisted data", async ({
  page,
  request,
}, info) => {
  const data = await (
    await request.get("/api/projects?pool=all&page_size=1")
  ).json();
  const project = data.items[0];
  expect(project).toBeTruthy();
  try {
    await page.goto("/#/projects");
    await expect(
      page.getByRole("button", { name: /^增长异动/ }),
    ).toHaveAttribute("aria-pressed", "true");
    const growing = await (
      await request.get("/api/projects?page_size=12")
    ).json();
    await expect(page.getByTestId("project-item")).toHaveCount(
      growing.items.length,
    );
    await expect(
      page.locator(
        '[data-testid="project-item"][data-momentum="watching"], [data-testid="project-item"][data-momentum="new"]',
      ),
    ).toHaveCount(0);
    await page.getByRole("button", { name: /^新项目/ }).click();
    await expect(page).toHaveURL(/pool=new/);
    const fresh = await (
      await request.get("/api/projects?pool=new&page_size=12")
    ).json();
    await expect(page.getByTestId("project-item")).toHaveCount(
      fresh.items.length,
    );
    await page.getByRole("button", { name: /^全部项目/ }).click();
    await expect(page).toHaveURL(/pool=all/);
    await page
      .getByRole("textbox", { name: "搜索项目", exact: true })
      .fill(project.name);
    await page
      .getByRole("textbox", { name: "搜索项目", exact: true })
      .press("Enter");
    await expect(page.getByTestId("project-item")).toHaveCount(1);
    const row = page.getByTestId("project-item").first();
    await expect(row).toContainText(project.name);
    await row
      .getByRole("button", { name: `${project.name} Stars 历史` })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    const history = await (
      await request.get(`/api/projects/${project.id}/history`)
    ).json();
    await expect(page.getByRole("dialog").locator("tbody tr")).toHaveCount(
      history.length,
    );
    await page.screenshot({
      path: `../.runtime/${info.project.name}-stars-history.png`,
      animations: "disabled",
    });
    await page.keyboard.press("Escape");
    await row
      .getByRole("button", {
        name: `${project.is_favorite ? "取消收藏" : "收藏"} ${project.name}`,
        exact: true,
      })
      .click();
    await expect(
      row.getByRole("button", {
        name: `${project.is_favorite ? "收藏" : "取消收藏"} ${project.name}`,
        exact: true,
      }),
    ).toBeVisible();
    await page.reload();
    await expect(
      row.getByRole("button", {
        name: `${project.is_favorite ? "收藏" : "取消收藏"} ${project.name}`,
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("textbox", { name: "搜索项目", exact: true }).fill("");
    await page
      .getByRole("textbox", { name: "搜索项目", exact: true })
      .press("Enter");
    await page.getByLabel("项目排序").selectOption("stars");
    const ranked = await (
      await request.get("/api/projects?pool=all&sort=stars&page_size=12")
    ).json();
    await expect(page.getByTestId("project-item").first()).toContainText(
      ranked.items[0].name,
    );
    await page.setViewportSize({ width: 1024, height: 1000 });
    const cumulative = page
      .getByTestId("project-item")
      .first()
      .locator(":scope > .project-numbers > div:last-child dd");
    await expect(cumulative).toHaveText(ranked.items[0].stars.toLocaleString());
    const size = await cumulative.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        height: element.getBoundingClientRect().height,
        lineHeight: parseFloat(style.lineHeight),
        width: element.clientWidth,
        scrollWidth: element.scrollWidth,
      };
    });
    expect(size.height).toBeLessThanOrEqual(size.lineHeight + 1);
    expect(size.scrollWidth).toBeLessThanOrEqual(size.width);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({
      path: `../.runtime/${info.project.name}-projects.png`,
      animations: "disabled",
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    if (ranked.total > 12) {
      await page.getByRole("button", { name: "下一页", exact: true }).click();
      await expect(page).toHaveURL(/page=2/);
      const secondPage = await (
        await request.get(
          "/api/projects?pool=all&sort=stars&page_size=12&page=2",
        )
      ).json();
      await expect(page.getByTestId("project-item").first()).toContainText(
        secondPage.items[0].name,
      );
      await page.getByRole("button", { name: "上一页", exact: true }).click();
      await expect(page.getByTestId("project-item").first()).toContainText(
        ranked.items[0].name,
      );
    }
  } finally {
    await request.patch(`/api/articles/${project.article_id}`, {
      headers,
      data: { is_favorite: project.is_favorite, is_read: project.is_read },
    });
  }
});

test("research interests survive reload and retired platforms disappear", async ({
  page,
  request,
}) => {
  const original = (await (await request.get("/api/settings")).json())
    .interest_topics;
  try {
    await page.goto("/");
    await page.getByText("研究偏好", { exact: true }).click();
    const selected = page.getByRole("checkbox", {
      name: "推理优化",
      exact: true,
    });
    if (!(await selected.isChecked())) await selected.check();
    const llm = page.getByRole("checkbox", { name: "大模型", exact: true });
    await llm.setChecked(false);
    await page.getByRole("button", { name: "保存偏好" }).click();
    await expect(page.getByRole("status")).toContainText("偏好已保存");
    await page.reload();
    await page.getByText("研究偏好", { exact: true }).click();
    await expect(llm).not.toBeChecked();
    await expect(selected).toBeChecked();
    const sources = await (await request.get("/api/sources")).json();
    expect(
      sources.some((source: { kind: string }) =>
        ["x", "reddit"].includes(source.kind),
      ),
    ).toBe(false);
    await page.goto("/#/sources");
    await page.getByRole("button", { name: "添加来源" }).click();
    const kinds = page.getByLabel("来源类型");
    await expect(
      kinds.locator('option[value="x"], option[value="reddit"]'),
    ).toHaveCount(0);
    await kinds.selectOption("github_discovery");
    await expect(page.getByRole("dialog")).not.toContainText("API Key");
  } finally {
    await request.patch("/api/preferences", {
      headers,
      data: { topics: original },
    });
  }
});
