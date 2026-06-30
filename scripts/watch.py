import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen


STATE_FILE = Path(os.getenv("STATE_FILE", ".watcher-state.json"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
USER_AGENT = os.getenv(
    "WATCHER_USER_AGENT",
    "Mozilla/5.0 (compatible; GitHubActionsKeywordWatcher/1.0)",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def truthy(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def ascii_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"Invalid URL: {url}")
    netloc = parts.netloc.encode("idna").decode("ascii")
    path = quote(parts.path, safe="/%")
    query = quote(parts.query, safe="=&%")
    fragment = quote(parts.fragment, safe="")
    return urlunsplit((parts.scheme, netloc, path, query, fragment))


def read_text_url(url: str) -> str:
    req = Request(
        ascii_url(url),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        body = response.read()
        content_type = response.headers.get("content-type", "")
    charset = "utf-8"
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            charset = part.split("=", 1)[1].strip()
            break
    return body.decode(charset, errors="replace")


def load_state() -> Dict:
    if not STATE_FILE.exists():
        return {"monitors": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"monitors": {}}


def save_state(state: Dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def split_keywords(value: str) -> List[str]:
    keywords = []
    for item in str(value or "").replace("\n", "|").split("|"):
        keyword = item.strip()
        if keyword:
            keywords.append(keyword)
    return keywords


def monitor_key(monitor: Dict) -> str:
    raw = "|".join(
        [
            monitor["name"],
            monitor["url"],
            "\n".join(monitor["keywords"]),
            str(monitor["case_sensitive"]),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def find_matches(content: str, keywords: Iterable[str], case_sensitive: bool) -> List[str]:
    haystack = content if case_sensitive else content.casefold()
    matches = []
    for keyword in keywords:
        needle = keyword if case_sensitive else keyword.casefold()
        if needle in haystack:
            matches.append(keyword)
    return matches


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def send_whatsapp(message: str) -> Tuple[bool, str]:
    api_version = os.getenv("WHATSAPP_API_VERSION", "v23.0").strip().lstrip("/")
    phone_number_id = require_env("WHATSAPP_PHONE_NUMBER_ID")
    token = require_env("WHATSAPP_ACCESS_TOKEN")
    recipient = require_env("WHATSAPP_TO").replace("+", "").replace(" ", "").replace("-", "")

    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return True, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {body}"
    except URLError as exc:
        return False, str(exc)


def message_for(monitor: Dict, status: str, matches: List[str] = None, error: str = "") -> str:
    lines = [f"Keyword watcher: {monitor['name']}"]
    if status == "match":
        lines.append("Status: keyword found")
        lines.append(f"Matches: {', '.join(matches or [])}")
    elif status == "fetch_failed":
        lines.append("Status: fetch failed")
        lines.append(f"Error: {error}")
    elif status == "recovered":
        lines.append("Status: recovered")
        lines.append("The page is reachable again.")
    lines.append(f"URL: {monitor['url']}")
    lines.append(f"Time: {utc_now()}")
    return "\n".join(lines)


def download_monitors_csv() -> str:
    local_path = os.getenv("MONITORS_CSV_PATH", "").strip()
    if local_path:
        return Path(local_path).read_text(encoding="utf-8")
    csv_url = require_env("MONITORS_CSV_URL")
    return read_text_url(csv_url)


def parse_monitors(csv_text: str) -> List[Dict]:
    rows = csv.DictReader(csv_text.splitlines())
    monitors = []
    for index, row in enumerate(rows, start=2):
        normalized = {str(k or "").strip().casefold(): str(v or "").strip() for k, v in row.items()}
        enabled = normalized.get("enabled", "yes")
        if enabled and not truthy(enabled):
            continue
        name = normalized.get("name") or f"Monitor row {index}"
        url = normalized.get("url", "")
        keywords = split_keywords(normalized.get("keywords", ""))
        if not url or not keywords:
            print(f"Skipping row {index}: url and keywords are required", file=sys.stderr)
            continue
        monitors.append(
            {
                "name": name,
                "url": url,
                "keywords": keywords,
                "case_sensitive": truthy(normalized.get("case_sensitive", "")),
            }
        )
    return monitors


def check_monitor(monitor: Dict, state: Dict) -> bool:
    key = monitor_key(monitor)
    monitor_state = state.setdefault("monitors", {}).setdefault(key, {})
    previous_alert_state = monitor_state.get("alert_state")
    changed = False

    try:
        content = read_text_url(monitor["url"])
    except Exception as exc:
        error = str(exc)
        alert_state = f"error:{error[:500]}"
        should_notify = previous_alert_state != alert_state
        monitor_state.update(
            {
                "name": monitor["name"],
                "url": monitor["url"],
                "alert_state": alert_state,
                "last_status": "error",
                "last_error": error,
                "last_checked_at": utc_now(),
            }
        )
        changed = True
        if should_notify:
            ok, response = send_whatsapp(message_for(monitor, "fetch_failed", error=error))
            print(f"{monitor['name']}: fetch failed, whatsapp_sent={ok}, response={response[:300]}")
        else:
            print(f"{monitor['name']}: still failing, no duplicate WhatsApp")
        return changed

    matches = find_matches(content, monitor["keywords"], monitor["case_sensitive"])
    if matches:
        alert_state = "match:" + json.dumps(matches, ensure_ascii=False)
        should_notify = previous_alert_state != alert_state
        monitor_state.update(
            {
                "name": monitor["name"],
                "url": monitor["url"],
                "alert_state": alert_state,
                "last_status": "matched",
                "last_matches": matches,
                "last_error": "",
                "last_checked_at": utc_now(),
            }
        )
        changed = True
        if should_notify:
            ok, response = send_whatsapp(message_for(monitor, "match", matches=matches))
            print(f"{monitor['name']}: matched {matches}, whatsapp_sent={ok}, response={response[:300]}")
        else:
            print(f"{monitor['name']}: same match, no duplicate WhatsApp")
        return changed

    recovered = str(previous_alert_state or "").startswith("error:")
    monitor_state.update(
        {
            "name": monitor["name"],
            "url": monitor["url"],
            "alert_state": "no_match",
            "last_status": "no_match",
            "last_matches": [],
            "last_error": "",
            "last_checked_at": utc_now(),
        }
    )
    changed = True
    if recovered:
        ok, response = send_whatsapp(message_for(monitor, "recovered"))
        print(f"{monitor['name']}: recovered, whatsapp_sent={ok}, response={response[:300]}")
    else:
        print(f"{monitor['name']}: no match")
    return changed


def main() -> int:
    # Fail fast so a misconfigured Action is obvious.
    require_env("WHATSAPP_ACCESS_TOKEN")
    require_env("WHATSAPP_PHONE_NUMBER_ID")
    require_env("WHATSAPP_TO")

    monitors = parse_monitors(download_monitors_csv())
    if not monitors:
        print("No enabled monitors found.")
        return 0

    state = load_state()
    changed = False
    for monitor in monitors:
        changed = check_monitor(monitor, state) or changed
    if changed:
        save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
