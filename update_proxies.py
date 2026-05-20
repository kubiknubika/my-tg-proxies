import os
import urllib.parse
import requests
from bs4 import BeautifulSoup

# Ссылка на веб-версию канала (зеркало)
CHANNEL_URL = "https://t.me/s/ProxyMTProto"

def parse_tg_channels():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(CHANNEL_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Ошибка запроса к TG: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Находим все блоки сообщений в канале
        messages = soup.find_all('div', class_='tgme_widget_message_text')
        proxies = []
        
        for msg in messages:
            text = msg.get_text(separator='\n')
            
            # Ищем параметры сервера внутри текста сообщения регулярными выражениями
            server_match = re.search(r'(?:Server|Сервер):\s*([^\s\n]+)', text, re.IGNORECASE)
            port_match = re.search(r'(?:Port|Порт):\s*(\d+)', text, re.IGNORECASE)
            secret_match = re.search(r'(?:Secret|Секрет):\s*([^\s\n]+)', text, re.IGNORECASE)
            
            if server_match and port_match and secret_match:
                server = server_match.group(1).strip()
                port = port_match.group(1).strip()
                secret = secret_match.group(1).strip()
                
                # Собираем прямую рабочую ссылку для Telegram
                tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
                
                proxy_data = {
                    "server": server,
                    "port": port,
                    "secret": secret,
                    "link": tg_link
                }
                
                if proxy_data not in proxies:
                    proxies.append(proxy_data)
                    
        # Если регулярками не нашлось, ищем по кнопкам "Connect"
        if not proxies:
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if "proxy?" in href or "tgme_widget_message_inline_button" in link.get('class', []):
                    # Если ссылка относительная или содержит параметры, добавляем в список
                    if "server=" in href:
                        parsed_url = urllib.parse.urlparse(href)
                        params = urllib.parse.parse_qs(parsed_url.query)
                        server = params.get('server', [None])[0]
                        port = params.get('port', [None])[0]
                        secret = params.get('secret', [None])[0]
                        if server and port and secret:
                            proxies.append({"server": server, "port": port, "secret": secret, "link": href})

        return proxies[::-1] # Свежие прокси будут вверху страницы
    except Exception as e:
        print(f"Ошибка при парсинге: {e}")
        return []

import re
proxies = parse_tg_channels()

html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мои Свежие Прокси</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 500px; margin: 20px auto; padding: 15px; background: #e7ebf0; color: #111; }}
        h2 {{ text-align: center; color: #2481cc; margin-bottom: 5px; }}
        .subtitle {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 25px; }}
        .proxy-card {{ background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); transition: 0.2s; }}
        .proxy-info {{ font-size: 15px; line-height: 1.6; margin-bottom: 12px; word-break: break-all; }}
        .btn {{ display: block; background: #2481cc; color: white; padding: 12px; text-decoration: none; border-radius: 8px; text-align: center; font-weight: bold; font-size: 15px; }}
        .btn:hover {{ background: #1a6baa; }}
    </style>
</head>
<body>
    <h2>🚀 Свежие MTProto Прокси</h2>
    <div class="subtitle">Обновляется автоматически каждые 30 минут сервером GitHub</div>
"""

if proxies:
    for idx, p in enumerate(proxies[:15], 1):
        html_content += f"""
        <div class="proxy-card">
            <div class="proxy-info">
                <b>Прокси #{idx}</b><br>
                📍 <b>Сервер:</b> {p['server']}<br>
                🔌 <b>Порт:</b> {p['port']}<br>
                🔑 <b>Секрет:</b> <small style="color:#555;">{p['secret']}</small>
            </div>
            <a class="btn" href="{p['link']}">Подключить в Telegram</a>
        </div>
        """
else:
    html_content += f"""
    <div class="proxy-card" style="text-align:center; padding: 40px 20px;">
        <p style="font-size:16px; color:#555; margin:0;">Пока нет свежих прокси.<br>Процесс перезапустился, обновите страницу через минуту.</p>
    </div>
    """

html_content += "</body></html>"

# Сохраняем результат в файл index.html
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"Успешно добавлено {len(proxies)} прокси в index.html")

# ТРЮК ДЛЯ ОБХОДА ЗАМОРОЗКИ CRON: записываем время в отдельный файл
import datetime
current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open("last_run.txt", "w", encoding="utf-8") as f:
    f.write(f"Последний успешный запуск робота: {current_time}")
print("Файл активности last_run.txt обновлен для поддержки триггера cron.")

