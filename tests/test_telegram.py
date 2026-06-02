from unittest.mock import MagicMock, patch

from app.telegram import send_message, get_updates


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


@patch("app.telegram.requests")
def test_get_updates_returns_result_list(mock_requests):
    resp = MagicMock()
    resp.json.return_value = {"ok": True, "result": [{"update_id": 5}]}
    mock_requests.get.return_value = resp
    out = get_updates("TOKEN", offset=4)
    assert out == [{"update_id": 5}]
    args, kwargs = mock_requests.get.call_args
    assert kwargs["params"]["offset"] == 4
