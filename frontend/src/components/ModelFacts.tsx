import { ArrowUpRight, Box, Code2, FileText } from "lucide-react";
import { dateTime, type Article } from "../lib/api";

const tasks: Record<string, string> = {
  "text-generation": "文本生成",
  "text2text-generation": "文本转换",
  "image-text-to-text": "图文理解",
  "visual-question-answering": "视觉问答",
  "image-to-text": "图像文字识别",
  "document-question-answering": "文档问答",
};
const accessNames: Record<string, string> = {
  public_weights: "公开权重文件",
  gated_weights: "权重需授权",
  unknown: "开放方式待确认",
};
const releaseNames: Record<string, string> = {
  announcement: "官方发布公告",
  preview: "预告 / 预览",
  available: "来源声明已可用",
  update: "版本更新",
  unknown: "模型仓库",
};
const modalityNames: Record<string, string> = {
  "3d": "3D 资产",
  text: "文本",
  image: "图像",
  video: "视频",
  audio: "音频",
};
const specNames: Record<string, string> = {
  output_format: "输出格式线索",
  editability: "参数化 / 可编辑性",
  simulation: "仿真环境声明",
  robot_hardware: "机器人硬件声明",
  resolution: "分辨率线索",
  duration: "时长线索",
  frame_rate: "帧率线索",
  sample_rate: "采样率线索",
  hardware: "运行环境线索",
  streaming: "流式 / 实时线索",
};

export default function ModelFacts({
  article,
  detailed = false,
}: {
  article: Article;
  detailed?: boolean;
}) {
  const model = article.metrics?.model;
  if (!model) return null;
  const specifications = new Map<
    string,
    {
      kinds: string[];
      text: string;
      source_url: string;
      revision: string | null;
    }
  >();
  for (const spec of model.specifications || []) {
    const key = JSON.stringify([spec.text, spec.source_url, spec.revision]);
    const existing = specifications.get(key);
    if (existing) existing.kinds.push(spec.kind);
    else specifications.set(key, { ...spec, kinds: [spec.kind] });
  }
  const links = [
    { href: model.card_url, label: "模型卡", icon: FileText },
    { href: model.weights_url, label: "权重目录", icon: Box },
    { href: model.code_url, label: "代码引用", icon: Code2 },
    { href: model.paper_url, label: "论文引用", icon: FileText },
  ];
  return (
    <div
      className={`model-facts ${detailed ? "is-detailed" : ""}`}
      data-testid="model-facts"
    >
      <div className="model-tags">
        <strong>{model.publisher}</strong>
        <span>{releaseNames[model.release_status] || "状态待确认"}</span>
        {model.task && (
          <span>{model.task_label || tasks[model.task] || model.task}</span>
        )}
        <span>{accessNames[model.access] || "开放方式待确认"}</span>
      </div>
      {detailed && (
        <>
          <dl className="model-details">
            {model.modalities && (
              <>
                <div>
                  <dt>输入模态（Hub 任务声明）</dt>
                  <dd>
                    {model.modalities.inputs
                      .map((key) => modalityNames[key] || key)
                      .join("、")}
                  </dd>
                </div>
                <div>
                  <dt>输出模态（Hub 任务声明）</dt>
                  <dd>
                    {model.modalities.outputs
                      .map((key) => modalityNames[key] || key)
                      .join("、")}
                  </dd>
                </div>
              </>
            )}
            <div>
              <dt>声明版本</dt>
              <dd>{model.version || "未声明"}</dd>
            </div>
            <div>
              <dt>许可证声明</dt>
              <dd>{model.license || "未声明"}</dd>
            </div>
            <div>
              <dt>官方发布日期</dt>
              <dd>{dateTime(model.release_at)}</dd>
            </div>
            {model.hub_created_at && (
              <div>
                <dt>Hub 仓库创建</dt>
                <dd>{dateTime(model.hub_created_at)}</dd>
              </div>
            )}
            {model.hub_updated_at && (
              <div>
                <dt>Hub 仓库更新</dt>
                <dd>{dateTime(model.hub_updated_at)}</dd>
              </div>
            )}
            {model.revision && (
              <div>
                <dt>仓库提交</dt>
                <dd title={model.revision}>
                  <code>{model.revision.slice(0, 12)}</code>
                </dd>
              </div>
            )}
          </dl>
          {model.publisher_evidence && (
            <a
              className="text-link"
              href={model.publisher_evidence}
              target="_blank"
              rel="noreferrer"
            >
              发布者身份依据 <ArrowUpRight size={14} />
            </a>
          )}
          {model.release_evidence && (
            <p className="muted">{model.release_evidence}</p>
          )}
          {!!specifications.size && (
            <details className="model-specifications">
              <summary>规格与运行线索 · 原文摘录</summary>
              <p className="muted">
                来源描述，未作运行验证；示例参数不代表能力上限。
              </p>
              {[...specifications.entries()].map(([key, spec]) => (
                <div className="model-specification" key={key}>
                  <strong>
                    {spec.kinds
                      .map((kind) => specNames[kind] || kind)
                      .join(" / ")}
                  </strong>
                  <blockquote>{spec.text}</blockquote>
                  <a
                    className="text-link"
                    href={spec.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看依据{" "}
                    {spec.revision ? `· ${spec.revision.slice(0, 8)}` : ""}
                    <ArrowUpRight size={14} />
                  </a>
                </div>
              ))}
            </details>
          )}
          {["metadata_only", "unavailable"].includes(model.card_status) && (
            <p className="model-caution">
              模型卡正文尚未完整获取；已保留元数据，已有解读可能来自此前版本。
            </p>
          )}
        </>
      )}
      <div className="model-links">
        {links
          .filter((link) => link.href)
          .map(({ href, label, icon: Icon }) => (
            <a key={label} href={href!} target="_blank" rel="noreferrer">
              <Icon size={14} />
              {label}
              <ArrowUpRight size={12} />
            </a>
          ))}
      </div>
    </div>
  );
}
