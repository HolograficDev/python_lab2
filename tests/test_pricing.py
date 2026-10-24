
from datetime import date, datetime

import pytest

from postal_service.items import Banderol, Letter, Parcel
from postal_service.pricing import Quote
from postal_service.tariffs import DeliveryMethod, DeliverySpeed

START = date(2026, 10, 17)


def letter(**kwargs):
    params = dict(sender="А", recipient="Б", weight_kg=0.05,
                  length_cm=22.9, width_cm=16.2, height_cm=0.5)
    params.update(kwargs)
    return Letter(**params)


def banderol(**kwargs):
    params = dict(sender="А", recipient="Б", weight_kg=2,
                  length_cm=40, width_cm=30, height_cm=20)
    params.update(kwargs)
    return Banderol(**params)


def parcel(**kwargs):
    params = dict(sender="А", recipient="Б", weight_kg=10,
                  length_cm=50, width_cm=40, height_cm=30)
    params.update(kwargs)
    return Parcel(**params)


def test_letter_standard_office():
    # 30 + 0.05*120 + 500/100*3 = 30 + 6 + 15 = 51
    q = Quote(letter(), 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    assert q.base_fee == 30.0
    assert q.weight_cost == 6.0
    assert q.distance_cost == 15.0
    assert q.tariff_cost == 51.0
    assert q.transport_cost == 51.0
    assert q.extras == 0.0
    assert q.delivery_fee == 0.0
    assert q.total == 51.0
    assert q.delivery_days == 4
    assert q.delivery_date == date(2026, 10, 21)


def test_letter_fast_with_notification():
    # 51 * 1.5 = 76.5; + 25 уведомление; + 60 заказное
    q = Quote(letter(with_notification=True), 500, DeliverySpeed.FAST,
              DeliveryMethod.REGISTERED, START)
    assert q.transport_cost == 76.5
    assert q.extras == 25.0
    assert q.total == 161.5
    assert q.delivery_days == 2


def test_letter_express_courier():
    # 51*2 = 102; +25; +250 = 377
    q = Quote(letter(with_notification=True), 500, DeliverySpeed.EXPRESS,
              DeliveryMethod.COURIER, START)
    assert q.total == 377.0
    assert q.delivery_days == 1
    assert q.delivery_date == date(2026, 10, 18)


def test_banderol_uses_volumetric_weight():
    # расчётная масса 4 кг: 80 + 4*70 + 10*6 = 420
    q = Quote(banderol(), 1000, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    assert q.billable_weight_kg == 4.0
    assert q.weight_cost == 280.0
    assert q.distance_cost == 60.0
    assert q.tariff_cost == 420.0
    assert q.total == 420.0
    assert q.delivery_days == 5


def test_banderol_printed_discount():
    # скидка 15% от 420 = 63; 420 - 63 = 357
    q = Quote(banderol(is_printed=True), 1000, DeliverySpeed.STANDARD,
              DeliveryMethod.OFFICE, START)
    assert q.extras == -63.0
    assert q.total == 357.0


def test_parcel_express_courier_fragile_insured():
    # тариф 150 + 12*50 + 20*9 = 930; *2 = 1860;
    # доплаты: 5000*3% = 150 и хрупкое 15% от 1860 = 279 -> 429; курьер 250
    q = Quote(parcel(declared_value=5000, fragile=True), 2000,
              DeliverySpeed.EXPRESS, DeliveryMethod.COURIER, START)
    assert q.billable_weight_kg == 12.0
    assert q.tariff_cost == 930.0
    assert q.transport_cost == 1860.0
    assert q.extras == 429.0
    assert q.delivery_fee == 250.0
    assert q.total == 2539.0
    assert q.delivery_days == 2


def test_parcel_standard_registered_insured():
    q = Quote(parcel(declared_value=5000), 2000, DeliverySpeed.STANDARD,
              DeliveryMethod.REGISTERED, START)
    assert q.total == 930.0 + 150.0 + 60.0
    assert q.delivery_days == 7  # ceil(2000/400) + 2


def test_price_grows_with_distance_and_weight():
    near = Quote(parcel(), 100, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    far = Quote(parcel(), 3000, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    assert far.total > near.total
    light = Quote(parcel(weight_kg=1, length_cm=10, width_cm=10, height_cm=10),
                  500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    heavy = Quote(parcel(weight_kg=19, length_cm=10, width_cm=10, height_cm=10),
                  500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    assert heavy.total > light.total


def test_total_equals_sum_of_breakdown_parts():
    q = Quote(parcel(weight_kg=7.333, declared_value=1234.56, fragile=True), 777.7,
              DeliverySpeed.FAST, DeliveryMethod.REGISTERED, START)
    parts = dict(q.breakdown())
    assert q.total == pytest.approx(q.transport_cost + q.extras + q.delivery_fee)
    assert q.breakdown()[-1] == ("ИТОГО", q.total)
    assert len(parts) == 8


def test_distance_validation():
    for bad in (0, -10, 20000.01):
        with pytest.raises(ValueError):
            Quote(letter(), bad, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    with pytest.raises(TypeError):
        Quote(letter(), "500", DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    # граничное значение допустимо
    Quote(letter(), 20000, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)


def test_argument_type_validation():
    with pytest.raises(TypeError):
        Quote("письмо", 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    with pytest.raises(TypeError):
        Quote(letter(), 500, "standard", DeliveryMethod.OFFICE, START)
    with pytest.raises(TypeError):
        Quote(letter(), 500, DeliverySpeed.STANDARD, "office", START)
    with pytest.raises(TypeError):
        Quote(letter(), 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, "2026-10-17")


def test_start_date_defaults_and_datetime():
    q = Quote(letter(), 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE)
    assert q.start_date == date.today()
    q2 = Quote(letter(), 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE,
               datetime(2026, 10, 17, 15, 30))
    assert q2.start_date == date(2026, 10, 17)


def test_limits_rechecked_on_calculation():
    item = parcel()
    item.weight_kg = 30
    with pytest.raises(ValueError):
        Quote(item, 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)


def test_quote_ordering_and_dunder_methods():
    cheap = Quote(letter(), 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE, START)
    pricey = Quote(letter(), 500, DeliverySpeed.EXPRESS, DeliveryMethod.COURIER, START)
    assert cheap < pricey
    assert sorted([pricey, cheap]) == [cheap, pricey]
    with pytest.raises(TypeError):
        cheap < 5
    text = str(cheap)
    assert "Письмо" in text and "51.00 руб." in text and "21.10.2026" in text
    assert repr(cheap).startswith("Quote(item=Letter(")
