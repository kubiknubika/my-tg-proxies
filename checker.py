# ─────────────────────────────────────────────────────────────
#  checker.py — параллельная TCP-проверка MTProto прокси
# ─────────────────────────────────────────────────────────────
#
#  ⚠️  ВАЖНО: TCP-connect показывает только что порт открыт.
#  Это НЕ гарантирует, что прокси действительно работает как MTProto.
#  Для 100% уверенности нужно подключаться через Telegram-клиент.
#  Рекомендуем всегда проверять прокси кнопкой в самом Telegram.
#
# ─────────────────────────────────────────────────────────────

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import TCP_TIMEOUT, CHECKER_WORKERS


def _tcp_check(proxy: dict) -> dict:
    """
    Пытается установить TCP-соединение с server:port.
    Возвращает proxy-словарь с добавленными полями:
      - alive (bool)   — порт ответил
      - latency (float|None) — задержка в мс, None если недоступен
    """
    server = proxy.get("server", "")
    try:
        port = int(proxy.get("port", 0))
    except (ValueError, TypeError):
        return {**proxy, "alive": False, "latency": None}

    start = time.monotonic()
    try:
        with socket.create_connection((server, port), timeout=TCP_TIMEOUT):
            latency = round((time.monotonic() - start) * 1000)
        return {**proxy, "alive": True, "latency": latency}
    except OSError:
        return {**proxy, "alive": False, "latency": None}


def check_all(proxies: list[dict], workers: int = CHECKER_WORKERS) -> list[dict]:
    """
    Проверяет список прокси параллельно.
    Возвращает тот же список с полями alive и latency.
    Сортирует: живые по возрастанию latency, мёртвые — в конце.
    """
    if not proxies:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=min(workers, len(proxies))) as executor:
        futures = {executor.submit(_tcp_check, p): p for p in proxies}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                original = futures[future]
                results.append({**original, "alive": False, "latency": None})

    # Живые — по latency, мёртвые — в конце
    alive = sorted([p for p in results if p["alive"]], key=lambda x: x["latency"])
    dead  = [p for p in results if not p["alive"]]

    total = len(proxies)
    alive_count = len(alive)
    print(f"[checker] Проверено: {total} | Живых: {alive_count} | Мёртвых: {total - alive_count}")
    return alive + dead


if __name__ == "__main__":
    # Быстрый тест
    test = [
        {"server": "1.1.1.1",     "port": "443",  "secret": "test"},
        {"server": "8.8.8.8",     "port": "443",  "secret": "test"},
        {"server": "0.0.0.1",     "port": "9999", "secret": "dead"},
    ]
    for p in check_all(test):
        status = f"✅ {p['latency']} ms" if p["alive"] else "❌ dead"
        print(f"  {p['server']}:{p['port']} — {status}")
