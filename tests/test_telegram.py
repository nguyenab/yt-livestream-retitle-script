from unittest.mock import MagicMock, patch

from app.telegram import send_message


@patch("app.telegram.requests")
def test_send_message_posts_json(mock_requests):
    resp = MagicMock()
    resp.json.return_value = {"ok": True}
    mock_requests.post.return_value = resp
    out = send_message("TOKEN", "123", "hello")
    assert out == {"ok": True}
    args, kwargs = mock_requests.post.call_args
    assert "botTOKEN/sendMessage" in args[0]
    assert kwargs["json"] == {"chat_id": "123", "text": "hello"}
