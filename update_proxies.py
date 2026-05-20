import re
import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup

CHANNEL_URL = "https://t.me/s/ProxyMTProto"

# ── Паттерны для валидации сервера ───────────────────────────────────────────
_IP_RE     = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
_DOMAIN_RE = r'[a-zA-Z0-9][a-zA-Z0-9\-]*(?:\.[a-zA-Z0-9][a-zA-Z0-9\-]*)*\.[a-zA-Z]{2,6}'


def is_valid_server(s) -> bool:
    """Белый список: только IPv4 или домен. Unknown, None и т.п. — мимо."""
    if not isinstance(s, str) or not s.strip():
        return False
    v = s.strip()
    return bool(
        re.fullmatch(_IP_RE, v) or
        re.fullmatch(_DOMAIN_RE, v)
    )


def parse_tg_channels():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(CHANNEL_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Ошибка запроса: HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        proxies = []
        seen = set()  # дедупликация за O(1)

        # ══════════════════════════════════════════════════════════════════════
        # СТРАТЕГИЯ 1 (приоритетная): готовые tg:// и https://t.me/proxy? ссылки
        # Они уже содержат все три параметра — самый надёжный источник.
        # ══════════════════════════════════════════════════════════════════════
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "server=" not in href:
                continue

            # Нормализуем tg://proxy? и https://t.me/proxy? к одному виду
            normalized = href.replace("https://t.me/proxy?", "scheme://x?")
            normalized = normalized.replace("tg://proxy?", "scheme://x?")

            try:
                params = urllib.parse.parse_qs(
                    urllib.parse.urlparse(normalized).query
                )
                server = params.get("server", [None])[0]
                port   = params.get("port",   [None])[0]
                secret = params.get("secret", [None])[0]
            except Exception:
                continue

            if not (server and port and secret):
                continue
            if not is_valid_server(server):
                print(f"[SKIP-1] невалидный сервер из ссылки: {server!r}")
                continue

            key = (server.lower(), port, secret)
            if key in seen:
                continue
            seen.add(key)

            tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
            proxies.append({"server": server, "port": port, "secret": secret, "link": tg_link})

        # ══════════════════════════════════════════════════════════════════════
        # СТРАТЕГИЯ 2 (резервная): парсинг текста сообщений
        # Нужна для постов без кнопок. Учитывает, что значение может быть
        # на СЛЕДУЮЩЕЙ строке после метки (реальный формат канала).
        # ══════════════════════════════════════════════════════════════════════
        for msg in soup.find_all("div", class_="tgme_widget_message_text"):
            text = msg.get_text(separator="\n")

            # \n?\s* — значение может быть на следующей строке
            server_m = re.search(
                r'(?:Server|Сервер)\s*:\s*\n?\s*(%s|%s)' % (_IP_RE, _DOMAIN_RE),
                text, re.IGNORECASE
            )
            port_m = re.search(
                r'(?:Port|Порт)\s*:\s*\n?\s*(\d{1,5})',
                text, re.IGNORECASE
            )
            secret_m = re.search(
                r'(?:Secret|Секрет)\s*:\s*\n?\s*([A-Za-z0-9+/=]{10,})',
                text, re.IGNORECASE
            )

            if not (server_m and port_m and secret_m):
                continue

            server = server_m.group(1).strip()
            port   = port_m.group(1).strip()
            secret = secret_m.group(1).strip()

            if not is_valid_server(server):
                print(f"[SKIP-2] невалидный сервер из текста: {server!r}")
                continue

            key = (server.lower(), port, secret)
            if key in seen:
                continue  # уже добавлен стратегией 1
            seen.add(key)

            tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
            proxies.append({"server": server, "port": port, "secret": secret, "link": tg_link})

        # Переворачиваем: последние посты канала → первые карточки на странице
        return proxies[::-1]

    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []


# ── Генерация HTML ────────────────────────────────────────────────────────────

proxies = parse_tg_channels()
current_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

print(f"Найдено прокси: {len(proxies)}")
for p in proxies[:5]:
    print(f"  {p['server']}:{p['port']}")

html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Свежие MTProto Прокси</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            max-width: 520px;
            margin: 24px auto;
            padding: 0 15px 40px;
            background: #e7ebf0;
            color: #111;
        }}
        h2 {{ text-align: center; color: #2481cc; margin-bottom: 4px; }}
        .subtitle {{
            text-align: center;
            color: #666;
            font-size: 13px;
            margin-bottom: 24px;
        }}
        .proxy-card {{
            background: #fff;
            padding: 20px;
            margin-bottom: 14px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,.08);
        }}
        .proxy-info {{
            font-size: 15px;
            line-height: 1.7;
            margin-bottom: 12px;
            word-break: break-all;
        }}
        .badge {{
            display: inline-block;
            background: #ff6b35;
            color: #fff;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 6px;
            margin-left: 6px;
            vertical-align: middle;
        }}
        .btn {{
            display: block;
            background: #2481cc;
            color: #fff;
            padding: 12px;
            text-decoration: none;
            border-radius: 8px;
            text-align: center;
            font-weight: 700;
            font-size: 15px;
        }}
        .btn:hover {{ background: #1a6aaa; }}
        .empty {{
            text-align: center;
            padding: 40px 20px;
            color: #555;
            font-size: 16px;
        }}
    </style>
</head>
<body>
    <h2>&#128640; Свежие MTProto Прокси</h2>
    <div class="subtitle">Обновляется автоматически &middot; {current_time}</div>
"""

if proxies:
    for idx, p in enumerate(proxies[:15], 1):
        badge = '<span class="badge">&#128293; Свежий</span>' if idx == 1 else ""
        html_content += f"""
    <div class="proxy-card">
        <div class="proxy-info">
            <b>Прокси #{idx}</b>{badge}<br>
            &#128205; <b>Сервер:</b> {p['server']}<br>
            &#128299; <b>Порт:</b> {p['port']}<br>
            &#128273; <b>Секрет:</b> <small style="color:#555;">{p['secret']}</small>
        </div>
        <a class="btn" href="{p['link']}">Подключить в Telegram</a>
    </div>
"""
else:
    html_content += """
    <div class="proxy-card empty">
        <p>Пока нет свежих прокси.<br>Обновите страницу через минуту.</p>
    </div>
"""

html_content += "</body>\n</html>\n"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

with open("last_run.txt", "w", encoding="utf-8") as f:
    f.write(f"Последний успешный запуск: {current_time}\n")

print(f"Готово. Сохранено {len(proxies)} прокси в index.html")
