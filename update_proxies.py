import os
import re
import urllib.parse
import datetime
import requests
from bs4 import BeautifulSoup

CHANNEL_URL = "https://t.me"

def parse_tg_channels():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(CHANNEL_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message_bubble')
        proxies = []
        
        for msg in messages:
            text_block = msg.find('div', class_='tgme_widget_message_text')
            if not text_block:
                continue
                
            text = text_block.get_text(separator='\n')
            
            # Находим порт и секрет (они всегда одинаковые)
            port_match = re.search(r'(?:Port|Порт):\s*(\d+)', text, re.IGNORECASE)
            secret_match = re.search(r'(?:Secret|Секрет):\s*([^\s\n]+)', text, re.IGNORECASE)
            
            if port_match and secret_match:
                port = port_match.group(1).strip()
                secret = secret_match.group(1).strip()
                
                # Умный поиск сервера: ищем ключевое слово, либо паттерн IP/домена
                server_match = re.search(r'(?:Server|Сервер):\s*([^\s\n]+)', text, re.IGNORECASE)
                if server_match:
                    server = server_match.group(1).strip()
                else:
                    ip_or_domain = re.search(r'([a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
                    server = ip_or_domain.group(1).strip() if ip_or_domain else None
                
                # Проверяем, что сервер — это строка, она существует и это не "Unknown"
                if server and hasattr(server, 'lower') and server.lower() != "unknown":
                    # Очищаем от мусора в конце строки
                    server = re.sub(r'Border.*', '', server, flags=re.IGNORECASE)
                    server = re.sub(r'(@\w+|https?://\S+)', '', server).strip()
                    
                    tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
                    
                    proxy_data = {
                        "server": server,
                        "port": port,
                        "secret": secret,
                        "link": tg_link
                    }
                    
                    if proxy_data not in proxies:
                        proxies.append(proxy_data)
                        
        return proxies[::-1]
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return []

proxies = parse_tg_channels()

html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мои Свежие Прокси</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; max-width: 500px; margin: 20px auto; padding: 15px; background: #e7ebf0; color: #111; }}
        h2 {{ text-align: center; color: #2481cc; margin-bottom: 5px; }}
        .subtitle {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 25px; }}
        .proxy-card {{ background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        .proxy-info {{ font-size: 15px; line-height: 1.6; margin-bottom: 12px; word-break: break-all; }}
        .btn {{ display: block; background: #2481cc; color: white; padding: 12px; text-decoration: none; border-radius: 8px; text-align: center; font-weight: bold; font-size: 15px; }}
    </style>
</head>
<body>
    <h2>🚀 Свежие MTProto Прокси</h2>
    <div class="subtitle">Обновляется автоматически сервером GitHub</div>
"""

if proxies:
    for idx, p in enumerate(proxies[:15], 1):
        html_content += f"""
        <div class="proxy-card">
            <div class="proxy-info">
                <b>Прокси #{idx}</b> {'🔥 (Самый свежий)' if idx == 1 else ''}<br>
                📍 <b>Сервер:</b> {p['server']}<br>
                🔌 <b>Порт:</b> {p['port']}<br>
                🔑 <b>Секрет:</b> <small style="color:#555;">{p['secret']}</small>
            </div>
            <a class="btn" href="{p['link']}">Подключить в Telegram</a>
        </div>
        """
else:
    html_content += """
    <div class="proxy-card" style="text-align:center; padding: 40px 20px;">
        <p style="font-size:16px; color:#555; margin:0;">Пока нет свежих прокси.<br>Обновите страницу через минуту.</p>
    </div>
    """

html_content += "</body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

import datetime
current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open("last_run.txt", "w", encoding="utf-8") as f:
    f.write(f"Последний успешный запуск робота: {current_time}")
print(f"Успешно сохранено {len(proxies)} прокси.")
