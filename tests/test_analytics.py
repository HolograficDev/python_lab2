from datetime import date

from postal_service.analytics import (
    cheapest_quote,
    compare_options,
    fastest_quote,
    summarize_history,
)
from postal_service.items import Parcel
from postal_service.pricing import Quote
from postal_service.tariffs import DeliveryMethod, DeliverySpeed

START = date(2026, 10, 17)



def make_parcel():
    return Parcel("А", "Б", 10, 50, 40, 30, declared_value=5000, fragile=True)


def test_compare_options_returns_all_combinations_sorted():
    quotes = compare_options(make_parcel(), 2000, START)
    assert len(quotes) == len(DeliverySpeed) * len(DeliveryMethod) == 9
    totals = [q.total for q in quotes]
    assert totals == sorted(totals)


def test_cheapest_option():
    quotes = compare_options(make_parcel(), 2000, START)
    best = cheapest_quote(quotes)
    # тариф 930; стандартная, до отделения: 930 + 150 + 15% * 930 = 1219.5
    assert best.speed is DeliverySpeed.STANDARD
    assert best.delivery is DeliveryMethod.OFFICE
    assert best.total == 1219.5


def test_fastest_option_prefers_cheaper_on_tie():
    quotes = compare_options(make_parcel(), 2000, START)
    best = fastest_quote(quotes)
    assert best.speed is DeliverySpeed.EXPRESS
    assert best.delivery is DeliveryMethod.OFFICE
    assert best.delivery_days == 2
    # 930*2 = 1860; 150 + 279 = 429; итого 2289
    assert best.total == 2289.0


def test_empty_quotes():
    assert cheapest_quote([]) is None
    assert fastest_quote([]) is None


def test_quote_objects_are_not_mutated_between_options():
    quotes = compare_options(make_parcel(), 2000, START)
    assert all(isinstance(q, Quote) for q in quotes)
    assert len({id(q) for q in quotes}) == 9


def test_summarize_history():
    rows = [
        {"item_type": "letter", "total_cost": 51.0},
        {"item_type": "letter", "total_cost": 100.0},
        {"item_type": "parcel", "total_cost": 2539.0},
    ]
    summary = summarize_history(rows)
    assert summary["count"] == 3
    assert summary["total_sum"] == 2690.0
    assert summary["average"] == 896.67
    assert summary["min"] == 51.0
    assert summary["max"] == 2539.0
    assert summary["by_type"]["letter"] == {"count": 2, "total_sum": 151.0}
    assert summary["by_type"]["parcel"] == {"count": 1, "total_sum": 2539.0}


def test_summarize_empty_history():
    summary = summarize_history([])
    assert summary["count"] == 0
    assert summary["total_sum"] == 0.0
    assert summary["by_type"] == {}
