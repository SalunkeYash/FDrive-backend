"""
FDrive background worker (Phase 12).

Polls SQS for jobs such as thumbnail generation and trash purge.
Run: python -m workers
"""

from __future__ import annotations

import json
import logging
import time

from app.core.config import settings
from app.integrations.sqs import get_sqs_client

logger = logging.getLogger("fdrive.worker")


def handle_job(job_type: str, payload: dict) -> None:
    if job_type == "generate_thumbnail":
        logger.info("thumbnail job received for file_id=%s", payload.get("file_id"))
        # Phase 13 expands real thumbnail generation
        return
    if job_type == "purge_expired_trash":
        logger.info("purge trash job received")
        return
    logger.warning("unknown job_type=%s", job_type)


def poll_forever() -> None:
    if not settings.sqs_queue_url:
        logger.error("SQS_QUEUE_URL is not set; worker idle")
        while True:
            time.sleep(30)

    client = get_sqs_client()
    logger.info("worker started queue=%s", settings.sqs_queue_url)
    while True:
        response = client.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10,
        )
        for message in response.get("Messages", []):
            try:
                body = json.loads(message["Body"])
                handle_job(body.get("job_type", ""), body.get("payload") or {})
                client.delete_message(
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )
            except Exception:
                logger.exception("failed processing message")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    poll_forever()


if __name__ == "__main__":
    main()
