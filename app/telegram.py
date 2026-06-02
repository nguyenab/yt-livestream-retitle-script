from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"


def send_message(token: str, chat_id: str, text: str) -> dict:
    url = _API.format(token=token, method="sendMessage")
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_updates(token: str, offset: int | None = None, timeout: int = 30) -> list:
    url = _API.format(token=token, method="getUpdates")
    params: dict = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(url, params=params, timeout=timeout + 10)
    resp.raise_for_status()
    return resp.json().get("result", [])
