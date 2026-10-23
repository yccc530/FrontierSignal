import { expect, test } from "@playwright/test";
const headers = { "X-FrontierSignal": "1" };

test("GLM and Meta filters show real records and collection transfer is visible", async ({
  page,
  request,
}) => {
  for (const [publisher, label] of [
    ["zai", "智谱 / Z.ai"],
    ["meta", "Meta"],
  ]) {
    const response = await request.get(
      `/api/articles?content_type=models&publisher=${publisher}&technical=true`,
    );
    const data = await response.json();
    expect(data.total).toBeGreaterThan(0);
    await page.goto(`/#/feed?content_type=models&publisher=${publisher}`);
    await expect(page.getByLabel("模型发布团队")).toHaveValue(publisher);
    await expect(page.getByTestId("article-row")).toHaveCount(
      Math.min(data.total, 20),
    );
    for (const facts of await page.getByTestId("model-facts").all())
      await expect(facts.locator(".model-tags strong")).toHaveText(label);
  }
  await page.screenshot({
    path: "../.runtime/publishers-batch1-models.png",
    animations: "disabled",
  });
  await page.goto("/#/sources");
  const panel = page.locator(".coverage-panel");
  await panel.locator(":scope > summary").click();
  await expect(panel.getByText("智谱 / Z.ai", { exact: true })).toBeVisible();
  await expect(
    panel.getByText("Meta · facebook", { exact: true }),
  ).toBeVisible();
  await panel.getByText("每日采集接收量（UTC）").click();
  const table = panel.getByRole("table", { name: "每日采集流量记录" });
  await expect(table.locator("tbody tr")).toHaveCount(7);
  await expect(table.getByText(/MiB/).first()).toBeVisible();
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: 1000 });
    const containerBox = await panel.boundingBox();
    const tableBox = await table.boundingBox();
    expect(tableBox!.width).toBeGreaterThan(containerBox!.width * 0.9);
    expect(tableBox!.x + tableBox!.width).toBeLessThanOrEqual(width);
    const contrast = await panel
      .locator(".coverage-traffic > p")
      .evaluate((note) => {
        const foreground = getComputedStyle(note)
          .color.match(/[\d.]+/g)!
          .slice(0, 3)
          .map(Number);
        const canvas = getComputedStyle(document.documentElement)
          .getPropertyValue("--canvas")
          .trim();
        const background = canvas
          .slice(1)
          .match(/.{2}/g)!
          .map((part) => parseInt(part, 16));
        const luminance = (rgb: number[]) =>
          rgb
            .map((value) => {
              const normalized = value / 255;
              return normalized <= 0.04045
                ? normalized / 12.92
                : ((normalized + 0.055) / 1.055) ** 2.4;
            })
            .reduce(
              (sum, value, index) =>
                sum + value * [0.2126, 0.7152, 0.0722][index],
              0,
            );
        const a = luminance(foreground),
          b = luminance(background);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
    await page.screenshot({
      path: `../.runtime/publishers-batch1-traffic-${width}.png`,
      animations: "disabled",
    });
  }
});

test("recommendation shares persist and coverage reports actual observation", async ({
  page,
  request,
}) => {
  const original = await (
    await request.get("/api/recommendation-policy")
  ).json();
  try {
    await page.goto("/");
    await page.getByText("推荐份额", { exact: true }).click();
    await page.getByLabel("模型展示条数", { exact: true }).fill("3");
    await page.getByLabel("3D 资产生成推荐份额", { exact: true }).fill("2");
    await page
      .getByRole("button", { name: "保存推荐设置", exact: true })
      .click();
    await expect(page.locator(".policy-panel").getByRole("status")).toHaveText(
      "推荐设置已保存",
    );
    await page.reload();
    await page.getByText("推荐份额", { exact: true }).click();
    await expect(page.getByLabel("模型展示条数", { exact: true })).toHaveValue(
      "3",
    );
    await expect(
      page.getByLabel("3D 资产生成推荐份额", { exact: true }),
    ).toHaveValue("2");
    await page.goto("/#/sources");
    const panel = page.locator(".coverage-panel");
    await panel.locator(":scope > summary").click();
    await expect(
      panel.getByRole("cell", { name: "3D 资产生成", exact: true }),
    ).toBeVisible();
    await expect(
      panel.getByRole("table", { name: "技术方向覆盖" }).locator("tbody tr"),
    ).toHaveCount(30);
    await page.screenshot({
      path: "../.runtime/desktop-expansion-coverage.png",
      animations: "disabled",
    });
    const report = await (await request.get("/api/discovery/runtime")).json();
    expect(["pending", "gaps", "covered"]).toContain(report.observation.status);
    if (report.observation.observed_hours < 24)
      expect(report.observation.status).toBe("pending");
  } finally {
    expect(
      (
        await request.patch("/api/recommendation-policy", {
          headers,
          data: original,
        })
      ).ok(),
    ).toBe(true);
  }
});

test("all topic preferences survive reload with active collection groups", async ({
  page,
  request,
}) => {
  const original = await (await request.get("/api/settings")).json();
  const topics = await (await request.get("/api/topics")).json();
  expect(topics.length).toBeGreaterThan(8);
  try {
    await page.goto("/");
    await page.getByText("研究偏好", { exact: true }).click();
    await expect(page.getByRole("checkbox")).toHaveCount(topics.length);
    await expect(page.getByText("待专项接入")).toHaveCount(0);
    await page.getByRole("button", { name: "全选方向" }).click();
    await page.getByRole("button", { name: "保存偏好" }).click();
    await expect(page.getByRole("status")).toContainText("偏好已保存");
    await page.reload();
    await page.getByText("研究偏好", { exact: true }).click();
    expect(
      await page
        .getByRole("checkbox")
        .evaluateAll((items) =>
          items.every((item) => (item as HTMLInputElement).checked),
        ),
    ).toBe(true);
    const coverage = await (
      await request.get("/api/discovery/coverage")
    ).json();
    expect(
      coverage.sources
        .flatMap((source: { groups: { topics: string[] }[] }) => source.groups)
        .some((group: { topics: string[] }) => group.topics.includes("3d")),
    ).toBe(true);
    await page.screenshot({
      path: "../.runtime/desktop-all-topics.png",
      animations: "disabled",
    });
  } finally {
    expect(
      (
        await request.patch("/api/preferences", {
          headers,
          data: { topics: original.interest_topics },
        })
      ).ok(),
    ).toBe(true);
  }
});

test("real model filters, metadata, references and source scope persist", async ({
  page,
  request,
}) => {
  const sources = await (await request.get("/api/sources")).json();
  const original = sources.find(
    (source: { id: string }) => source.id === "hf-models",
  );
  const response = await request.get(
    "/api/articles?content_type=models&source=hf-models&topic=coding_models&technical=true&page_size=1",
  );
  expect(response.ok()).toBe(true);
  const data = await response.json();
  expect(data.total).toBeGreaterThan(0);
  const model = data.items[0];
  try {
    await page.goto(
      "/#/feed?content_type=models&source=hf-models&topic=coding_models",
    );
    await expect(page.getByLabel("资讯内容类型")).toHaveValue("models");
    await expect(page.getByLabel("资讯技术主题")).toHaveValue("coding_models");
    const row = page.getByTestId("article-row").first();
    await expect(row.locator(".article-title")).toHaveText(
      model.title_zh || model.title,
    );
    await expect(row.getByTestId("model-facts")).toBeVisible();
    await expect(row.locator("time")).toContainText("Hub 更新");
    await row.locator(".article-title").click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByText("官方发布日期", { exact: true }),
    ).toBeVisible();
    await expect(
      dialog.getByRole("link", { name: "模型卡", exact: true }),
    ).toHaveAttribute("href", model.metrics.model.card_url);
    await page.screenshot({
      path: "../.runtime/desktop-model-detail.png",
      animations: "disabled",
    });
    await page.keyboard.press("Escape");
    await page.getByLabel("模型发布团队").selectOption("qwen");
    await expect(page).toHaveURL(/publisher=qwen/);
    const qwen = await (
      await request.get(
        "/api/articles?content_type=models&source=hf-models&topic=coding_models&publisher=qwen&technical=true",
      )
    ).json();
    await expect(page.getByTestId("article-row")).toHaveCount(
      Math.min(qwen.total, 20),
    );
    await page.getByLabel("资讯技术主题").selectOption("");
    const publisherModels = await (
      await request.get(
        "/api/articles?content_type=models&source=hf-models&publisher=qwen&technical=true",
      )
    ).json();
    expect(publisherModels.total).toBeGreaterThan(0);
    await expect(page.getByTestId("article-row")).toHaveCount(
      Math.min(publisherModels.total, 20),
    );
    const facts = page.getByTestId("model-facts");
    for (const item of await facts.all())
      await expect(item.locator(".model-tags strong")).toHaveText("阿里 Qwen");
    await page.screenshot({
      path: "../.runtime/desktop-model-feed.png",
      animations: "disabled",
    });
    await page.goto("/#/sources");
    const sourceRow = page
      .locator(".source-table tbody tr")
      .filter({ hasText: "Hugging Face 模型发现" });
    await sourceRow.getByText("采集方向与扫描记录", { exact: true }).click();
    const topics = await (await request.get("/api/topics")).json();
    await expect(sourceRow.getByRole("checkbox")).toHaveCount(
      topics.filter((topic: { collectors: string[] }) =>
        topic.collectors.includes("hf_models"),
      ).length,
    );
    for (const checkbox of await sourceRow.getByRole("checkbox").all())
      await checkbox.setChecked(false);
    await sourceRow
      .getByRole("checkbox", { name: "OCR 与文档模型", exact: true })
      .check();
    await sourceRow.getByRole("button", { name: "保存采集范围" }).click();
    await expect(sourceRow.getByRole("status")).toContainText("采集范围已保存");
    await page.reload();
    await sourceRow.getByText("采集方向与扫描记录", { exact: true }).click();
    await expect(
      sourceRow.getByRole("checkbox", { name: "OCR 与文档模型", exact: true }),
    ).toBeChecked();
    await expect(
      sourceRow.getByRole("checkbox", { name: "大模型", exact: true }),
    ).not.toBeChecked();
    await page.screenshot({
      path: "../.runtime/desktop-model-sources.png",
      animations: "disabled",
    });
  } finally {
    expect(
      (
        await request.patch("/api/sources/hf-models", {
          headers,
          data: {
            discovery_topics: original.discovery_scope_customized
              ? original.discovery_topics
              : null,
          },
        })
      ).ok(),
    ).toBe(true);
    expect(
      (
        await request.patch(`/api/articles/${model.id}`, {
          headers,
          data: { is_read: model.is_read },
        })
      ).ok(),
    ).toBe(true);
  }
});

test("creative model topics expose real task metadata and quoted specifications on desktop", async ({
  page,
  request,
}) => {
  const changed: { id: string; is_read: boolean }[] = [];
  try {
    for (const [topic, width] of [
      ["image", 1440],
      ["video", 1024],
      ["audio", 1920],
    ] as const) {
      await page.setViewportSize({ width, height: 1000 });
      const query = new URLSearchParams({
        content_type: "models",
        source: "hf-models",
        topic,
        technical: "true",
      });
      const response = await request.get(
        `/api/articles?${query}&page_size=100`,
      );
      expect(response.ok()).toBe(true);
      const data = await response.json();
      expect(data.total).toBeGreaterThan(0);
      const model = data.items.find(
        (item: {
          id: string;
          metrics: { model: { specifications?: unknown[]; topics: string[] } };
        }) =>
          item.metrics.model.specifications?.length &&
          item.metrics.model.topics.includes(topic) &&
          !changed.some((previous) => previous.id === item.id),
      );
      expect(model).toBeTruthy();
      query.set("q", model.title);
      await page.goto(`/#/feed?${query}`);
      await expect(page.getByLabel("资讯技术主题")).toHaveValue(topic);
      changed.push({ id: model.id, is_read: model.is_read });
      await page
        .getByRole("button", {
          name: model.title_zh || model.title,
          exact: true,
        })
        .click();
      const dialog = page.getByRole("dialog");
      if (model.metrics.model.modalities) {
        await expect(
          dialog.getByText("输入模态（Hub 任务声明）", { exact: true }),
        ).toBeVisible();
        await expect(
          dialog.getByText("输出模态（Hub 任务声明）", { exact: true }),
        ).toBeVisible();
      }
      await dialog
        .getByText("规格与运行线索 · 原文摘录", { exact: true })
        .click();
      const quotes = dialog.locator(".model-specification");
      const unique = new Map<string, { text: string; source_url: string }>();
      for (const spec of model.metrics.model.specifications) {
        unique.set(
          JSON.stringify([spec.text, spec.source_url, spec.revision]),
          spec,
        );
      }
      await expect(quotes).toHaveCount(unique.size);
      for (const [index, spec] of [...unique.values()].entries()) {
        await expect(quotes.nth(index).locator("blockquote")).toHaveText(
          spec.text,
        );
        await expect(quotes.nth(index).getByRole("link")).toHaveAttribute(
          "href",
          spec.source_url,
        );
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(
        await dialog.evaluate(
          (element) => element.scrollWidth <= element.clientWidth + 1,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `../.runtime/desktop-creative-${topic}.png`,
        animations: "disabled",
      });
      await page.keyboard.press("Escape");
    }
  } finally {
    for (const model of changed) {
      expect(
        (
          await request.patch(`/api/articles/${model.id}`, {
            headers,
            data: { is_read: model.is_read },
          })
        ).ok(),
      ).toBe(true);
    }
  }
});
