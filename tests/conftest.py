import pytest
from frontiersignal.config import Settings
from frontiersignal.db import Database
from frontiersignal.main import create_app
from frontiersignal.models import Base
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def database(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        scheduler_enabled=False,
        collector_concurrency=1,
        _env_file=None,
    )
    db = Database(settings)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db, settings
    await db.engine.dispose()


@pytest.fixture
async def client(database):
    db, settings = database
    app = create_app(settings, db)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-FrontierSignal": "1"},
        ) as client:
            yield client
