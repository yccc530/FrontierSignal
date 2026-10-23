from sqlalchemy import select

from .models import Article, ArticleEmbedding
from .similarity import save_link


async def store_and_link(
    session, article: Article, vector: list[float], model: str, threshold: float
):
    embedding = ArticleEmbedding(
        article_id=article.id,
        content_hash=article.content_hash,
        model=model,
        dimensions=len(vector),
        vector=vector,
    )
    await session.merge(embedding)
    await session.flush()
    if session.bind.dialect.name != "postgresql":
        return
    distance = ArticleEmbedding.vector.cosine_distance(vector)
    rows = (
        await session.execute(
            select(ArticleEmbedding.article_id, distance.label("distance"))
            .join(Article, Article.id == ArticleEmbedding.article_id)
            .where(
                ArticleEmbedding.model == model,
                ArticleEmbedding.dimensions == len(vector),
                ArticleEmbedding.content_hash == Article.content_hash,
                Article.source_id != article.source_id,
                ArticleEmbedding.article_id != article.id,
            )
            .order_by(distance)
            .limit(5)
        )
    ).all()
    for other_id, distance_value in rows:
        similarity = 1 - distance_value
        if similarity >= threshold:
            left, right = sorted([article.id, other_id])
            await save_link(session, left, right, "embedding", similarity)
