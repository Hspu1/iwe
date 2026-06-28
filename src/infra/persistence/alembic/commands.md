# **alembic commands**

## initialization
> uv run alembic init -t async some_directory

## revision
> uv run alembic -c deploy/alembic/alembic.ini revision --autogenerate -m "initial"

## upgrade
> uv run alembic -c deploy/alembic/alembic.ini upgrade head

## specific upgrade/downgrade
> uv run alembic -c deploy/alembic/alembic.ini upgrade <revision>
>
> uv run alembic -c deploy/alembic/alembic.ini downgrade <revision>

#### or (just one)
> uv run alembic -c deploy/alembic/alembic.ini upgrade +1
>
> uv run alembic -c deploy/alembic/alembic.ini downgrade -1

## monitoring
> uv run alembic -c deploy/alembic/alembic.ini current
>
> uv run alembic -c deploy/alembic/alembic.ini history
>
> uv run alembic -c deploy/alembic/alembic.ini heads
