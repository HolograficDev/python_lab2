"""Аналитика: сравнение вариантов доставки и статистика выполненных расчётов."""
from .pricing import Quote
from .tariffs import DeliveryMethod, DeliverySpeed, round_money


def compare_options(item, distance_km, start_date=None):
    """Рассчитывает все сочетания «срочность x способ доставки».

    Возвращает список Quote, отсортированный по возрастанию стоимости.
    """
    quotes = [
        Quote(item, distance_km, speed, method, start_date)
        for speed in DeliverySpeed
        for method in DeliveryMethod
    ]
    return sorted(quotes)



def cheapest_quote(quotes):
    """Самый дешёвый вариант (при равенстве - самый быстрый); None для пустого списка."""
    quotes = list(quotes)
    if not quotes:
        return None
    return min(quotes, key=lambda q: (q.total, q.delivery_days))


def fastest_quote(quotes):
    """Самый быстрый вариант (при равенстве - самый дешёвый); None для пустого списка."""
    quotes = list(quotes)
    if not quotes:
        return None
    return min(quotes, key=lambda q: (q.delivery_days, q.total))


def summarize_history(rows):
    """Сводная статистика по сохранённым расчётам (список словарей из БД).

    Возвращает словарь: количество, сумма, среднее, минимум, максимум
    и разбивку по типам отправлений.
    """
    rows = list(rows)
    summary = {
        "count": len(rows),
        "total_sum": 0.0,
        "average": 0.0,
        "min": 0.0,
        "max": 0.0,
        "by_type": {},
    }
    if not rows:
        return summary

    totals = [row["total_cost"] for row in rows]
    summary["total_sum"] = round_money(sum(totals))
    summary["average"] = round_money(sum(totals) / len(totals))
    summary["min"] = round_money(min(totals))
    summary["max"] = round_money(max(totals))

    for row in rows:
        entry = summary["by_type"].setdefault(
            row["item_type"], {"count": 0, "total_sum": 0.0}
        )
        entry["count"] += 1
        entry["total_sum"] += row["total_cost"]

    for entry in summary["by_type"].values():
        entry["total_sum"] = round_money(entry["total_sum"])

    return summary
