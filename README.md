# 5-Minute Free Watcher

This version uses:

- `monitors.csv` in GitHub as the place where you add websites and keywords.
- GitHub Actions as the free scheduled runner.
- ntfy phone push notifications.
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

Install the ntfy app on your phone:

- iPhone: https://apps.apple.com/app/ntfy/id1625396347
- Android: https://play.google.com/store/apps/details?id=io.heckel.ntfy

Subscribe to this topic in the app:

```text
keyword-watcher-ef43f9800c09930d25563d8c
```

The topic is intentionally random. Treat it like a password.

## GitHub Setup

Go to repo Settings -> Secrets and variables -> Actions -> New repository secret.

Add these secrets:

```text
NTFY_TOPIC
```

Use:

```text
NTFY_TOPIC=keyword-watcher-ef43f9800c09930d25563d8c
```

No Meta app, no WhatsApp Business setup, no payment.

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

- Sends a phone notification when a keyword match first appears.
- Sends a phone notification when the set of matched keywords changes.
- Sends a phone notification when a fetch fails.
- Sends a phone notification when a failed site starts working again.
- Does not resend the same unchanged match or same unchanged fetch error every run.

## Limits

GitHub scheduled workflows can run every 5 minutes, but GitHub may delay scheduled jobs during heavy load. For this use case, it is usually good enough, but it is not a hard real-time monitor.

GitHub docs: https://docs.github.com/en/actions/reference/events-that-trigger-workflows#schedule

ntfy docs: https://docs.ntfy.sh/
