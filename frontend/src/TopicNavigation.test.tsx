import "@testing-library/jest-dom/vitest";
import { afterEach, expect, it } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import TopicNavigation from "./components/TopicNavigation";
import type { Topic } from "./lib/api";

afterEach(cleanup);

const topics: Topic[] = [
  { id: "llm", label: "大模型", group: "基础模型" },
  { id: "agents", label: "AI Agent", group: "工具与应用" },
  { id: "inference", label: "推理优化", group: "工程与研究" },
  { id: "training", label: "训练与数据", group: "工程与研究" },
  { id: "rag", label: "RAG 与检索", group: "工程与研究" },
  { id: "multimodal", label: "多模态", group: "基础模型" },
  { id: "image", label: "图像生成与编辑", group: "创作模型" },
  { id: "3d", label: "3D 资产生成", group: "空间模型", discovery_ready: false },
];
function Location() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="route">{location.search}</output>
      <button onClick={() => navigate(-1)}>测试后退</button>
      <button onClick={() => navigate(1)}>测试前进</button>
    </>
  );
}
function mount(entry = "/?tab=papers&topic=llm") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <TopicNavigation topics={topics} />
      <Location />
    </MemoryRouter>,
  );
}

it("navigates directly to a topic while retaining the content tab and browser history", () => {
  mount();
  const nav = within(screen.getByRole("navigation", { name: "技术方向" }));
  fireEvent.click(nav.getByRole("link", { name: "AI Agent" }));
  expect(screen.getByTestId("route")).toHaveTextContent(
    "tab=papers&topic=agents",
  );
  expect(nav.getByRole("link", { name: "AI Agent" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  fireEvent.click(screen.getByRole("button", { name: "测试后退" }));
  expect(nav.getByRole("link", { name: "大模型" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  fireEvent.click(screen.getByRole("button", { name: "测试前进" }));
  expect(nav.getByRole("link", { name: "AI Agent" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  fireEvent.click(nav.getByRole("link", { name: "全部方向" }));
  const params = new URLSearchParams(screen.getByTestId("route").textContent!);
  expect(params.get("tab")).toBe("papers");
  expect(params.has("topic")).toBe(false);
});

it("searches the grouped directory and keeps the chosen non-primary topic visible", async () => {
  mount();
  fireEvent.click(screen.getByRole("button", { name: "更多方向" }));
  const dialog = within(
    await screen.findByRole("dialog", { name: "选择技术方向" }),
  );
  expect(dialog.getByRole("region", { name: "创作模型" })).toBeVisible();
  expect(dialog.getByText("待专项接入")).toBeVisible();
  fireEvent.change(dialog.getByRole("textbox", { name: "搜索技术方向" }), {
    target: { value: "3d" },
  });
  expect(
    dialog.queryByRole("link", { name: "大模型" }),
  ).not.toBeInTheDocument();
  fireEvent.click(dialog.getByRole("link", { name: /3D 资产生成/ }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("navigation", { name: "技术方向" })).getByRole(
      "link",
      { name: "3D 资产生成" },
    ),
  ).toHaveAttribute("aria-current", "page");
  expect(screen.getByTestId("route")).toHaveTextContent("topic=3d");
});

it("restores a non-primary deep link and reports an empty directory search without numeric controls", async () => {
  mount("/?topic=image&tab=models");
  expect(screen.getByRole("link", { name: "图像生成与编辑" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  fireEvent.click(screen.getByRole("button", { name: "更多方向" }));
  const dialog = within(await screen.findByRole("dialog"));
  fireEvent.change(dialog.getByRole("textbox", { name: "搜索技术方向" }), {
    target: { value: "no-such-topic" },
  });
  expect(dialog.getByRole("status")).toHaveTextContent("没有匹配的技术方向");
  expect(dialog.queryByRole("link")).not.toBeInTheDocument();
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  fireEvent.click(dialog.getByRole("button", { name: "关闭" }));
  fireEvent.click(screen.getByRole("button", { name: "更多方向" }));
  expect(screen.getByRole("textbox", { name: "搜索技术方向" })).toHaveValue("");
});
