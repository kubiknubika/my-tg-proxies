# ─────────────────────────────────────────────────────────────
#  parser.py — парсинг proxy-ссылок из Telegram-каналов
# ─────────────────────────────────────────────────────────────

import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

_IP_RE     = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
_DOMAIN_RE = r'[a-zA-Z0-9][a-zA-Z0-9\-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9\-]*)*\.[a-zA-Z]{2,6}'

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def is_valid_server(s) -> bool:
    """Белый список: только IPv4 или домен. Unknown и т.п. — мимо."""
    if not isinstance(s, str) or not s.strip():
        return False
    v = s.strip()
    return bool(re.fullmatch(_IP_RE, v) or re.fullmatch(_DOMAIN_RE, v))


def _parse_one_channel(url: str) -> list[dict]:
    """
    Парсит одну страницу канала.
    Стратегия 1 (приоритет): готовые tg:// и https://t.me/proxy? ссылки.
    Стратегия 2 (резерв):    текст сообщений с многострочным форматом.
    """
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"[parser] {url} → HTTP {r.status_code}")
            return []
    except Exception as e:
        print(f"[parser] {url} → {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    proxies = []
    seen    = set()

    # ── Стратегия 1: кнопки ────────────────────────────────────
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "server=" not in href:
            continue
        norm = href.replace("https://t.me/proxy?", "s://x?") \
                   .replace("tg://proxy?",          "s://x?")
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(norm).query)
            server = params.get("server", [None])[0]
            port   = params.get("port",   [None])[0]
            secret = params.get("secret", [None])[0]
        except Exception:
            continue

        if not (server and port and secret):
            continue
        if not is_valid_server(server):
            continue

        key = (server.lower(), port, secret)
        if key in seen:
            continue
        seen.add(key)

        proxies.append({
            "server": server,
            "port":   port,
            "secret": secret,
            "link":   f"tg://proxy?server={server}&port={port}&secret={secret}",
            "source": url,
        })

    # ── Стратегия 2: текст (резерв) ────────────────────────────
    for msg in soup.find_all("div", class_="tgme_widget_message_text"):
        text = msg.get_text(separator="\n")

        server_m = re.search(
            r'(?:Server|Сервер|IP)\s*:\s*\n?\s*(%s|%s)' % (_IP_RE, _DOMAIN_RE),
            text, re.IGNORECASE
        )
        port_m   = re.search(r'(?:Port|Порт)\s*:\s*\n?\s*(\d{1,5})',          text, re.IGNORECASE)
        secret_m = re.search(r'(?:Secret|Секрет)\s*:\s*\n?\s*([A-Za-z0-9+/=_-]{10,})', text, re.IGNORECASE)

        if not (server_m and port_m and secret_m):
            continue

        server = server_m.group(1).strip()
        port   = port_m.group(1).strip()
        secret = secret_m.group(1).strip()

        if not is_valid_server(server):
            continue

        key = (server.lower(), port, secret)
        if key in seen:
            continue
        seen.add(key)

        proxies.append({
            "server": server,
            "port":   port,
            "secret": secret,
            "link":   f"tg://proxy?server={server}&port={port}&secret={secret}",
            "source": url,
        })

    return proxies


def parse_all(channels: list[str]) -> list[dict]:
    """Парсит все каналы, возвращает дедуплицированный список."""
    all_proxies = []
    global_seen = set()

    for url in channels:
        found = _parse_one_channel(url)
        for p in found:
            key = (p["server"].lower(), p["port"], p["secret"])
            if key not in global_seen:
                global_seen.add(key)
                all_proxies.append(p)
        print(f"[parser] {url} → +{len(found)} (уник. новых: {len([p for p in found if (p['server'].lower(), p['port'], p['secret']) in global_seen])})")

    return all_proxies
