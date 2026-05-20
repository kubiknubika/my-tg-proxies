# ─────────────────────────────────────────────────────────────
#  generator.py — генерация HTML-страниц из кеша прокси
# ─────────────────────────────────────────────────────────────

import os
import datetime
from config import MAX_FRESH, MAX_ARCHIVE

# ── Общий CSS (inline, один раз) ─────────────────────────────
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
.nav a { color: #2481cc; text-decoration: none; margin: 0 8px; }
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
.badge-new    { background: #ff6b35; color: #fff; }
.badge-alive  { background: #27ae60; color: #fff; }
.badge-dead   { background: #e74c3c; color: #fff; }
.badge-warn   { background: #f39c12; color: #fff; }
.meta { font-size: 12px; color: #999; margin-bottom: 8px; }
.btn {
    display: block; background: #2481cc; color: #fff; padding: 11px;
    text-decoration: none; border-radius: 8px; text-align: center;
    font-weight: 700; font-size: 15px;
}
.btn:hover { background: #1a6aaa; }
.empty { text-align: center; padding: 40px 20px; color: #666; font-size: 15px; }
.warning-box {
    background: #fff8e1; border: 1px solid #ffe082; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 20px; font-size: 13px; color: #555; line-height: 1.6;
}
"""

_NAV_FRESH   = '<a href="index.html">&#128640; Свежие</a>'
_NAV_ARCHIVE = '<a href="archive.html">&#128196; Архив 7 дней</a>'


def _html_shell(title: str, body: str, updated: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{_CSS}</style>
</head>
<body>
{body}
    <div class="subtitle" style="margin-top:30px;">&#128337; Обновлено: {updated}</div>
</body>
</html>
"""


def _card(p: dict, idx: int, show_date: bool = False) -> str:
    alive   = p.get("alive")
    latency = p.get("latency")

    if alive is True:
        card_cls  = "alive"
        status_badge = f'<span class="badge badge-alive">&#9989; {latency} ms</span>'
    elif alive is False:
        card_cls  = "dead"
        status_badge = '<span class="badge badge-dead">&#10060; недоступен</span>'
    else:
        card_cls  = "unknown"
        status_badge = '<span class="badge badge-warn">&#10067; не проверен</span>'

    fresh_badge = '<span class="badge badge-new">&#128293; Новый</span>' if idx == 1 else ""

    date_line = ""
    if show_date:
        last = p.get("last_seen", "")
        first = p.get("first_seen", "")
        date_line = f'<div class="meta">Последний раз: {last} &nbsp;|&nbsp; Впервые: {first}</div>'

    warn = ""
    if alive is True:
        warn = (
            '<div class="warning-box">'
            '&#9888;&#65039; TCP-проверка показывает только что порт открыт. '
            'Реальную работу прокси проверяет сам Telegram при подключении.'
            '</div>'
        ) if idx == 1 else ""  # только на первой карточке страницы

    return f"""
    <div class="proxy-card {card_cls}">
        {warn}
        {date_line}
        <div class="proxy-info">
            <b>#{idx}</b>{fresh_badge}{status_badge}<br>
            &#128205; <b>Сервер:</b> {p['server']}<br>
            &#128299; <b>Порт:</b> {p['port']}<br>
            &#128273; <b>Секрет:</b> <small style="color:#666;">{p['secret']}</small>
        </div>
        <a class="btn" href="{p['link']}">Подключить в Telegram</a>
    </div>"""


def _empty_card(msg: str) -> str:
    return f'<div class="proxy-card unknown empty"><p>{msg}</p></div>'


# ── Страница 1: свежие живые прокси ──────────────────────────
def build_index(fresh: list[dict], updated: str) -> str:
    alive_fresh = [p for p in fresh if p.get("alive") is True]
    display = alive_fresh[:MAX_FRESH] if alive_fresh else fresh[:MAX_FRESH]

    cards = ""
    if display:
        for i, p in enumerate(display, 1):
            cards += _card(p, i, show_date=False)
    else:
        cards = _empty_card("Пока нет свежих прокси.<br>Обновите страницу через минуту.")

    body = f"""
    <h2>&#128640; Свежие MTProto Прокси</h2>
    <div class="subtitle">Живые прокси из сегодняшних постов</div>
    <div class="nav">{_NAV_FRESH} &bull; {_NAV_ARCHIVE}</div>
{cards}"""

    return _html_shell("Свежие MTProto Прокси", body, updated)


# ── Страница 2: архив за 7 дней ──────────────────────────────
def build_archive(archive: list[dict], updated: str) -> str:
    display = archive[:MAX_ARCHIVE]

    cards = ""
    if display:
        for i, p in enumerate(display, 1):
            cards += _card(p, i, show_date=True)
    else:
        cards = _empty_card("Архив пуст. Появится после нескольких запусков.")

    body = f"""
    <h2>&#128196; Архив прокси (7 дней)</h2>
    <div class="subtitle">Прокси из прошлых запусков — могут быть устаревшими</div>
    <div class="nav">{_NAV_FRESH} &bull; {_NAV_ARCHIVE}</div>
{cards}"""

    return _html_shell("Архив MTProto Прокси", body, updated)


# ── Запись файлов ─────────────────────────────────────────────
def write_pages(fresh: list[dict], archive: list[dict]) -> None:
    os.makedirs("docs", exist_ok=True)
    updated = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    index_html   = build_index(fresh, updated)
    archive_html = build_archive(archive, updated)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    with open("docs/archive.html", "w", encoding="utf-8") as f:
        f.write(archive_html)

    print(f"[generator] index.html   — {len([p for p in fresh if p.get('alive')])} живых из {len(fresh)} свежих")
    print(f"[generator] archive.html — {len(archive)} прокси в архиве")
