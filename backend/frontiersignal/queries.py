import re
from datetime import datetime

from sqlalchemy import func, or_, select

from .models import Article


def article_query(
    q: str = "",
    source: str | None = None,
    category: str | None = None,
    favorite: bool | None = None,
    read: bool | None = None,
    status: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    dialect="postgresql",
):
    statement = select(Article)
    if source:
        statement = statement.where(Article.source_id == source)
    if category:
        statement = statement.where(Article.category == category)
    if favorite is not None:
        statement = statement.where(Article.is_favorite == favorite)
    if read is not None:
        statement = statement.where(Article.is_read == read)
    if status:
        statement = statement.where(Article.status == status)
    timestamp = func.coalesce(Article.published_at, Article.collected_at)
    if after:
        statement = statement.where(timestamp >= after)
    if before:
        statement = statement.where(timestamp < before)
    query = q.strip()
    if query:
        document = (
            func.coalesce(Article.title, "")
            + " "
            + func.coalesce(Article.title_zh, "")
            + " "
            + func.coalesce(Article.body, "")
            + " "
            + func.coalesce(Article.summary_zh, "")
        )
        if (
            dialect == "postgresql"
            and re.search(r"[A-Za-z0-9]", query)
            and not re.search(r"[\u3400-\u9fff]", query)
        ):
            statement = statement.where(
                func.to_tsvector("simple", document).bool_op("@@")(
                    func.websearch_to_tsquery("simple", query)
                )
            )
        else:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(
                or_(
                    Article.title.ilike(f"%{escaped}%", escape="\\"),
                    Article.title_zh.ilike(f"%{escaped}%", escape="\\"),
                    Article.body.ilike(f"%{escaped}%", escape="\\"),
                    Article.summary_zh.ilike(f"%{escaped}%", escape="\\"),
                )
            )
    return statement
