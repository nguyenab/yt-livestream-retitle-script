from unittest.mock import MagicMock

from app.youtube import list_broadcasts, get_video_snippet, update_title


def _make_service(pages):
    """pages: list of response dicts returned by successive execute() calls."""
    service = MagicMock()
    execute = service.liveBroadcasts.return_value.list.return_value.execute
    execute.side_effect = pages
    return service


def test_list_broadcasts_paginates_and_extracts():
    pages = [
        {
            "items": [
                {
                    "id": "v1",
                    "snippet": {
                        "title": "A",
                        "actualStartTime": "2026-05-10T18:00:00Z",
                    },
                }
            ],
            "nextPageToken": "p2",
        },
        {
            "items": [
                {
                    "id": "v2",
                    "snippet": {
                        "title": "B",
                        "scheduledStartTime": "2026-05-17T18:00:00Z",
                    },
                }
            ]
        },
    ]
    service = _make_service(pages)
    result = list_broadcasts(service, ["all"])
    assert result == [
        ("v1", "A", "2026-05-10T18:00:00Z"),
        ("v2", "B", "2026-05-17T18:00:00Z"),
    ]


def test_list_broadcasts_skips_items_without_start():
    pages = [{"items": [{"id": "v1", "snippet": {"title": "A"}}]}]
    service = _make_service(pages)
    assert list_broadcasts(service, ["all"]) == []


def test_get_video_snippet_returns_snippet():
    service = MagicMock()
    service.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": "A", "categoryId": "22"}}]
    }
    assert get_video_snippet(service, "v1") == {"title": "A", "categoryId": "22"}


def test_update_title_sets_title_and_preserves_snippet():
    service = MagicMock()
    update = service.videos.return_value.update
    update_title(service, "v1", {"title": "Old", "categoryId": "22"}, "New")
    _, kwargs = update.call_args
    assert kwargs["part"] == "snippet"
    assert kwargs["body"] == {
        "id": "v1",
        "snippet": {"title": "New", "categoryId": "22"},
    }
