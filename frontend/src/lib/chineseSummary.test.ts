import { expect, it } from "vitest";
import { summaryText } from "./chineseSummary";

it("uses persisted Chinese and distinguishes missing, processing and failure", () => {
  expect(summaryText("中文摘要", "failed", "旧错误")).toBe("中文摘要");
  expect(summaryText(null, "processing")).toContain("正在生成");
  expect(summaryText(null, "failed")).toContain("生成失败");
  expect(summaryText(null, "filtered", "模型服务返回 HTTP 503")).toContain(
    "生成失败",
  );
  expect(summaryText(null, "filtered", "技术筛选：缺少证据")).toContain(
    "待生成",
  );
  expect(summaryText("  ", "pending")).toContain("待生成");
});
