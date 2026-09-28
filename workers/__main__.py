"""
FDrive background worker (Phase 12+).

Polls SQS for jobs such as thumbnail generation and trash purge.
Run: PYTHONPATH=. python -m workers
"""

from __future__ import annotations

import json
import logging
import time
from uuid import UUID

from dependencies.config import settings
from dependencies.sql_session import SessionLocal
from integrations.sqs import get_sqs_client
from service.thumbnail_service import generate_thumbnail_for_file

logger = logging.getLogger("fdrive.worker")


def handle_job(job_type: str, payload: dict) -> None:
    if job_type == "generate_thumbnail":
        file_id = payload.get("file_id")
        if not file_id:
            logger.warning("thumbnail job missing file_id")
            return
        db = SessionLocal()
        try:
            generate_thumbnail_for_file(db, UUID(str(file_id)))
        finally:
            db.close()
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
        try:
            response = client.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=5,
                WaitTimeSeconds=10,
            )
        except Exception:
            logger.exception("SQS receive failed; retrying in 5s")
            time.sleep(5)
            continue

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
