"""SQS job queue helpers (Phase 12)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import settings

_SQS_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"max_attempts": 1})


@lru_cache
def get_sqs_client() -> BaseClient:
    return boto3.client(
        "sqs",
        endpoint_url=settings.sqs_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=_SQS_CONFIG,
    )


def enqueue_job(job_type: str, payload: dict[str, Any]) -> str | None:
    """Send a job message. Returns message id, or None if queue is not configured."""
    if not settings.sqs_queue_url:
        return None
    body = json.dumps({"job_type": job_type, "payload": payload})
    response = get_sqs_client().send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=body,
    )
    return response.get("MessageId")
