import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .similarity import compute_simhash


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        p = urlsplit(value.strip())
        if p.scheme.lower() not in {"http", "https"} or not p.hostname or p.username or p.password:
            return None
        host = p.hostname.encode("idna").decode().lower()
        if ":" in host:
            host = f"[{host}]"
        port = p.port
        if port and (p.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
            host += f":{port}"
        query = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
            and k.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
        ]
        # Preserve path case, trailing slashes, repeated parameters and their order.
        return urlunsplit((p.scheme.lower(), host, p.path or "/", urlencode(query), ""))
    except (ValueError, UnicodeError):
        return None


def plain_text(value: str | None) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"[ \t]+", " ", soup.get_text(" ", strip=True)).strip()


@dataclass
class RawItem:
    platform_id: str | None = None
    title: str | None = None
    body: str = ""
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    raw: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    repository: dict | None = None
    identity_url: str | None = None


def normalize(item: RawItem) -> dict:
    title = plain_text(item.title)[:2000] or None
    body = plain_text(item.body)[:100000]
    url = canonical_url(item.url)
    if not any((title, body, url, item.platform_id)):
        raise ValueError("Source entry contains no usable identity or content")
    content_hash = digest(json.dumps([title, body], ensure_ascii=False))
    identity = item.platform_id or url or content_hash
    published = item.published_at
    if published and published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return dict(
        identity_key=digest(identity),
        platform_id=item.platform_id,
        title=title,
        body=body,
        original_url=item.url if url else None,
        canonical_url=canonical_url(item.identity_url) if item.identity_url else url,
        author=plain_text(item.author)[:500] or None,
        published_at=published,
        content_hash=content_hash,
        fingerprint=compute_simhash(body or title or ""),
    )
