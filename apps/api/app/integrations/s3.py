"""S3 / MinIO object storage helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import settings


@lru_cache
def get_s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def build_original_object_key(user_id: str, file_id: str) -> str:
    return f"users/{user_id}/files/{file_id}/original"


def create_presigned_upload_url(*, bucket: str, key: str, content_type: str | None) -> str:
    params: dict[str, Any] = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=settings.s3_presign_expire_seconds,
    )


def get_object_metadata(*, bucket: str, key: str) -> dict[str, Any]:
    """Return HeadObject response. Raises if the object is missing."""
    return get_s3_client().head_object(Bucket=bucket, Key=key)


def ensure_bucket_exists(bucket: str | None = None) -> None:
    bucket = bucket or settings.s3_bucket
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
