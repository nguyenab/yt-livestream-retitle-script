from __future__ import annotations

import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
_NUM_RETRIES = 3  # googleapiclient applies exponential backoff for 5xx/429


def build_service(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def list_broadcasts(service, statuses):
    """Return [(video_id, title, start_iso)] for the given broadcastStatus values.

    statuses: iterable from {'all','active','upcoming','completed'}.
    Uses liveBroadcasts.list, which returns only livestreams (never plain uploads).
    start_iso prefers actualStartTime, falling back to scheduledStartTime; items
    with neither are skipped.
    """
    results = []
    seen = set()
    for status in statuses:
        page_token = None
        while True:
            resp = (
                service.liveBroadcasts()
                .list(
                    part="snippet,status",
                    broadcastStatus=status,
                    broadcastType="all",
                    maxResults=50,
                    pageToken=page_token,
                )
                .execute(num_retries=_NUM_RETRIES)
            )
            for item in resp.get("items", []):
                vid = item["id"]
                if vid in seen:
                    continue
                snip = item.get("snippet", {})
                start = snip.get("actualStartTime") or snip.get("scheduledStartTime")
                if not start:
                    continue
                seen.add(vid)
                results.append((vid, snip.get("title", ""), start))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return results


def list_livestreams_via_uploads(service):
    """Return [(video_id, title, start_iso)] for the channel's livestreams, sourced from
    the uploads playlist and filtered to videos that carry liveStreamingDetails.

    This is a more reliable fallback than liveBroadcasts.list for completed history: it
    catches streams produced by an external encoder / persistent stream key that may never
    appear under liveBroadcasts. It stays livestreams-only by keeping a video only if it has
    a liveStreamingDetails block (plain uploads have none). start_iso prefers
    actualStartTime, falling back to scheduledStartTime; items with neither are skipped.

    Quota: channels.list (~1) + playlistItems.list (~1/page) + videos.list (~1/50 ids).
    """
    channel = (
        service.channels()
        .list(part="contentDetails", mine=True)
        .execute(num_retries=_NUM_RETRIES)
    )
    items = channel.get("items", [])
    if not items:
        return []
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids = []
    page_token = None
    while True:
        resp = (
            service.playlistItems()
            .list(part="contentDetails", playlistId=uploads_id, maxResults=50, pageToken=page_token)
            .execute(num_retries=_NUM_RETRIES)
        )
        for item in resp.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    results = []
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        resp = (
            service.videos()
            .list(part="snippet,liveStreamingDetails", id=",".join(batch))
            .execute(num_retries=_NUM_RETRIES)
        )
        for video in resp.get("items", []):
            lsd = video.get("liveStreamingDetails")
            if not lsd:
                continue  # plain upload, not a livestream
            start_iso = lsd.get("actualStartTime") or lsd.get("scheduledStartTime")
            if not start_iso:
                continue
            results.append((video["id"], video.get("snippet", {}).get("title", ""), start_iso))
    return results


def list_playlist_video_ids(service, playlist_id):
    """Return the set of video ids currently in a playlist (read live each run, so
    videos added to the playlist later are picked up automatically). Quota ~1/page.
    """
    ids: set[str] = set()
    page_token = None
    while True:
        resp = (
            service.playlistItems()
            .list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=page_token,
            )
            .execute(num_retries=_NUM_RETRIES)
        )
        for item in resp.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                ids.add(vid)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def fetch_durations(service, video_ids):
    """Return {video_id: duration_seconds} for the given ids via videos.list.

    Batched 50 ids per call (1 quota unit each). Videos still processing may report a
    zero/absent duration; callers treat unknown length as "not long enough".
    """
    from app.dates import parse_iso_duration

    out: dict[str, int] = {}
    ids = list(video_ids)
    for start in range(0, len(ids), 50):
        batch = ids[start : start + 50]
        resp = (
            service.videos()
            .list(part="contentDetails", id=",".join(batch))
            .execute(num_retries=_NUM_RETRIES)
        )
        for video in resp.get("items", []):
            dur = video.get("contentDetails", {}).get("duration")
            out[video["id"]] = parse_iso_duration(dur)
    return out


def get_video_snippet(service, video_id: str):
    resp = (
        service.videos()
        .list(part="snippet", id=video_id)
        .execute(num_retries=_NUM_RETRIES)
    )
    items = resp.get("items", [])
    return items[0]["snippet"] if items else None


def update_title(service, video_id: str, snippet: dict, new_title: str):
    new_snippet = dict(snippet)
    new_snippet["title"] = new_title
    body = {"id": video_id, "snippet": new_snippet}
    return (
        service.videos()
        .update(part="snippet", body=body)
        .execute(num_retries=_NUM_RETRIES)
    )
