import os
import urllib.parse
import requests
from bs4 import BeautifulSoup

CHANNEL_URL = "https://t.me"

def parse_tg_channels():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(CHANNEL_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        proxies = []
        
        for link in links:
            href = link['href']
            if "proxy?" in href:
                parsed_url = urllib.parse.urlparse(href)
                params = urllib.parse.parse_qs(parsed_url.query)
                server = params.get('server', [None])[0]
                port = params.get('port', [None])[0]
                secret = params.get('secret', [None])[0]
                
                if server and port and secret:
                    proxies.append({"server": server, "port": port, "secret": secret, "link": href})
        return proxies
    except:
        return []

proxies = parse_tg_channels()

# Генерируем красивую HTML-страничку
html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Мои Свежие Прокси</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f4f7f6; }}
        .proxy-card {{ background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        .btn {{ display: inline-block; background: #0088cc; color: white; padding: 8px 15px; text-decoration: none; border-radius: 5px; margin-top: 10px; font-weight: bold; }}
    </style>
</head>
<body>
    <h2>Свежие MTProto Прокси</h2>
    <p>Обновлено автоматически сервером GitHub.</p>
"""

if proxies:
    for idx, p in enumerate(proxies[:15], 1):
        html_content += f"""
        <div class="proxy-card">
            <strong>Прокси #{idx}</strong><br>
            IP: {p['server']} | Порт: {p['port']}<br>
            <a class="btn" href="{p['link']}">Подключить в Telegram</a>
        </div>
        """
else:
    html_content += "<p>Пока нет свежих прокси. Попробуйте обновить позже.</p>"

html_content += "</body></html>"

# Сохраняем результат в файл index.html
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("Файл index.html успешно обновлен!")
