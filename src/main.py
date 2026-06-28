from fastapi import FastAPI
from src.infra.persistence.postgres import PostgresManager

from src.core.env_conf import pg_stg
from src.core.lifespan import get_lifespan

from .docs import static_docs_urls


def create_app() -> FastAPI:
    pg_manager = PostgresManager(config=pg_stg)

    app = FastAPI(
        title="IwannaEat",
        lifespan=get_lifespan(pg_manager=pg_manager),
        docs_url=None,
        redoc_url=None,
    )
    static_docs_urls(app=app)

    return app


app = create_app()
