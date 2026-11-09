import { expect, it } from "vitest";
import { selectFeatured } from "./featured";
import {
  makeDashboard,
  makeProject,
  makeRecommendation,
} from "../test-fixtures";

it("includes projects, de-duplicates article IDs and honors section shares within twelve seats", () => {
  const data = makeDashboard({
    projects: [makeProject("project-1")],
    emerging_projects: [makeProject("project-1"), makeProject("project-2")],
    sections: [
      {
        id: "models",
        title: "模型",
        window: "近 30 天",
        items: [
          makeRecommendation("project-1"),
          ...Array.from({ length: 9 }, (_, i) =>
            makeRecommendation(`model-${i}`),
          ),
        ],
      },
      {
        id: "papers",
        title: "论文",
        window: "近 14 天",
        items: [
          makeRecommendation("model-0"),
          ...Array.from({ length: 4 }, (_, i) =>
            makeRecommendation(`paper-${i}`),
          ),
        ],
      },
      {
        id: "hot",
        title: "讨论",
        window: "近 72 小时",
        items: [makeRecommendation("disabled", { recommendation_score: 999 })],
      },
    ],
    policy: {
      section_limits: { models: 10, papers: 5, hot: 0 },
      topic_weights: {},
      repeat_hours: 24,
    },
  });
  const original = structuredClone(data);
  const selected = selectFeatured(data);
  const ids = selected.map((entry) =>
    entry.kind === "project" ? entry.project.article_id : entry.item.article.id,
  );
  expect(selected).toHaveLength(12);
  expect(ids.slice(0, 2)).toEqual(["project-1", "project-2"]);
  expect(new Set(ids).size).toBe(12);
  expect(ids).not.toContain("disabled");
  expect(ids.filter((id) => id.startsWith("model-"))).toHaveLength(7);
  expect(ids.filter((id) => id.startsWith("paper-"))).toHaveLength(3);
  expect(data).toEqual(original);
});

it("prioritizes unexposed queues and preserves server order instead of comparing source heat", () => {
  const data = makeDashboard({
    sections: [
      {
        id: "hot",
        title: "讨论",
        window: "",
        items: [
          makeRecommendation("seen-high-score", {
            recommendation_score: 95,
            exposure: {
              revision_hash: "seen",
              recent: true,
              status: "unchanged",
            },
          }),
        ],
      },
      {
        id: "papers",
        title: "论文",
        window: "",
        items: [
          makeRecommendation("unseen-low-score", { recommendation_score: 50 }),
          makeRecommendation("second-higher-score", {
            recommendation_score: 80,
          }),
        ],
      },
    ],
  });
  expect(
    selectFeatured(data).map(
      (entry) => entry.kind === "article" && entry.item.article.id,
    ),
  ).toEqual(["unseen-low-score", "second-higher-score", "seen-high-score"]);
});

it("shows project-only candidates and fills spare seats without duplicating project articles", () => {
  const projects = Array.from({ length: 4 }, (_, i) =>
    makeProject(`project-${i}`),
  );
  const data = makeDashboard({ emerging_projects: projects });
  expect(
    selectFeatured(data).map(
      (entry) => entry.kind === "project" && entry.project.id,
    ),
  ).toEqual(projects.map((project) => project.id));
  data.sections[0].items = [makeRecommendation("project-3")];
  const selected = selectFeatured(data);
  expect(selected).toHaveLength(4);
  expect(selected.filter((entry) => entry.kind === "project")).toHaveLength(3);
});
