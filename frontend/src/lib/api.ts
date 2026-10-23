export type Source = {
  id: string;
  name: string;
  kind: string;
  url: string;
  enabled: boolean;
  automatic: boolean;
  interval_minutes: number;
  trust: string;
  last_run_at: string | null;
  last_success_at: string | null;
  last_status: string;
  last_error: string | null;
};
export type Article = {
  id: string;
  source_id: string;
  source: Source;
  title: string | null;
  body: string;
  original_url: string | null;
  author: string | null;
  published_at: string | null;
  collected_at: string;
  status: string;
  is_read: boolean;
  is_favorite: boolean;
  title_zh: string | null;
  summary_zh: string | null;
  category: string | null;
  tags: string[] | null;
  score: number | null;
  is_ai_related: boolean | null;
  evidence: string | null;
  analysis_model: string | null;
  analyzed_at: string | null;
  analysis_error: string | null;
  embedding_error: string | null;
  metrics: ArticleMetrics;
  technical_score: number;
  technical_topics: string[];
  technical_reasons: string[];
  technical_eligible: boolean;
};
export type ArticleDetail = Article & {
  raw_versions: number;
  related: {
    id: string;
    title: string | null;
    title_zh: string | null;
    source: string;
    method: string;
    similarity: number;
  }[];
  attempts: {
    id: string;
    status: string;
    model: string;
    error: string | null;
    created_at: string;
    input_tokens: number | null;
    output_tokens: number | null;
  }[];
};
export type Category = { id: string; label: string; description: string };
export type Stats = {
  total: number;
  favorites: number;
  unread: number;
  pending: number;
  analyzed: number;
  failed: number;
  enabled_sources: number;
  active_tasks: number;
  input_tokens: number | null;
  output_tokens: number | null;
  last_collection: string | null;
};
export type LLMConfig = {
  llm_base_url: string;
  llm_model: string;
  llm_timeout: number;
  llm_max_retries: number;
  llm_batch_size: number;
  llm_json_mode: boolean;
  embedding_model: string;
};
export type SystemSettings = LLMConfig & {
  llm_key_configured: boolean;
  llm_configured: boolean;
  github_token_configured: boolean;
  interest_topics: string[];
  github_queries_per_run: number;
  github_track_per_run: number;
  proxy_configured: boolean;
  scheduler_enabled: boolean;
  config_file: string;
  prefilter_keywords: string[];
  semantic_threshold: number;
};
export type ArticlePage = {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
};
export type TaskRun = {
  id: string;
  source_id: string | null;
  kind: string;
  status: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  added: number;
  updated: number;
  duplicates: number;
  filtered: number;
  failed: number;
  error: string | null;
};
export type ArticleMetrics = {
  kind?: string;
  points?: number | null;
  comments_count?: number | null;
  discussion_url?: string;
  comments_sample?: {
    id: number;
    author: string | null;
    text: string;
    time: number | null;
  }[];
  authors?: string[];
  categories?: string[];
  downloads?: number | null;
  likes?: number | null;
  updated_at?: string | null;
  observed_at?: string;
};
export type Topic = { id: string; label: string };
export type StarGrowth = {
  value: number | null;
  baseline_at: string | null;
  observed_at: string | null;
  window_hours: number | null;
  reason: string;
};
export type Project = {
  id: string;
  article_id: string;
  name: string;
  description: string | null;
  summary_zh: string | null;
  url: string;
  language: string | null;
  license: string | null;
  topics: string[];
  stars: number;
  forks: number;
  growth_24h: StarGrowth;
  growth_7d: StarGrowth;
  momentum: {
    status: "surging" | "rising" | "new" | "watching";
    is_rising: boolean;
    is_new: boolean;
    age_days: number | null;
    acceleration: number | null;
    score: number;
    signal: {
      value: number;
      kind: "snapshot_net" | "github_daily";
      label: string;
      start_at: string;
      end_at: string;
      observed_at: string;
      window_hours: number;
      rate_per_hour: number;
      relative_percent: number | null;
      relative_label: string;
    } | null;
  };
  created_at: string | null;
  pushed_at: string | null;
  updated_at: string | null;
  observed_at: string;
  first_seen_at: string;
  has_code: boolean | null;
  code_evidence: string[];
  latest_release: {
    tag_name: string;
    html_url: string;
    published_at: string | null;
  } | null;
  tracked: boolean;
  recommendation_score: number;
  reasons: string[];
  is_read: boolean;
  is_favorite: boolean;
};
export type Recommendation = {
  article: Article;
  recommendation_score: number;
  reasons: string[];
  related_count: number;
};
export type Dashboard = {
  generated_at: string;
  topics: Topic[];
  interests: string[];
  projects: Project[];
  emerging_projects: Project[];
  sections: {
    id: string;
    title: string;
    window: string;
    items: Recommendation[];
  }[];
  counts: {
    projects: number;
    growth_pending: number;
    rising: number;
    new: number;
  };
  coverage: {
    project_candidates_truncated: boolean;
    article_candidates_truncated: boolean;
    candidate_limit: number;
  };
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-FrontierSignal": "1",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let detail = `请求失败 (${response.status})`;
    try {
      const value = await response.json();
      detail =
        typeof value.detail === "string"
          ? value.detail
          : `输入不符合要求 (${response.status})`;
    } catch {
      /* Preserve the HTTP error for non-JSON responses. */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
export const dateTime = (value: string | null) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "时间未提供";
