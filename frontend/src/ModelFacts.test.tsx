import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ModelFacts from "./components/ModelFacts";
import { articleTime, type Article, type ModelInfo } from "./lib/api";

afterEach(cleanup);
const model: ModelInfo = {
  id: "fixture/model",
  publisher_id: null,
  publisher: "测试团队",
  publisher_verified: false,
  publisher_evidence: null,
  task: "text-generation",
  topics: ["llm"],
  version: null,
  revision: "abcdef123456abcdef123456abcdef123456abcdef",
  license: null,
  access: "unknown",
  hub_created_at: "2025-01-01T00:00:00Z",
  hub_updated_at: "2026-10-22T00:00:00Z",
  release_at: null,
  release_status: "unknown",
  release_evidence: null,
  card_status: "unavailable",
  card_url: "https://huggingface.co/fixture/model",
  weights_url: null,
  code_url: null,
  paper_url: null,
};
function article(value = model): Article {
  return {
    source: { kind: "hf_models" },
    metrics: { kind: "model", model: value },
    published_at: null,
    collected_at: "2026-10-22T08:00:00Z",
  } as Article;
}

it("keeps missing version and release date unknown while showing distinct Hub timestamps", () => {
  const item = article();
  render(<ModelFacts article={item} detailed />);
  expect(screen.getByText("开放方式待确认")).toBeInTheDocument();
  expect(screen.getAllByText("未声明")).toHaveLength(2);
  expect(screen.getByText("时间未提供")).toBeInTheDocument();
  expect(screen.getByText("Hub 仓库创建")).toBeInTheDocument();
  expect(screen.getByText("Hub 仓库更新")).toBeInTheDocument();
  expect(screen.getByText(/模型卡正文尚未完整获取/)).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "权重目录" }),
  ).not.toBeInTheDocument();
  expect(articleTime(item)).toMatch(/^Hub 更新/);
  expect(articleTime(item)).not.toContain("2025");
});

it("renders supplied source links and does not equate gated weights with open code", () => {
  render(
    <ModelFacts
      article={article({
        ...model,
        access: "gated_weights",
        weights_url: "https://huggingface.co/fixture/model/tree/main",
        paper_url: "https://arxiv.org/abs/2601.00001",
      })}
    />,
  );
  expect(screen.getByText("权重需授权")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "权重目录" })).toHaveAttribute(
    "href",
    "https://huggingface.co/fixture/model/tree/main",
  );
  expect(screen.getByRole("link", { name: "论文引用" })).toHaveAttribute(
    "target",
    "_blank",
  );
  expect(
    screen.queryByRole("link", { name: "代码引用" }),
  ).not.toBeInTheDocument();
});

it("shows creative task modalities and qualified source excerpts without inventing limits", () => {
  render(
    <ModelFacts
      article={article({
        ...model,
        task: "text-to-video",
        task_label: "文生视频",
        modalities: {
          inputs: ["text"],
          outputs: ["video"],
          basis: "text-to-video",
        },
        specifications: [
          {
            kind: "duration",
            text: "The example generates 5 seconds; this is not a maximum.",
            source_url:
              "https://huggingface.co/fixture/model/blob/abcdef/README.md",
            revision: "abcdef123456",
          },
          {
            kind: "frame_rate",
            text: "The example generates 5 seconds; this is not a maximum.",
            source_url:
              "https://huggingface.co/fixture/model/blob/abcdef/README.md",
            revision: "abcdef123456",
          },
        ],
      })}
      detailed
    />,
  );
  expect(screen.getByText("文生视频")).toBeInTheDocument();
  expect(screen.getByText("输入模态（Hub 任务声明）")).toBeInTheDocument();
  expect(screen.getByText("视频")).toBeInTheDocument();
  expect(screen.getByText(/this is not a maximum/)).toBeInTheDocument();
  expect(screen.getByText("时长线索 / 帧率线索")).toBeInTheDocument();
  expect(screen.getAllByText(/this is not a maximum/)).toHaveLength(1);
  expect(screen.getByText(/未作运行验证/)).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: /查看依据/, hidden: true }),
  ).toHaveAttribute(
    "href",
    "https://huggingface.co/fixture/model/blob/abcdef/README.md",
  );
  expect(screen.queryByText("最大时长")).not.toBeInTheDocument();
});
