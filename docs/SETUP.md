# Setup Guide

## 1. Google Cloud OAuth (one time)

YouTube has no service-account path for channel ownership, so you authorize once as yourself
and the service reuses a long-lived **refresh token**. Do all of this while signed in with the
**Google account that owns the YouTube channel**.

> Google recently renamed "OAuth consent screen" to the **Google Auth Platform** (left sidebar:
> Overview / Branding / Audience / Clients / Data Access). The steps below use the new names.

### 1a. Create a project
1. Go to <https://console.cloud.google.com/>.
2. Top bar → project dropdown → **New Project** → name it `yt-retitle` → **Create** → make sure
   it's selected in the dropdown.

### 1b. Enable the API
3. **APIs & Services → Library** → search **YouTube Data API v3** → **Enable**.

### 1c. Configure the consent screen (Google Auth Platform)
4. **APIs & Services → OAuth consent screen** (a.k.a. Google Auth Platform) → **Get started**.
5. **Branding:** App name = `yt-retitle`, user support email = your email.
6. **Audience:** choose **External** → continue.
7. **Contact information:** your email → agree → **Create**.
8. **Data Access** tab → **Add or remove scopes** → in the filter paste
   `https://www.googleapis.com/auth/youtube.force-ssl` → tick it → **Update** → **Save**.
   (This is the one scope the service needs: read your broadcasts and edit titles.)
9. **Audience** tab → **Publishing status**. Pick one:
   - **Publish app → confirm "In production" (recommended).** The refresh token does **not**
     expire. The app stays "unverified" (fine for personal single-user use — you just click
     past a warning in step 2); verification is only required for many external users.
   - *Or* leave it in **Testing** and add your own Google account under **Test users**. Simpler,
     but ⚠️ refresh tokens then **expire after 7 days** and the weekly job breaks. Not recommended.

### 1d. Create the OAuth client
10. **Clients** tab (or **APIs & Services → Credentials**) → **Create credentials → OAuth client
    ID** → Application type: **Desktop app** → name it `yt-retitle-desktop` → **Create**.
11. Copy the **Client ID** and **Client secret** (or **Download JSON**). These become
    `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`.

## 2. Mint the refresh token (run on your laptop, with a browser)

`get_token.py` does the one-time browser sign-in and prints the refresh token. Run it on a
machine **with a browser** (your laptop), not the headless VPS.

```bash
# in a local clone of this repo
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
YOUTUBE_CLIENT_ID=xxx YOUTUBE_CLIENT_SECRET=yyy python get_token.py
```

A browser tab opens:

1. Choose the **Google account that owns the channel**.
2. If you published as unverified, you'll see **"Google hasn't verified this app"** →
   **Advanced** → **Go to yt-retitle (unsafe)**. (Safe — it's your own app.)
3. Grant the **"See, edit, and permanently delete your YouTube videos…"** permission → **Continue**.
4. The tab shows "The authentication flow has completed."; the terminal prints:

```
YOUTUBE_REFRESH_TOKEN=1//0g...
```

Copy that whole value into `.env` as `YOUTUBE_REFRESH_TOKEN` (along with the client id/secret).

> Token didn't print? Re-run — `get_token.py` forces `prompt=consent` + offline access, which is
> required to receive a refresh token. If it still fails, you likely authorized a Google account
> that isn't the channel owner.

## 3. Telegram

- Your bot token comes from @BotFather (you already have a bot).
- Get your chat ID: message the bot, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
- Put both in `.env` as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

## 4. VPS install

Run the service as an **unprivileged user, never root** — it holds your YouTube and Telegram
tokens, so you want the blast radius contained. These steps use the existing user
`banhmisaigon`; substitute your own (and update `User=` in the unit file to match).

```bash
# Code lives in /opt, owned by the service user
sudo install -d -o banhmisaigon -g banhmisaigon /opt/yt-retitle
sudo -u banhmisaigon git clone https://github.com/nguyenab/yt-livestream-retitle-script.git /opt/yt-retitle
cd /opt/yt-retitle
sudo -u banhmisaigon python3 -m venv .venv
sudo -u banhmisaigon .venv/bin/pip install -r requirements.txt

# Secrets: readable only by the service user
sudo -u banhmisaigon cp .env.example .env
sudo -u banhmisaigon nano .env             # fill in all values; keep DRY_RUN=true first
sudo chmod 600 /opt/yt-retitle/.env
```

> Clone over **https** (not the `git@github.com:` SSH URL) — the VPS user needs no GitHub key
> for read-only access. Run the `python -m app.main …` commands below as that user too, e.g.
> `sudo -u banhmisaigon .venv/bin/python -m app.main list`.

### Step 1 (gating): confirm your livestreams are visible

The service finds streams via the YouTube `liveBroadcasts.list` API. Before trusting it,
verify your real (Streamlabs-created) streams actually show up — this makes no changes:

```bash
.venv/bin/python -m app.main list
```

This prints two sources side by side: **`liveBroadcasts (all)`** and **`uploads playlist
(livestreams)`** (each line: date, video id, title). You should see your past worship-service
streams in at least one. The jobs read **both** sources and dedupe, so a stream that appears
in either is covered:

- If both lists show your streams — great, you're fully covered.
- If `liveBroadcasts` is empty but `uploads playlist` shows them — expected with a legacy
  persistent stream key; the jobs still catch them via the uploads source.
- **If both are empty or missing streams** — stop and report it; neither API path sees your
  streams and the jobs would do nothing (`Scanned: 0`).

### Step 2: preview before writing anything

```bash
.venv/bin/python -m app.main backdate       # DRY_RUN=true → logs what it WOULD change
```

When the preview looks right, set `DRY_RUN=false` in `.env` and run the real backdate:

```bash
.venv/bin/python -m app.main backdate
```

### Install the service (weekly automation + Telegram control)

The unit runs as `User=banhmisaigon` with systemd hardening (`ProtectSystem=strict`,
`ProtectHome`, `NoNewPrivileges`, etc.) and grants write access only to `/opt/yt-retitle`
(for `state.json`). Confirm the `User=` line matches your user before installing.

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
