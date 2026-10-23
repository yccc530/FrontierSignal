# 第三方声明

[返回项目首页](README.zh-CN.md) · [上游复用评估](REUSE_ASSESSMENT.md)

本文件说明实际复用的代码、组件和来源标识。各项原始许可证保留原文，不因中文说明而改变。
FrontierSignal 的项目代码与文档采用 [MIT 许可证](LICENSE)。第三方代码和依赖仍保留各自的版权与许可；项目许可证不重新授权采集内容或第三方商标。

## AI News Brief

`backend/frontiersignal/collectors/rss.py` 的订阅条目解析和
`backend/frontiersignal/similarity.py` 的部分 SimHash 逻辑适配自 AI News Brief。

- 作者与版权：frankzch，Copyright (c) 2026 frankzch。
- 仓库：[frankzch/ai-news-brief](https://github.com/frankzch/ai-news-brief)。
- 复用版本：`3b3e182384b27461ebed8512c9e506c7a2fbb002`。
- 原始文件：`src/rss_fetcher.py`、`src/lsh_dedup.py`。
- 许可证：[MIT 原文](licenses/ai-news-brief-MIT.txt)。
- 适配内容：拆分网络与解析职责、支持缺失日期、统一类型记录、限制正文长度、修正有符号 64 位距离计算，并将跨来源去重改为保留记录的关联。

其余五个已审计仓库的源码未被复制进本项目。运行与开发依赖保留各自分发包中的许可证。

## shadcn/ui

`frontend/src/components/ui/` 中的五个组件于 2026-10-22 使用 shadcn CLI 4.22.1 从官方 registry 生成。
Copyright (c) 2023 shadcn；[MIT 原文](licenses/shadcn-ui-MIT.txt) 已保留。

## 来源标识

`frontend/public/sources/` 中三个 64 × 64 PNG 用于标识对应发布者，于 2026-10-22 获取：

- `https://github.com/huggingface.png?size=64`
- `https://github.com/openai.png?size=64`
- `https://github.com/google-deepmind.png?size=64`

相关商标归各自权利人所有，不包含在上述代码 MIT 声明中。
