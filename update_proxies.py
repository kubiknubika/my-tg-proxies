import re
import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup

# ── Замените на реальный URL вашего канала (формат /s/<name>) ────────────────
CHANNEL_URL = "https://t.me/s/YOUR_CHANNEL_NAME"

# ── Паттерны адресов ─────────────────────────────────────────────────────────
_IP_RE     = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
_DOMAIN_RE = (
    r'[a-zA-Z0-9]'
    r'[a-zA-Z0-9\-]{0,61}'
    r'[a-zA-Z0-9]'
    r'(?:\.[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])*'
    r'\.[a-zA-Z]{2,6}'
)
_ANY_ADDR_RE = re.compile(r'(%s|%s)' % (_IP_RE, _DOMAIN_RE))


def extract_server(text: str):
    """
    Двухуровневый поиск сервера:
    1) После ключевого слова «Server»/«Сервер» — берём первый IP или домен
       в радиусе 30 символов (обходит emoji, пробелы, \xa0, переносы строк).
    2) Fallback: первый IP или домен в любом месте текста.
    """
    # Уровень 1 — по ключевому слову
    kw = re.search(
        r'(?:Server|Сервер)\s*:\s*[^\n]{0,30}?(%s|%s)' % (_IP_RE, _DOMAIN_RE),
        text, re.IGNORECASE
    )
    if kw:
        return kw.group(1).strip()

    # Уровень 2 — fallback по паттерну
    fb = _ANY_ADDR_RE.search(text)
    if fb:
        return fb.group(1).strip()

    return None


def is_valid_server(server) -> bool:
    """
    Белый список: пропускаем только IPv4 или домен.
    Любое слово без точки (Unknown, None, Test…) не пройдёт.
    """
    if not isinstance(server, str) or not server.strip():
        return False
    s = server.strip()
    # IPv4
    if re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', s):
        return True
    # Домен (минимум одна точка и буквенная зона)
    if re.fullmatch(
        r'[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}'
        r'(?:\.[a-zA-Z0-9][a-zA-Z0-9\-]{0,61})*'
        r'\.[a-zA-Z]{2,6}',
        s
    ):
        return True
    return False


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
            print(f"Сервер вернул статус {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message_bubble")

        proxies = []
        seen = set()  # дедупликация за O(1)

        for msg in messages:
            text_block = msg.find("div", class_="tgme_widget_message_text")
            if not text_block:
                continue

            # separator='\n' — любой <br>/<p> превращается в перенос строки
            text = text_block.get_text(separator="\n")

            # ── Порт ────────────────────────────────────────────────────────
            port_m = re.search(r'(?:Port|Порт)\s*:\s*(\d{1,5})', text, re.IGNORECASE)
            # ── Секрет ──────────────────────────────────────────────────────
            secret_m = re.search(
                r'(?:Secret|Секрет)\s*:\s*([A-Za-z0-9+/=]{10,})',
                text, re.IGNORECASE
            )

            if not (port_m and secret_m):
                continue

            port   = port_m.group(1).strip()
            secret = secret_m.group(1).strip()

            # ── Сервер ──────────────────────────────────────────────────────
            server = extract_server(text)

            if not is_valid_server(server):
                # Заглушка (Unknown, None…) или вообще не нашли — пропускаем
                print(f"[SKIP] невалидный сервер: {server!r}")
                continue

            # Дедупликация
            key = (server.lower(), port, secret)
            if key in seen:
                continue
            seen.add(key)

            # Кодируем для URL (на всякий случай)
            tg_link = (
                f"tg://proxy"
                f"?server={urllib.parse.quote(server)}"
                f"&port={port}"
                f"&secret={secret}"
            )

            proxies.append({
                "server": server,
                "port":   port,
                "secret": secret,
                "link":   tg_link,
            })

        # Переворачиваем: последний пост канала → первая карточка на странице
        return proxies[::-1]

    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []


# ── Генерация HTML ────────────────────────────────────────────────────────────

proxies = parse_tg_channels()
current_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

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
    <h2>🚀 Свежие MTProto Прокси</h2>
    <div class="subtitle">Обновляется автоматически · {current_time}</div>
"""

if proxies:
    for idx, p in enumerate(proxies[:15], 1):
        badge = '<span class="badge">🔥 Свежий</span>' if idx == 1 else ""
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

print(f"Сохранено прокси: {len(proxies)}")
