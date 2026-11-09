import type {
  Article,
  Dashboard,
  Project,
  Recommendation,
  Source,
} from "./lib/api";

const time = "2026-11-05T00:00:00Z";
const source: Source = {
  id: "fixture",
  name: "测试来源",
  kind: "rss",
  url: "https://example.com/feed",
  enabled: true,
  automatic: false,
  interval_minutes: 120,
  trust: "official",
  last_run_at: null,
  last_success_at: null,
  last_status: "never",
  last_error: null,
};

export function makeArticle(id: string): Article {
  return {
    id,
    source_id: source.id,
    source,
    title: `测试资讯 ${id}`,
    body: "测试原文",
    original_url: `https://example.com/${id}`,
    author: null,
    published_at: null,
    collected_at: time,
    status: "pending",
    is_read: false,
    is_favorite: false,
    title_zh: null,
    summary_zh: null,
    category: null,
    tags: null,
    score: null,
    is_ai_related: null,
    evidence: null,
    analysis_model: null,
    analyzed_at: null,
    analysis_error: null,
    embedding_error: null,
    metrics: {},
    technical_score: 70,
    technical_topics: ["llm"],
    technical_reasons: [],
    technical_eligible: true,
  };
}

export function makeRecommendation(
  id: string,
  overrides: Partial<Recommendation> = {},
): Recommendation {
  return {
    article: makeArticle(id),
    recommendation_score: 60,
    reasons: ["测试推荐依据"],
    related_count: 0,
    exposure: { revision_hash: `revision-${id}`, status: "new", recent: false },
    ...overrides,
  };
}

export function makeProject(id: string): Project {
  const growth = {
    value: null,
    baseline_at: null,
    observed_at: time,
    window_hours: null,
    reason: "历史快照不足",
  };
  return {
    id,
    article_id: id,
    name: `fixture/${id}`,
    description: "测试项目简介",
    summary_zh: null,
    url: `https://github.com/fixture/${id}`,
    language: "Python",
    license: "MIT",
    topics: ["llm"],
    stars: 100,
    forks: 2,
    growth_24h: growth,
    growth_7d: growth,
    momentum: {
      status: "new",
      is_rising: false,
      is_new: true,
      age_days: 5,
      acceleration: null,
      score: 0,
      signal: null,
    },
    created_at: "2026-10-31T00:00:00Z",
    pushed_at: time,
    updated_at: time,
    observed_at: time,
    first_seen_at: time,
    has_code: null,
    code_evidence: [],
    latest_release: null,
    tracked: true,
    recommendation_score: 60,
    reasons: ["近 30 天创建，增长待观测"],
    is_read: false,
    is_favorite: false,
  };
}

export function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    generated_at: time,
    topics: [
      { id: "llm", label: "大模型" },
      { id: "inference", label: "推理优化" },
    ],
    interests: ["llm"],
    projects: [],
    emerging_projects: [],
    sections: [
      { id: "models", title: "模型资讯", window: "近 30 天", items: [] },
      { id: "tools", title: "工具资讯", window: "近 30 天", items: [] },
      { id: "hot", title: "技术热点", window: "近 72 小时", items: [] },
      { id: "papers", title: "前沿论文", window: "近 14 天", items: [] },
    ],
    policy: { section_limits: {}, topic_weights: {}, repeat_hours: 24 },
    counts: { projects: 0, growth_pending: 0, rising: 0, new: 0 },
    coverage: {
      project_candidates_truncated: false,
      article_candidates_truncated: false,
      candidate_limit: 1000,
    },
    ...overrides,
  };
}
