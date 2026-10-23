# Adapted from AI News Brief src/lsh_dedup.py, Copyright (c) 2026 frankzch, MIT.
# Signed distance correction and report-linking policy are FrontierSignal changes.
from difflib import SequenceMatcher

from simhash import Simhash
from sqlalchemy import or_, select

from .models import Article, ArticleLink


class _WideSimhash(Simhash):
    @staticmethod
    def _bitarray_from_bytes(value):
        # simhash 2.1.2 multiplies uint8 bits by counts that can exceed 255.
        # Promote before multiplication to preserve weights under NumPy 2.
        return Simhash._bitarray_from_bytes(value).astype("int64")


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
    candidates = (
        await session.scalars(
            select(Article)
            .where(
                Article.id != article.id,
                or_(
                    Article.original_url == article.original_url if article.original_url else False,
                    Article.canonical_url == article.canonical_url
                    if article.canonical_url
                    else False,
                    Article.content_hash == article.content_hash,
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
        if (article.canonical_url and other.canonical_url == article.canonical_url) or (
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
    await session.execute(
        insert(ArticleLink)
        .values(
            left_id=left,
            right_id=right,
            method=method,
            similarity=similarity,
        )
        .on_conflict_do_nothing(index_elements=["left_id", "right_id"])
    )
