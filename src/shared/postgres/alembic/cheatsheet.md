uv run alembic init -t async some_directory

uv run alembic -c deploy/alembic/alembic.ini revision --autogenerate -m "initial"
uv run alembic -c deploy/alembic/alembic.ini upgrade head

uv run alembic -c deploy/alembic/alembic.ini upgrade <revision>
uv run alembic -c deploy/alembic/alembic.ini downgrade <revision>

uv run alembic -c deploy/alembic/alembic.ini upgrade +1
uv run alembic -c deploy/alembic/alembic.ini downgrade -1

uv run alembic -c deploy/alembic/alembic.ini current
uv run alembic -c deploy/alembic/alembic.ini history
uv run alembic -c deploy/alembic/alembic.ini heads
