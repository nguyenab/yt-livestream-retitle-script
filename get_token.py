"""One-time helper: mint a YouTube OAuth refresh token.

Run on a machine with a browser:
    YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... python get_token.py

Copy the printed YOUTUBE_REFRESH_TOKEN line into your .env.
"""
from __future__ import annotations

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def main() -> None:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in the environment first.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        sys.exit("No refresh token returned. Re-run; ensure prompt=consent and offline access.")
    print("\n# Add this line to your .env:")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
