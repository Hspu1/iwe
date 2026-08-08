from typing import Annotated

from dotenv import find_dotenv
from pydantic import AfterValidator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

CFG = SettingsConfigDict(
    env_file=find_dotenv(usecwd=True), env_file_encoding="utf-8", extra="ignore"
)


class ScalarSettings(BaseSettings):
    model_config = CFG

    scalar_static_dir: str = "/opt/scalar"


class PostgresSettings(BaseSettings):
    model_config = CFG

    postgres_url: Annotated[PostgresDsn, AfterValidator(str)]


class StripeSettings(BaseSettings):
    model_config = CFG

    stripe_secret_key: str
    stripe_webhook_secret: str


scalar_stg = ScalarSettings()
pg_stg = PostgresSettings()
stripe_stg = StripeSettings()
