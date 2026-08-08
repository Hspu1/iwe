class BaseAppError(Exception):
    default_message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class SafeStartError(BaseAppError):
    default_message: str = "Application failed to start --> infrastructure is down"


class PostgresNotReachableError(BaseAppError):
    default_message: str = "PostgreSQL isn't reachable/initialized"
