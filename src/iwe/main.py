from fastapi import FastAPI

from iwe import scalar_spec
from iwe.core.env_conf import pg_stg
from iwe.core.lifespan import get_lifespan
from iwe.shared.postgres.manager import PostgresManager

from .components import components_router


def create_app() -> FastAPI:
    pg_manager = PostgresManager(config=pg_stg)

    app = FastAPI(
        title="IwannaEat",
        lifespan=get_lifespan(pg_manager_instance=pg_manager),
        docs_url=None,
        redoc_url=None,
    )
    scalar_spec.mount_standalone(app=app)

    app.include_router(components_router)

    return app


app = create_app()
