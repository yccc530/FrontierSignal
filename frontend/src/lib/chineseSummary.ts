export function summaryText(
  summary: string | null | undefined,
  status?: string,
  error?: string | null,
): string {
  if (summary?.trim()) return summary;
  if (status === "processing") return "中文摘要正在生成，原文已保留。";
  if (status === "failed" || error?.startsWith("模型"))
    return "中文摘要生成失败，原文已保留，可在详情中重试。";
  return "中文摘要待生成，原文已保留。";
}
