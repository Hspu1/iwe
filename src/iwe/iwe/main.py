from fastapi import FastAPI

from iwe import scalar_spec
from iwe.infra.postgres.manager import PostgresManager
from iwe.shared.env_conf import pg_stg

from .features import components_router
from .healthz import healthz_router
from .lifespan import get_lifespan


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
