from fastapi import FastAPI

from src.core.env_conf import pg_stg
from src.core.lifespan import get_lifespan
from src.shared.postgres.manager import PostgresManager

from .docs import static_docs_urls
from .modules import modules_router


def create_app() -> FastAPI:
    pg_manager = PostgresManager(config=pg_stg)

    app = FastAPI(
        title="IwannaEat",
        lifespan=get_lifespan(pg_manager=pg_manager),
        docs_url=None,
        redoc_url=None,
    )
    static_docs_urls(app=app)

    app.include_router(modules_router)

    return app


app = create_app()

# run locally w/
# uv run --group dev uvicorn src.main:app --host 127.0.0.1 --port 1488 --workers 1
