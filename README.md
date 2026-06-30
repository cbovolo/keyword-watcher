# 5-Minute Free Watcher

This version uses:

- `monitors.csv` in GitHub as the place where you add websites and keywords.
- GitHub Actions as the free scheduled runner.
- WhatsApp Cloud API for notifications.
- A committed `.watcher-state.json` file so the same unchanged match or fetch failure does not spam you every 5 minutes.

No server. No Vercel. No SSH after setup.

## Add Websites

Edit `monitors.csv` in GitHub. Keep this header row:

```text
enabled,name,url,keywords,case_sensitive
```

Example rows:

```text
yes,eFantasy Pokemon,https://www.efantasy.gr/el/search-results?αναζήτηση=pokemon&sort=auto_min_price,151|booster box|elite trainer box|surging sparks,no
yes,Another shop,https://example.com/search?q=pokemon,pikachu|charizard,no
```

Use `|` between keywords in the `keywords` cell.

To disable a row, set `enabled` to `no`.

## GitHub Setup

Go to repo Settings -> Secrets and variables -> Actions -> New repository secret.

Add these secrets:

```text
WHATSAPP_API_VERSION
WHATSAPP_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_TO
```

Use:

```text
WHATSAPP_API_VERSION=v23.0
WHATSAPP_TO=3069XXXXXXXX
```

`WHATSAPP_TO` is your recipient phone number in international format. Spaces and `+` are stripped automatically.

## Run It

Go to Actions -> Keyword watcher -> Run workflow.

After that, GitHub runs it every 5 minutes.

## Adding Websites Later

Open `monitors.csv` in GitHub, click edit, add a row, and commit:

```text
yes,Shop name,https://shop.example/search?q=pokemon,keyword one|keyword two|keyword three,no
```

No redeploy. No server.

## Alert Behavior

- Sends WhatsApp when a keyword match first appears.
- Sends WhatsApp when the set of matched keywords changes.
- Sends WhatsApp when a fetch fails.
- Sends WhatsApp when a failed site starts working again.
- Does not resend the same unchanged match or same unchanged fetch error every run.

## Limits

GitHub scheduled workflows can run every 5 minutes, but GitHub may delay scheduled jobs during heavy load. For this use case, it is usually good enough, but it is not a hard real-time monitor.

GitHub docs: https://docs.github.com/en/actions/reference/events-that-trigger-workflows#schedule

WhatsApp Cloud API docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
