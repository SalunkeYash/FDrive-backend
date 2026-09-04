import logging
from unittest.mock import MagicMock, patch

from workers.__main__ import handle_job

from app.integrations.sqs import enqueue_job


def test_enqueue_job_sends_message() -> None:
    mock_client = MagicMock()
    mock_client.send_message.return_value = {"MessageId": "msg-1"}

    with (
        patch("app.integrations.sqs.settings.sqs_queue_url", "http://localhost:9324/queue/fdrive-jobs"),
        patch("app.integrations.sqs.get_sqs_client", return_value=mock_client),
    ):
        message_id = enqueue_job("generate_thumbnail", {"file_id": "abc"})

    assert message_id == "msg-1"
    mock_client.send_message.assert_called_once()
    body = mock_client.send_message.call_args.kwargs["MessageBody"]
    assert "generate_thumbnail" in body
    assert "abc" in body


def test_enqueue_job_skips_when_queue_unset() -> None:
    with patch("app.integrations.sqs.settings.sqs_queue_url", None):
        assert enqueue_job("generate_thumbnail", {}) is None


def test_handle_job_known_types(caplog) -> None:
    with caplog.at_level(logging.INFO):
        handle_job("generate_thumbnail", {"file_id": "f1"})
        handle_job("purge_expired_trash", {})
        handle_job("unknown", {})
    assert "thumbnail job received" in caplog.text
    assert "purge trash job received" in caplog.text
    assert "unknown job_type" in caplog.text
