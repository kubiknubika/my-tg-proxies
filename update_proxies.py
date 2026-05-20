"""
update_proxies.py — единый скрипт: парсинг → TCP-проверка → кеш → HTML
Запускается GitHub Actions каждый час.
"""

import re
import json
import os
import socket
import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════

CHANNELS = [
    "https://t.me/s/ProxyMTProto",
    "https://t.me/s/MTProtoProxies",
    "https://t.me/s/mtproto_proxy",
]

HISTORY_DAYS    = 7    # сколько дней хранить прокси в кеше
TCP_TIMEOUT     = 3    # секунды на TCP-проверку одного прокси
CHECKER_WORKERS = 30   # потоков для параллельной проверки
MAX_FRESH       = 15   # карточек на главной странице
MAX_ARCHIVE     = 60   # карточек на странице архива
CACHE_FILE      = "data/proxies.json"

# ═══════════════════════════════════════════════════════════
#  ПАРСЕР
# ═══════════════════════════════════════════════════════════

_IP_RE     = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
_DOMAIN_RE = r'[a-zA-Z0-9][a-zA-Z0-9\-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9\-]*)*\.[a-zA-Z]{2,6}'
_HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def _is_valid_server(s) -> bool:
    if not isinstance(s, str) or not s.strip():
        return False
    v = s.strip()
    return bool(re.fullmatch(_IP_RE, v) or re.fullmatch(_DOMAIN_RE, v))

def _parse_channel(url: str) -> list:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"[parser] {url} → HTTP {r.status_code}")
            return []
    except Exception as e:
        print(f"[parser] {url} → {e}")
        return []

    soup    = BeautifulSoup(r.text, "html.parser")
    proxies = []
    seen    = set()

    # Стратегия 1: готовые tg:// и https://t.me/proxy? ссылки в кнопках
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
        if not _is_valid_server(server):
            continue
        key = (server.lower(), port, secret)
        if key in seen:
            continue
        seen.add(key)
        proxies.append({
            "server": server, "port": port, "secret": secret,
            "link":   f"tg://proxy?server={server}&port={port}&secret={secret}",
            "source": url,
        })

    # Стратегия 2: текст сообщений (значение может быть на следующей строке)
    for msg in soup.find_all("div", class_="tgme_widget_message_text"):
        text = msg.get_text(separator="\n")
        sm = re.search(
            r'(?:Server|Сервер|IP)\s*:\s*\n?\s*(%s|%s)' % (_IP_RE, _DOMAIN_RE),
            text, re.IGNORECASE)
        pm = re.search(r'(?:Port|Порт)\s*:\s*\n?\s*(\d{1,5})',                   text, re.IGNORECASE)
        km = re.search(r'(?:Secret|Секрет)\s*:\s*\n?\s*([A-Za-z0-9+/=_-]{10,})', text, re.IGNORECASE)
        if not (sm and pm and km):
            continue
        server, port, secret = sm.group(1).strip(), pm.group(1).strip(), km.group(1).strip()
        if not _is_valid_server(server):
            continue
        key = (server.lower(), port, secret)
        if key in seen:
            continue
        seen.add(key)
        proxies.append({
            "server": server, "port": port, "secret": secret,
            "link":   f"tg://proxy?server={server}&port={port}&secret={secret}",
            "source": url,
        })

    return proxies

def parse_all(channels: list) -> list:
    all_proxies = []
    global_seen = set()
    for url in channels:
        found = _parse_channel(url)
        added = 0
        for p in found:
            key = (p["server"].lower(), p["port"], p["secret"])
            if key not in global_seen:
                global_seen.add(key)
                all_proxies.append(p)
                added += 1
        print(f"[parser] {url} → {len(found)} найдено, +{added} уникальных")
    return all_proxies

# ═══════════════════════════════════════════════════════════
#  TCP-ПРОВЕРКА
#  ⚠️ Показывает только что порт открыт — не гарантирует
#  работу MTProto. Проверяйте прокси в самом Telegram.
# ═══════════════════════════════════════════════════════════

def _tcp_check(proxy: dict) -> dict:
    server = proxy.get("server", "")
    try:
        port = int(proxy.get("port", 0))
    except (ValueError, TypeError):
        return {**proxy, "alive": False, "latency": None}
    import time
    start = time.monotonic()
    try:
        with socket.create_connection((server, port), timeout=TCP_TIMEOUT):
            latency = round((time.monotonic() - start) * 1000)
        return {**proxy, "alive": True, "latency": latency}
    except OSError:
        return {**proxy, "alive": False, "latency": None}

def check_all(proxies: list) -> list:
    if not proxies:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=min(CHECKER_WORKERS, len(proxies))) as ex:
        futures = {ex.submit(_tcp_check, p): p for p in proxies}
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception:
                results.append({**futures[f], "alive": False, "latency": None})
    alive = sorted([p for p in results if p["alive"]],     key=lambda x: x["latency"])
    dead  =        [p for p in results if not p["alive"]]
    print(f"[checker] Проверено: {len(proxies)} | Живых: {len(alive)} | Мёртвых: {len(dead)}")
    return alive + dead

# ═══════════════════════════════════════════════════════════
#  КЕШ  (data/proxies.json)
# ═══════════════════════════════════════════════════════════

def _today() -> str:
    return datetime.date.today().isoformat()

def cache_load() -> list:
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def cache_save(proxies: list) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(proxies, f, ensure_ascii=False, indent=2)

def cache_merge(cached: list, fresh: list) -> list:
    today   = _today()
    cutoff  = (datetime.date.today() - datetime.timedelta(days=HISTORY_DAYS)).isoformat()
    index   = {_ckey(p): p for p in cached}
    for p in fresh:
        k = _ckey(p)
        if k in index:
            index[k].update({
                "last_seen": today,
                "alive":     p.get("alive",   index[k].get("alive")),
                "latency":   p.get("latency", index[k].get("latency")),
                "source":    p.get("source",  index[k].get("source")),
            })
        else:
            index[k] = {**p, "first_seen": today, "last_seen": today,
                        "alive": p.get("alive"), "latency": p.get("latency")}
    result = [v for v in index.values() if v.get("last_seen", today) >= cutoff]
    print(f"[cache] В кеше: {len(result)} (удалено устаревших: {len(index)-len(result)})")
    return result

def cache_get_fresh(cached: list) -> list:
    today = _today()
    fresh = [p for p in cached if p.get("last_seen") == today]
    # Живые по latency, мёртвые в конце
    alive = sorted([p for p in fresh if p.get("alive")],  key=lambda x: x.get("latency") or 9999)
    other = [p for p in fresh if not p.get("alive")]
    return alive + other

def cache_get_archive(cached: list) -> list:
    today = _today()
    old = [p for p in cached if p.get("last_seen", "") < today]
    return sorted(old, key=lambda x: x.get("last_seen", ""), reverse=True)

def _ckey(p: dict) -> tuple:
    return (p.get("server", "").lower(), p.get("port", ""), p.get("secret", ""))

# ═══════════════════════════════════════════════════════════
#  ГЕНЕРАТОР HTML
# ═══════════════════════════════════════════════════════════

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    max-width: 540px; margin: 24px auto; padding: 0 15px 50px;
    background: #e7ebf0; color: #111;
}
h2 { text-align: center; color: #2481cc; margin-bottom: 4px; }
.subtitle { text-align: center; color: #666; font-size: 13px; margin-bottom: 6px; }
.nav { text-align: center; margin-bottom: 22px; font-size: 14px; }
.nav a { color: #2481cc; text-decoration: none; margin: 0 8px; font-weight: 600; }
.nav a:hover { text-decoration: underline; }
.proxy-card {
    background: #fff; padding: 18px 20px; margin-bottom: 13px;
    border-radius: 12px; box-shadow: 0 3px 10px rgba(0,0,0,.08);
    border-left: 4px solid #ccc;
}
.proxy-card.alive  { border-left-color: #27ae60; }
.proxy-card.dead   { border-left-color: #e74c3c; opacity: .75; }
.proxy-card.unknown{ border-left-color: #95a5a6; }
.proxy-info { font-size: 14px; line-height: 1.75; margin-bottom: 11px; word-break: break-all; }
.badge {
    display: inline-block; font-size: 11px; font-weight: 700;
    padding: 2px 7px; border-radius: 5px; margin-left: 5px; vertical-align: middle;
}
.badge-new   { background: #ff6b35; color: #fff; }
.badge-alive { background: #27ae60; color: #fff; }
.badge-dead  { background: #e74c3c; color: #fff; }
.badge-warn  { background: #f39c12; color: #fff; }
.meta { font-size: 12px; color: #999; margin-bottom: 8px; }
.btn {
    display: block; background: #2481cc; color: #fff; padding: 11px;
    text-decoration: none; border-radius: 8px; text-align: center;
    font-weight: 700; font-size: 15px;
}
.btn:hover { background: #1a6aaa; }
.empty { text-align: center; padding: 40px 20px; color: #666; font-size: 15px; }
.tcp-note {
    background: #fff8e1; border: 1px solid #ffe082; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 18px; font-size: 12px; color: #666;
}
"""

def _card(p: dict, idx: int, show_date: bool = False) -> str:
    alive   = p.get("alive")
    latency = p.get("latency")
    if alive is True:
        cls   = "alive"
        sbadge = f'<span class="badge badge-alive">&#9989; {latency} ms</span>'
    elif alive is False:
        cls   = "dead"
        sbadge = '<span class="badge badge-dead">&#10060; недоступен</span>'
    else:
        cls   = "unknown"
        sbadge = '<span class="badge badge-warn">&#10067; не проверен</span>'

    new_badge = '<span class="badge badge-new">&#128293; Новый</span>' if idx == 1 else ""
    date_line = ""
    if show_date:
        date_line = f'<div class="meta">Обновлён: {p.get("last_seen","")} | Впервые: {p.get("first_seen","")}</div>'

    return f"""
    <div class="proxy-card {cls}">
        {date_line}
        <div class="proxy-info">
            <b>#{idx}</b>{new_badge}{sbadge}<br>
            &#128205; <b>Сервер:</b> {p['server']}<br>
            &#128299; <b>Порт:</b> {p['port']}<br>
            &#128273; <b>Секрет:</b> <small style="color:#666;">{p['secret']}</small>
        </div>
        <a class="btn" href="{p['link']}">Подключить в Telegram</a>
    </div>"""

def _page(title: str, heading: str, subtitle: str, cards_html: str, updated: str) -> str:
    nav = (
        '<div class="nav">'
        '<a href="index.html">&#128640; Свежие</a> &bull; '
        '<a href="archive.html">&#128196; Архив 7 дней</a>'
        '</div>'
    )
    tcp_note = (
        '<div class="tcp-note">'
        '&#9888;&#65039; <b>TCP-проверка</b> показывает только что порт открыт — '
        'не гарантирует работу MTProto. Проверяйте прокси кнопкой в Telegram.'
        '</div>'
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{_CSS}</style>
</head>
<body>
    <h2>{heading}</h2>
    <div class="subtitle">{subtitle}</div>
    {nav}
    {tcp_note}
    {cards_html}
    <div class="subtitle" style="margin-top:24px;">&#128337; Обновлено: {updated}</div>
</body>
</html>
"""

def generate_html(fresh: list, archive: list, updated: str) -> None:
    os.makedirs("docs", exist_ok=True)

    # --- index.html ---
    display = fresh[:MAX_FRESH]
    if display:
        cards = "".join(_card(p, i, False) for i, p in enumerate(display, 1))
    else:
        cards = '<div class="proxy-card unknown empty"><p>Пока нет свежих прокси.<br>Обновите страницу через минуту.</p></div>'
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(_page(
            "Свежие MTProto Прокси",
            "&#128640; Свежие MTProto Прокси",
            "Живые прокси из сегодняшних постов",
            cards, updated
        ))

    # --- archive.html ---
    display_a = archive[:MAX_ARCHIVE]
    if display_a:
        cards_a = "".join(_card(p, i, True) for i, p in enumerate(display_a, 1))
    else:
        cards_a = '<div class="proxy-card unknown empty"><p>Архив пуст. Появится после нескольких запусков.</p></div>'
    with open("docs/archive.html", "w", encoding="utf-8") as f:
        f.write(_page(
            "Архив MTProto Прокси",
            "&#128196; Архив прокси (7 дней)",
            "Прокси из прошлых запусков — могут быть устаревшими",
            cards_a, updated
        ))

    alive_n = len([p for p in fresh if p.get("alive")])
    print(f"[html] index.html: {alive_n} живых из {len(fresh)} свежих")
    print(f"[html] archive.html: {len(archive)} прокси")

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*55}\n  Запуск: {started}\n{'='*55}\n")

    # 1. Кеш
    cached = cache_load()
    print(f"[main] Кеш: {len(cached)} записей\n")

    # 2. Парсинг
    print("[main] ── Парсинг ──")
    fresh_raw = parse_all(CHANNELS)
    print(f"[main] Итого уникальных: {len(fresh_raw)}\n")

    # 3. TCP-проверка
    print("[main] ── TCP-проверка ──")
    fresh_checked = check_all(fresh_raw)
    print()

    # 4. Обновление кеша
    print("[main] ── Кеш ──")
    merged = cache_merge(cached, fresh_checked)
    cache_save(merged)
    print()

    # 5. Срезы
    fresh   = cache_get_fresh(merged)
    archive = cache_get_archive(merged)

    # 6. HTML
    print("[main] ── HTML ──")
    generate_html(fresh, archive, started)
    print()

    # 7. Лог
    with open("last_run.txt", "w", encoding="utf-8") as f:
        alive_n = len([p for p in fresh if p.get("alive")])
        f.write(
            f"Запуск: {started}\n"
            f"Каналов: {len(CHANNELS)}\n"
            f"Свежих прокси: {len(fresh)} (живых TCP: {alive_n})\n"
            f"В архиве: {len(archive)}\n"
            f"Всего в кеше: {len(merged)}\n"
        )

    print(f"[main] ✅ Готово. Свежих: {len(fresh)}, архив: {len(archive)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
