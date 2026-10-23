# Third-party notices

Portions of `backend/frontiersignal/collectors/rss.py` (feed entry parsing) and
`backend/frontiersignal/similarity.py` (SimHash) are adapted from AI News Brief:

- Author: frankzch, Copyright (c) 2026 frankzch
- Repository: https://github.com/frankzch/ai-news-brief
- Revision: 3b3e182384b27461ebed8512c9e506c7a2fbb002
- Original files: src/rss_fetcher.py, src/lsh_dedup.py
- License: MIT, preserved in licenses/ai-news-brief-MIT.txt
- Changes: separate network/parse responsibilities, nullable dates, typed records,
  bounded content, signed 64-bit distance correction and non-destructive linking.

No source code from the other five audited repositories is included.
Runtime and development dependencies retain their own licenses in their distributions.

`frontend/src/components/ui/` contains five components generated from the official
shadcn/ui registry using shadcn CLI 4.22.1 on 2026-10-22. Copyright (c) 2023 shadcn,
MIT license preserved in `licenses/shadcn-ui-MIT.txt`.

The three PNGs in `frontend/public/sources/` are publisher avatars fetched on
2026-10-22 from `https://github.com/huggingface.png?size=64`,
`https://github.com/openai.png?size=64`, and
`https://github.com/google-deepmind.png?size=64` (64x64 PNG).
They identify their respective sources; their trademarks remain with their owners
and are not included in the code's MIT attribution.
