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

Save that whole value — it becomes the **`YOUTUBE_REFRESH_TOKEN`** GitHub secret in step 4.

> Token didn't print? Re-run — `get_token.py` forces `prompt=consent` + offline access, which is
> required to receive a refresh token. If it still fails, you likely authorized a Google account
> that isn't the channel owner.

## 3. Telegram

- Your **bot token** comes from @BotFather → `/mybots` → your bot → API Token.
- Your **chat ID**: message the bot once, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
- These become the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` GitHub secrets in step 4.

## 4. Deploy on GitHub Actions

The service runs entirely on GitHub Actions — no server. Add your credentials as repo secrets
and the scheduled workflow does the rest.

### Set the secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add all six:

| Secret | Value |
|---|---|
| `YOUTUBE_CLIENT_ID` | from step 1d |
| `YOUTUBE_CLIENT_SECRET` | from step 1d |
| `YOUTUBE_REFRESH_TOKEN` | from step 2 |
| `TELEGRAM_BOT_TOKEN` | from step 3 |
| `TELEGRAM_CHAT_ID` | from step 3 |
| `BASE_TITLES` | the title(s) to match, `||`-separated |

(`TIMEZONE` is hardcoded to `America/Los_Angeles` in the workflow.) From a machine where the
`gh` CLI is logged in you can instead run `gh secret set NAME --repo <owner>/<repo>` per secret.

### Verify, then run

The **Actions** tab → **Retitle livestreams** → **Run workflow** lets you trigger runs manually
with a `command` (weekly / backdate) and a `dry_run` toggle:

1. **`list`-style check first:** run **backdate** with **dry_run ✓**. It makes no changes and
   Telegrams you a preview of exactly what it would retitle. Confirm your streams appear with the
   right dates. (If the report shows `Scanned: 0`, neither API source saw your streams — stop and
   investigate before going further.)
2. **Real backfill:** run **backdate** with **dry_run off** — applies the dates to your whole
   history once.
3. After that, the **weekly schedule** (`cron: "0 2 * * 1"`, Mondays 02:00 UTC ≈ Sunday evening
   Pacific) runs automatically forever.

## 5. How you'll know it ran

- **Telegram** — every run posts a report (scanned / changed, and the new titles).
- **Actions tab** — weekly runs appear labeled trigger `schedule`; green check = success.
- **Failures** (e.g. an expired token) send a Telegram alert instead of failing silently.

> GitHub auto-pauses scheduled workflows after **60 days of no repo activity** and emails you to
> re-enable. The included `keepalive.yml` workflow makes a tiny monthly commit to prevent that,
> so it stays set-and-forget.

### Local testing (optional)

To run the CLI on your own machine, create a `.env` from `.env.example`, fill it in, and run
`python -m app.main list` / `backdate` / `weekly`. Useful for debugging; not required for the
Actions deployment.
