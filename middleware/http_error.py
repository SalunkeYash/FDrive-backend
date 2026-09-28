from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        content={"ok": False, "message": exc.detail},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def http422_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        content={"ok": False, "message": exc.errors()},
        status_code=422,
    )
