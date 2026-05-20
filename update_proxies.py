import datetime
import cache
import checker
import generator
import parser as tg_parser
from config import CHANNELS

def main():
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*55}")
    print(f"  Запуск: {started}")
    print(f"{'='*55}\n")

    cached = cache.load()
    print(f"[main] Загружен кеш: {len(cached)} записей\n")

    print("[main] ── Парсинг каналов ──")
    fresh_raw = tg_parser.parse_all(CHANNELS)
    print(f"[main] Спарсено уникальных: {len(fresh_raw)}\n")

    print("[main] ── TCP-проверка ──")
    fresh_checked = checker.check_all(fresh_raw)
    print()

    print("[main] ── Обновление кеша ──")
    merged = cache.merge(cached, fresh_checked)
    cache.save(merged)
    print()

    fresh   = cache.get_fresh(merged)
    archive = cache.get_archive(merged)

    print("[main] ── Генерация HTML ──")
    generator.write_pages(fresh, archive)
    print()

    with open("last_run.txt", "w", encoding="utf-8") as f:
        alive_count = len([p for p in fresh if p.get("alive")])
        f.write(
            f"Запуск: {started}\n"
            f"Каналов: {len(CHANNELS)}\n"
            f"Свежих прокси: {len(fresh)} (живых TCP: {alive_count})\n"
            f"В архиве: {len(archive)}\n"
            f"Всего в кеше: {len(merged)}\n"
        )

    print(f"[main] ✅ Готово. Свежих: {len(fresh)}, архив: {len(archive)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
