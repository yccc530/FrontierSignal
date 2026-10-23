from .arxiv import ArxivCollector
from .github import GitHubCollector
from .github_discovery import GitHubDiscoveryCollector
from .hackernews import HackerNewsCollector
from .huggingface import HuggingFaceCollector
from .rss import RSSCollector

COLLECTORS = {
    "rss": RSSCollector,
    "arxiv": ArxivCollector,
    "hackernews": HackerNewsCollector,
    "github": GitHubCollector,
    "github_discovery": GitHubDiscoveryCollector,
    "hf_models": HuggingFaceCollector,
    "hf_datasets": HuggingFaceCollector,
}
