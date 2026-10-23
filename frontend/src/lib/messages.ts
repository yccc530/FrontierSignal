// Translate historical diagnostics for display without rewriting stored task evidence.
const messages: [string, string][] = [
  ["Application stopped before collection completed", "采集完成前应用已停止"],
  ["Application stopped before completion", "任务完成前应用已停止"],
  ["Application interrupted analysis", "应用停止，分析已中断"],
  ["Application is shutting down", "应用正在关闭"],
  ["Application stopped", "应用已停止"],
  ["Source disabled before execution", "执行前来源已被停用"],
  ["Source is disabled", "来源已停用"],
  ["Source not found", "未找到该来源"],
  ["Article not found", "未找到该资讯"],
  ["Collection exceeded the configured task timeout", "采集任务超过设定时限"],
  ["Source did not return a usable RSS/Atom feed", "来源未返回有效的订阅内容"],
  ["Source response exceeds 5 MB", "来源响应超过 5 MB 限制"],
  ["Too many redirects", "来源重定向次数过多"],
  [
    "URL must use HTTPS on an explicitly allowed feed host",
    "订阅地址必须使用已允许域名的 HTTPS 地址",
  ],
  ["Feed DNS resolved to a non-public address", "订阅域名解析到了非公网地址"],
  ["LLM network timeout or connection failure", "模型请求超时或连接失败"],
  ["LLM response failed schema validation", "模型返回内容未通过格式校验"],
  ["LLM is not configured", "尚未配置模型服务"],
  ["LLM HTTP", "模型服务返回 HTTP"],
  ["Entry rejected", "条目处理失败"],
  ["Network request failed", "网络请求失败"],
  ["HN item fetch failed", "科技社区条目获取失败"],
  ["Analysis stopped", "分析中断"],
  ["Provider probe failed", "模型接口验证失败"],
  ["Origin not allowed", "请求来自未允许的站点"],
  ["Management request header required", "管理请求缺少必要的验证信息"],
  ["Failed to fetch", "无法连接本地服务"],
  ["OverflowError", "数值超出范围"],
  ["ClientConnectorError", "无法建立连接"],
  ["ClientOSError", "连接中断"],
  ["TimeoutError", "请求超时"],
];

export function displayError(message: string): string {
  for (const [original, translation] of messages)
    message = message.replaceAll(original, translation);
  return message;
}
