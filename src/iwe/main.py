from fastapi import FastAPI

from iwe import scalar_spec
from iwe.bootstrap.env_conf import pg_stg
from iwe.bootstrap.lifespan import get_lifespan
from iwe.infra.postgres.manager import PostgresManager

from .features import components_router
from .healthz import healthz_router


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
    app.include_router(healthz_router)

    return app


app = create_app()
