# Adapted from AI News Brief src/lsh_dedup.py, Copyright (c) 2026 frankzch, MIT.
# Signed distance correction and report-linking policy are FrontierSignal changes.
from difflib import SequenceMatcher

from simhash import Simhash
from sqlalchemy import Text, cast, func, or_, select

from .models import Article, ArticleLink


class _WideSimhash(Simhash):
    @staticmethod
    def _bitarray_from_bytes(value):
        # simhash 2.1.2 multiplies uint8 bits by counts that can exceed 255.
        # Promote before multiplication to preserve weights under NumPy 2.
        return Simhash._bitarray_from_bytes(value).astype("int64")


def distinct_model_ids(first, second) -> bool:
    left, right = first.metrics or {}, second.metrics or {}
    left_id, right_id = (left.get("model") or {}).get("id"), (right.get("model") or {}).get("id")
    return bool(
        left.get("kind") == right.get("kind") == "model"
        and left_id
        and right_id
        and left_id.casefold() != right_id.casefold()
    )


def compute_simhash(text: str) -> int:
    if not text.strip():
        return 0
    value = _WideSimhash(text).value
    return value - (1 << 64) if value >= (1 << 63) else value


def hamming_distance(first: int, second: int) -> int:
    return ((first ^ second) & ((1 << 64) - 1)).bit_count()


async def link_related(session, article: Article):
    # Bounded candidate window. Relations are evidence candidates, not a claim
    # that the stories describe one verified event. Nothing is deleted.
    references = set(
        (article.metrics or {}).get("model", {}).get("references", [])
        or (article.metrics or {}).get("model_references", [])
    )
    own_refs = set((article.metrics or {}).get("identity_refs", []))
    resource_refs = set((article.metrics or {}).get("reference_refs", []))
    candidates = (
        await session.scalars(
            select(Article)
            .where(
                Article.id != article.id,
                or_(
                    *[
                        cast(Article.metrics["identity_refs"], Text).contains(
                            f'"{ref}"', autoescape=True
                        )
                        for ref in sorted(resource_refs)[:16]
                    ],
                    *[
                        cast(Article.metrics["reference_refs"], Text).contains(
                            f'"{ref}"', autoescape=True
                        )
                        for ref in sorted(own_refs)[:4]
                    ],
                    Article.original_url == article.original_url if article.original_url else False,
                    Article.canonical_url == article.canonical_url
                    if article.canonical_url
                    else False,
                    Article.content_hash == article.content_hash,
                    func.lower(Article.metrics["model"]["id"].as_string()).in_(references)
                    if references
                    else False,
                    *[
                        cast(Article.metrics["model_references"], Text).contains(
                            f'"{ref}"', autoescape=True
                        )
                        for ref in sorted(references)[:12]
                    ],
                    *[
                        cast(Article.metrics["model"]["references"], Text).contains(
                            f'"{ref}"', autoescape=True
                        )
                        for ref in sorted(references)[:12]
                    ],
                ),
            )
            .limit(30)
        )
    ).all()
    recent = (
        await session.scalars(
            select(Article)
            .where(Article.id != article.id)
            .order_by(Article.collected_at.desc())
            .limit(200)
        )
    ).all()
    unique = {a.id: a for a in [*candidates, *recent]}
    for other in unique.values():
        method, similarity = "", 0.0
        other_refs = set(
            (other.metrics or {}).get("model", {}).get("references", [])
            or (other.metrics or {}).get("model_references", [])
        )
        direct = (resource_refs & set((other.metrics or {}).get("identity_refs", []))) | (
            own_refs & set((other.metrics or {}).get("reference_refs", []))
        )
        if distinct_model_ids(article, other) and not direct:
            continue
        if direct:
            kind = next(
                (
                    key
                    for key in ("model", "paper", "dataset", "code")
                    if any(ref.startswith(key + ":") for ref in direct)
                ),
                "code",
            )
            method, similarity = (
                (f"{kind}_reference" if kind in {"model", "paper"} else "resource_reference"),
                1.0,
            )
        elif references & other_refs:
            method, similarity = "model_reference", 1.0
        elif (article.canonical_url and other.canonical_url == article.canonical_url) or (
            article.original_url and other.original_url == article.original_url
        ):
            method, similarity = "same_url", 1.0
        elif article.content_hash == other.content_hash:
            method, similarity = "same_content", 1.0
        elif article.title and other.title and min(len(article.title), len(other.title)) >= 25:
            similarity = SequenceMatcher(
                None, article.title.casefold(), other.title.casefold()
            ).ratio()
            if similarity >= 0.9:
                method = "title_similarity"
        if (
            not method
            and article.fingerprint
            and other.fingerprint
            and min(len(article.body), len(other.body)) >= 200
        ):
            distance = hamming_distance(article.fingerprint, other.fingerprint)
            if distance <= 3:
                method, similarity = "simhash", 1 - distance / 64
        if method:
            left, right = sorted([article.id, other.id])
            await save_link(session, left, right, method, similarity)


async def save_link(session, left, right, method, similarity):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert(ArticleLink).values(
        left_id=left, right_id=right, method=method, similarity=similarity
    )
    if method in {"model_reference", "paper_reference", "resource_reference"}:
        statement = statement.on_conflict_do_update(
            index_elements=["left_id", "right_id"],
            set_={"method": method, "similarity": similarity},
            where=ArticleLink.method.in_(["title_similarity", "simhash", "embedding"]),
        )
    else:
        statement = statement.on_conflict_do_nothing(index_elements=["left_id", "right_id"])
    result = await session.execute(statement.returning(ArticleLink.id))
    return int(result.scalar_one_or_none() is not None)


async def rebuild_explicit_links(session, articles):
    """Bounded exact-reference repair; shared dependencies never link unrelated callers."""
    rows = (
        await session.execute(select(Article.id, Article.metrics).order_by(Article.id).limit(5001))
    ).all()
    identities = {}
    for row in rows[:5000]:
        for identity in (row.metrics or {}).get("identity_refs", []):
            identities.setdefault(identity, []).append(row.id)
    changed, seen = 0, set()
    for article in articles:
        for ref in (article.metrics or {}).get("reference_refs", []):
            for other_id in identities.get(ref, []):
                pair = tuple(sorted([article.id, other_id]))
                if article.id == other_id or pair in seen:
                    continue
                seen.add(pair)
                kind = ref.split(":", 1)[0]
                method = f"{kind}_reference" if kind in {"model", "paper"} else "resource_reference"
                changed += await save_link(session, *pair, method, 1.0)
    return {
        "matched_pairs": len(seen),
        "changed": changed,
        "identity_limit": 5000,
        "truncated": len(rows) > 5000,
    }
