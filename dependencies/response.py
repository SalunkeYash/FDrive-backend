"""Standard API response envelope — matches company backend style."""

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


def _serialize(data: Any) -> Any:
    if data is None:
        return None
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    if isinstance(data, list):
        return [_serialize(item) for item in data]
    if isinstance(data, dict):
        return {key: _serialize(value) for key, value in data.items()}
    return data


def success(
    data: Any = None,
    message: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    content: dict[str, Any] = {"ok": True}
    if message is not None:
        content["message"] = message
    if data is not None:
        content["data"] = _serialize(data)
    return JSONResponse(content=content, status_code=status_code)


def failure(message: str | list[Any], status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        content={"ok": False, "message": message},
        status_code=status_code,
    )
