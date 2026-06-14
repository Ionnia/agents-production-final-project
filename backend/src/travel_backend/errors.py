from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .i18n import choose_locale, message


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message_text: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message_text = message_text
        self.details = details


def request_locale(request: Request) -> str:
    settings = get_settings()
    return choose_locale(
        request.headers.get("accept-language"),
        settings.supported_locales,
        settings.default_locale,
    )


def error_payload(
    code: str, locale: str, custom_message: str | None = None, details: Any = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": custom_message or message(code, locale)}
    if details is not None:
        body["details"] = details
    return {"error": body}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, request_locale(request), exc.message_text, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = {
            "fields": [
                {
                    "location": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors()
            ]
        }
        return JSONResponse(
            status_code=422,
            content=error_payload("validation_error", request_locale(request), details=details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_payload("internal", request_locale(request)),
        )
