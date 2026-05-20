import os
import re
import datetime
import requests
from bs4 import BeautifulSoup

CHANNEL_URL = "https://t.me/s/mtproto_proxies"  # замените на ваш реальный канал

# Паттерн для валидного IP или домена (не заглушка)
_VALID_SERVER_RE = re.compile(
    r'^(?:'
    r'\d{1,3}(?:\.\d{1,3}){3}'           # IPv4: 1.2.3.4
    r'|'
    r'[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
    r'\.[a-zA-Z]{2,6}'                    # домен: example.com, sub.example.org
    r')$'
)

# Слова-заглушки, которые не являются реальными серверами
_PLACEHOLDER_WORDS = {"unknown", "none", "null", "n/a", "—", "-", ""}


def is_valid_server(value: str) -> bool:
    """Возвращает True, если value — реальный IP или домен, а не заглушка."""
    if not isinstance(value, str):
        return False
    v = value.strip().lower()
    if v in _PLACEHOLDER_WORDS:
        return False
    # Дополнительная защита: значение содержит кириллицу → заглушка
    if re.search(r'[а-яёА-ЯЁ]', value):
        return False
    # Проверяем структуру: должен быть IPv4 или нормальный домен
    return bool(_VALID_SERVER_RE.match(value.strip()))


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
        seen = set()   # дедупликация по (server, port, secret)

        for msg in messages:
            text_block = msg.find("div", class_="tgme_widget_message_text")
            if not text_block:
                continue

            text = text_block.get_text(separator="\n")

            # --- Порт ---
            port_match = re.search(r"(?:Port|Порт):\s*(\d+)", text, re.IGNORECASE)
            # --- Секрет ---
            secret_match = re.search(
                r"(?:Secret|Секрет):\s*([A-Za-z0-9+/=]{10,})", text, re.IGNORECASE
            )

            if not (port_match and secret_match):
                continue

            port = port_match.group(1).strip()
            secret = secret_match.group(1).strip()

            # --- Сервер: сначала по ключевому слову ---
            server = None
            server_kw_match = re.search(
                r"(?:Server|Сервер):\s*([^\s\n,;]+)", text, re.IGNORECASE
            )
            if server_kw_match:
                candidate = server_kw_match.group(1).strip()
                # Отрезаем «мусорный хвост» (Border..., @handle, URL)
                candidate = re.sub(r"(?i)Border.*$", "", candidate).strip()
                candidate = re.sub(r"(?:@\w+|https?://\S+)", "", candidate).strip()
                if is_valid_server(candidate):
                    server = candidate

            # --- Сервер: fallback — первый IP или домен в тексте ---
            if server is None:
                ip_or_domain = re.search(
                    r"\b(\d{1,3}(?:\.\d{1,3}){3}|"
                    r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
                    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*"
                    r"\.[a-zA-Z]{2,6})\b",
                    text,
                )
                if ip_or_domain:
                    candidate = ip_or_domain.group(1).strip()
                    if is_valid_server(candidate):
                        server = candidate

            # --- Финальная проверка ---
            if not is_valid_server(server):
                # Заглушка или не нашли — пропускаем карточку
                print(f"[SKIP] Заглушка/невалидный сервер: {server!r}")
                continue

            key = (server.lower(), port, secret)
            if key in seen:
                continue
            seen.add(key)

            tg_link = (
                f"tg://proxy?server={server}&port={port}&secret={secret}"
            )
            proxies.append(
                {"server": server, "port": port, "secret": secret, "link": tg_link}
            )

        # Переворачиваем: свежие посты (в конце HTML) идут первыми
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
            text-align: center; color: #666; font-size: 13px; margin-bottom: 24px;
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
            📍 <b>Сервер:</b> {p['server']}<br>
            🔌 <b>Порт:</b> {p['port']}<br>
            🔑 <b>Секрет:</b> <small style="color:#555;">{p['secret']}</small>
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

print(f"✅ Сохранено прокси: {len(proxies)}")
