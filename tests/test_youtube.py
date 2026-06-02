from unittest.mock import MagicMock

from app.youtube import (
    list_broadcasts,
    list_livestreams_via_uploads,
    get_video_snippet,
    update_title,
)


def _uploads_service(channel_resp, playlist_pages, video_pages):
    """Fake service for the uploads-playlist listing path."""
    service = MagicMock()
    service.channels.return_value.list.return_value.execute.return_value = channel_resp
    service.playlistItems.return_value.list.return_value.execute.side_effect = playlist_pages
    service.videos.return_value.list.return_value.execute.side_effect = video_pages
    return service


def test_list_via_uploads_keeps_only_livestreams():
    channel = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]}
    playlist_pages = [
        {"items": [{"contentDetails": {"videoId": "v1"}}, {"contentDetails": {"videoId": "v2"}}]}
    ]
    video_pages = [
        {
            "items": [
                {
                    "id": "v1",
                    "snippet": {"title": "Stream A"},
                    "liveStreamingDetails": {"actualStartTime": "2026-05-10T18:00:00Z"},
                },
                {"id": "v2", "snippet": {"title": "Plain Upload"}},  # no LSD -> excluded
            ]
        }
    ]
    svc = _uploads_service(channel, playlist_pages, video_pages)
    assert list_livestreams_via_uploads(svc) == [("v1", "Stream A", "2026-05-10T18:00:00Z")]


def test_list_via_uploads_paginates_and_falls_back_to_scheduled():
    channel = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]}
    playlist_pages = [
        {"items": [{"contentDetails": {"videoId": "v1"}}], "nextPageToken": "p2"},
        {"items": [{"contentDetails": {"videoId": "v2"}}]},
    ]
    video_pages = [
        {
            "items": [
                {
                    "id": "v1",
                    "snippet": {"title": "A"},
                    "liveStreamingDetails": {"scheduledStartTime": "2026-05-17T18:00:00Z"},
                },
                {
                    "id": "v2",
                    "snippet": {"title": "B"},
                    "liveStreamingDetails": {"actualStartTime": "2026-05-24T18:00:00Z"},
                },
            ]
        }
    ]
    svc = _uploads_service(channel, playlist_pages, video_pages)
    assert list_livestreams_via_uploads(svc) == [
        ("v1", "A", "2026-05-17T18:00:00Z"),
        ("v2", "B", "2026-05-24T18:00:00Z"),
    ]


def test_list_via_uploads_empty_channel_returns_empty():
    svc = _uploads_service({"items": []}, [], [])
    assert list_livestreams_via_uploads(svc) == []


def test_list_via_uploads_skips_livestream_without_start():
    channel = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]}
    playlist_pages = [{"items": [{"contentDetails": {"videoId": "v1"}}]}]
    video_pages = [{"items": [{"id": "v1", "snippet": {"title": "A"}, "liveStreamingDetails": {}}]}]
    svc = _uploads_service(channel, playlist_pages, video_pages)
    assert list_livestreams_via_uploads(svc) == []


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


def test_list_broadcasts_dedupes_same_id_across_statuses():
    # A broadcast can appear under more than one requested status; it must be returned once.
    pages = [
        {"items": [{"id": "v1", "snippet": {"title": "A", "actualStartTime": "2026-05-10T18:00:00Z"}}]},
        {
            "items": [
                {"id": "v1", "snippet": {"title": "A", "actualStartTime": "2026-05-10T18:00:00Z"}},
                {"id": "v2", "snippet": {"title": "B", "actualStartTime": "2026-05-17T18:00:00Z"}},
            ]
        },
    ]
    service = _make_service(pages)
    result = list_broadcasts(service, ["active", "completed"])
    assert result == [
        ("v1", "A", "2026-05-10T18:00:00Z"),
        ("v2", "B", "2026-05-17T18:00:00Z"),
    ]


def test_list_broadcasts_handles_response_without_items_key():
    service = _make_service([{}])  # no "items", no "nextPageToken"
    assert list_broadcasts(service, ["all"]) == []


def test_list_via_uploads_handles_videos_response_without_items():
    channel = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]}
    playlist_pages = [{"items": [{"contentDetails": {"videoId": "v1"}}]}]
    video_pages = [{}]  # videos.list returns no "items"
    svc = _uploads_service(channel, playlist_pages, video_pages)
    assert list_livestreams_via_uploads(svc) == []


def test_get_video_snippet_returns_snippet():
    service = MagicMock()
    service.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": "A", "categoryId": "22"}}]
    }
    assert get_video_snippet(service, "v1") == {"title": "A", "categoryId": "22"}


def test_get_video_snippet_returns_none_when_no_items():
    service = MagicMock()
    service.videos.return_value.list.return_value.execute.return_value = {}
    assert get_video_snippet(service, "v1") is None


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
