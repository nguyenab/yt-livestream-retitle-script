# Setup Guide

## 1. Google Cloud OAuth (one time)

1. Go to <https://console.cloud.google.com/> → create a project (e.g. `yt-retitle`).
2. **APIs & Services → Library →** enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen:**
   - User type: **External**.
   - Fill app name + your email.
   - **Publishing status → PUBLISH APP → confirm "In production".**
     > ⚠️ If you leave it in *Testing*, refresh tokens expire after **7 days** and the
     > service stops working every week. Production tokens do not expire.
   - Add scope `.../auth/youtube.force-ssl` (optional to list; the script requests it).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type: **Desktop app**.
   - Download / copy the **Client ID** and **Client secret**.

## 2. Mint the refresh token (run on your laptop, with a browser)

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
YOUTUBE_CLIENT_ID=xxx YOUTUBE_CLIENT_SECRET=yyy python get_token.py
```

A browser opens — log in **with the Google account that owns the YouTube channel** and
approve. The script prints:

```
YOUTUBE_REFRESH_TOKEN=1//0g...
```

Copy that value.

## 3. Telegram

- Your bot token comes from @BotFather (you already have a bot).
- Get your chat ID: message the bot, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
- Put both in `.env` as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

## 4. VPS install

```bash
sudo mkdir -p /opt/yt-retitle && sudo chown $USER /opt/yt-retitle
git clone <your-repo> /opt/yt-retitle && cd /opt/yt-retitle
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env && nano .env          # fill in all values; keep DRY_RUN=true first
```

### Preview before writing anything

```bash
.venv/bin/python -m app.main backdate       # DRY_RUN=true → logs what it WOULD change
```

When the preview looks right, set `DRY_RUN=false` in `.env` and run the real backdate:

```bash
.venv/bin/python -m app.main backdate
```

### Install the service (weekly automation + Telegram control)

```bash
sudo cp deploy/yt-retitle.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yt-retitle
sudo systemctl status yt-retitle
journalctl -u yt-retitle -f
```

## 5. Health check

In Telegram, send the bot:

- `/status` — last run, next run, last error
- `/run` — run the weekly job now
- `/backdate` — retitle all past livestreams
- `/help`

On startup the service messages you `✅ yt-retitle started. Next weekly run: …`.
