import pytest

from postal_service.tariffs import DeliveryMethod, DeliverySpeed, round_money


def test_round_money_half_up():
    # банковское округление дало бы 0.12; нужно «половина вверх»
    assert round_money(0.125) == 0.13
    assert round_money(10) == 10.0
    assert round_money(73.35000000000001) == 73.35


def test_round_money_negative_zero():
    assert str(round_money(-0.0)) == "0.0"


def test_speed_multipliers_and_codes():
    assert DeliverySpeed.STANDARD.multiplier == 1.0
    assert DeliverySpeed.FAST.multiplier == 1.5
    assert DeliverySpeed.EXPRESS.multiplier == 2.0
    assert DeliverySpeed.from_code("fast") is DeliverySpeed.FAST


def test_estimate_days():
    # 500 км: ceil(500/400)=2 + 2 суток обработки
    assert DeliverySpeed.STANDARD.estimate_days(500) == 4
    # ceil(500/700)=1 + 1
    assert DeliverySpeed.FAST.estimate_days(500) == 2
    # ceil(500/1000)=1 + 0
    assert DeliverySpeed.EXPRESS.estimate_days(500) == 1


def test_estimate_days_minimum_is_one_day():
    assert DeliverySpeed.EXPRESS.estimate_days(0.1) == 1


def test_delivery_method_fees_and_codes():
    assert DeliveryMethod.OFFICE.fee == 0.0
    assert DeliveryMethod.REGISTERED.fee == 60.0
    assert DeliveryMethod.COURIER.fee == 250.0
    assert DeliveryMethod.from_code("courier") is DeliveryMethod.COURIER


def test_unknown_codes_rejected():
    with pytest.raises(ValueError):
        DeliverySpeed.from_code("teleport")
    with pytest.raises(ValueError):
        DeliveryMethod.from_code("drone")


def test_dunder_methods_of_enums():
    assert str(DeliverySpeed.EXPRESS) == "Экспресс"
    assert repr(DeliverySpeed.EXPRESS) == "DeliverySpeed.EXPRESS"
    assert str(DeliveryMethod.OFFICE) == "До отделения связи"
    assert repr(DeliveryMethod.OFFICE) == "DeliveryMethod.OFFICE"
