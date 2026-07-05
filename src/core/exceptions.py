from uuid import UUID


class BaseAppError(Exception):
    default_message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class SafeStartError(BaseAppError):
    default_message: str = "Application failed to start --> infrastructure is down"


class PostgresNotReachableError(BaseAppError):
    default_message: str = "PostgreSQL isn't reachable/initialized"


class RaceConditionCreatingWalletError(BaseAppError):
    default_message: str = "RACE CONDITION creating WALLET (registration process)"


class WalletNotFoundError(BaseAppError):
    default_message: str = "Requested wallet not found"

    def __init__(self, user_id: UUID, *args, **kwargs) -> None:
        self.user_id = user_id
        super().__init__(*args, **kwargs)


class WalletBalanceOverflowError(BaseAppError):
    default_message: str = "Wallet balance limit exceeded"

    def __init__(self, user_id: UUID, *args, **kwargs) -> None:
        self.user_id = user_id
        super().__init__(*args, **kwargs)
