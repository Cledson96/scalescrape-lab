from typing import Any


class ApiError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


class NotFoundError(ApiError):
    def __init__(self, detail: str) -> None:
        super().__init__(404, detail)


class ConflictError(ApiError):
    def __init__(self, detail: dict[str, str | None]) -> None:
        super().__init__(409, detail)
