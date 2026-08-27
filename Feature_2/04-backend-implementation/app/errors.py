from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    status_code = 500
    error_code = "APPLICATION_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(ApplicationError):
    status_code = 409
    error_code = "CONFLICT"


class ForbiddenError(ApplicationError):
    status_code = 403
    error_code = "FORBIDDEN"


class InvalidOperationError(ApplicationError):
    status_code = 422
    error_code = "INVALID_OPERATION"


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request,
        error: ApplicationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.message, "code": error.error_code},
        )
