"""S3 / MinIO object storage helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from dependencies.config import settings


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


def build_preview_object_key(user_id: str, file_id: str, variant: str) -> str:
    return f"users/{user_id}/files/{file_id}/previews/{variant}"


def create_presigned_upload_url(*, bucket: str, key: str, content_type: str | None) -> str:
    params: dict[str, Any] = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=settings.s3_presign_expire_seconds,
    )


def create_presigned_download_url(
    *,
    bucket: str,
    key: str,
    download_filename: str,
    content_type: str | None = None,
    inline: bool = False,
) -> str:
    """Presigned GET so the browser/client downloads directly from storage."""
    # Keep filename safe for Content-Disposition
    safe_name = download_filename.replace('"', "")
    disposition = "inline" if inline else "attachment"
    params: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "ResponseContentDisposition": f'{disposition}; filename="{safe_name}"',
    }
    if content_type:
        params["ResponseContentType"] = content_type
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=settings.s3_presign_expire_seconds,
    )


def create_presigned_part_upload_url(
    *,
    bucket: str,
    key: str,
    upload_id: str,
    part_number: int,
) -> str:
    return get_s3_client().generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": bucket,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=settings.s3_presign_expire_seconds,
    )


def initiate_multipart_upload(*, bucket: str, key: str, content_type: str | None) -> str:
    params: dict[str, Any] = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    response = get_s3_client().create_multipart_upload(**params)
    return response["UploadId"]


def complete_multipart_upload(
    *,
    bucket: str,
    key: str,
    upload_id: str,
    parts: list[dict[str, Any]],
) -> dict[str, Any]:
    return get_s3_client().complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )


def abort_multipart_upload(*, bucket: str, key: str, upload_id: str) -> None:
    get_s3_client().abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)


def get_object_metadata(*, bucket: str, key: str) -> dict[str, Any]:
    """Return HeadObject response. Raises if the object is missing."""
    return get_s3_client().head_object(Bucket=bucket, Key=key)


def object_exists(*, bucket: str, key: str) -> bool:
    try:
        get_object_metadata(bucket=bucket, key=key)
        return True
    except Exception:
        return False


def download_object_bytes(*, bucket: str, key: str) -> bytes:
    response = get_s3_client().get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def upload_object_bytes(
    *,
    bucket: str,
    key: str,
    body: bytes,
    content_type: str | None = None,
) -> None:
    params: dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": body}
    if content_type:
        params["ContentType"] = content_type
    get_s3_client().put_object(**params)


def copy_object(
    *,
    source_bucket: str,
    source_key: str,
    destination_bucket: str,
    destination_key: str,
) -> None:
    get_s3_client().copy_object(
        Bucket=destination_bucket,
        Key=destination_key,
        CopySource={"Bucket": source_bucket, "Key": source_key},
    )


def delete_object(*, bucket: str, key: str) -> None:
    get_s3_client().delete_object(Bucket=bucket, Key=key)


def ensure_bucket_exists(bucket: str | None = None) -> None:
    bucket = bucket or settings.s3_bucket
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
