"""Расчёт стоимости и срока доставки почтового отправления.

Формула расчёта:

    расчётная_масса = max(фактическая масса, объёмная масса)
    тариф           = БАЗОВЫЙ_СБОР
                      + расчётная_масса * ПЛАТА_ЗА_КГ
                      + расстояние / 100 * ПЛАТА_ЗА_100_КМ
    перевозка       = тариф * коэффициент_срочности
    доплаты         = item.calculate_extras(перевозка)   (может быть < 0)
    ИТОГО           = перевозка + доплаты + плата_за_способ_вручения

Каждая составляющая округляется до копеек, итог - сумма округлённых частей.
"""
from datetime import date, datetime, timedelta

from .items import PostalItem
from .tariffs import DeliveryMethod, DeliverySpeed, MAX_DISTANCE_KM, round_money



class Quote:
    """Результат расчёта стоимости и срока доставки одного отправления."""

    def __init__(self, item, distance_km, speed, delivery, start_date=None):
        if not isinstance(item, PostalItem):
            raise TypeError("Ожидается объект PostalItem")
        if not isinstance(speed, DeliverySpeed):
            raise TypeError("Срочность должна быть элементом DeliverySpeed")
        if not isinstance(delivery, DeliveryMethod):
            raise TypeError("Способ доставки должен быть элементом DeliveryMethod")

        if start_date is None:
            start_date = date.today()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()
        elif not isinstance(start_date, date):
            raise TypeError("Дата отправки должна быть датой (datetime.date)")

        # параметры могли быть изменены после создания объекта - проверяем снова
        item.check_limits()

        self.item = item
        self.distance_km = distance_km
        self.speed = speed
        self.delivery = delivery
        self.start_date = start_date
        self._calculate()

    @property
    def distance_km(self):
        return self._distance_km

    @distance_km.setter
    def distance_km(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Расстояние: ожидается число")
        value = float(value)
        if not (0 < value <= MAX_DISTANCE_KM):
            raise ValueError(
                f"Расстояние должно быть больше 0 и не более {MAX_DISTANCE_KM:g} км"
            )
        self._distance_km = value

    def _calculate(self):
        item = self.item
        self.billable_weight_kg = item.billable_weight_kg
        self.base_fee = round_money(item.BASE_FEE)
        self.weight_cost = round_money(self.billable_weight_kg * item.WEIGHT_RATE)
        self.distance_cost = round_money(self.distance_km / 100 * item.DISTANCE_RATE)
        self.tariff_cost = round_money(
            self.base_fee + self.weight_cost + self.distance_cost
        )
        self.transport_cost = round_money(self.tariff_cost * self.speed.multiplier)
        self.extras = round_money(item.calculate_extras(self.transport_cost))
        self.delivery_fee = round_money(self.delivery.fee)
        self.total = round_money(
            self.transport_cost + self.extras + self.delivery_fee
        )
        self.delivery_days = self.speed.estimate_days(self.distance_km)
        self.delivery_date = self.start_date + timedelta(days=self.delivery_days)

    def breakdown(self):
        """Состав стоимости: список пар (название статьи, сумма в рублях)."""
        return [
            ("Базовый сбор", self.base_fee),
            (f"Плата за массу ({self.billable_weight_kg:g} кг)", self.weight_cost),
            (f"Плата за расстояние ({self.distance_km:g} км)", self.distance_cost),
            ("Тариф без учёта срочности", self.tariff_cost),
            (f"С учётом срочности (x{self.speed.multiplier:g})", self.transport_cost),
            ("Доплаты и скидки по типу отправления", self.extras),
            (f"Способ доставки: {self.delivery.title}", self.delivery_fee),
            ("ИТОГО", self.total),
        ]

    def __lt__(self, other):
        """Сравнение для сортировки: сначала дешевле, при равенстве - быстрее."""
        if not isinstance(other, Quote):
            return NotImplemented
        return (self.total, self.delivery_days) < (other.total, other.delivery_days)

    def __str__(self):
        return (
            f"{self.item.type_name}, {self.distance_km:g} км, "
            f"{self.speed.title}, {self.delivery.title}: {self.total:.2f} руб., "
            f"срок {self.delivery_days} дн. "
            f"(до {self.delivery_date:%d.%m.%Y})"
        )

    def __repr__(self):
        return (
            f"Quote(item={self.item!r}, distance_km={self.distance_km}, "
            f"speed={self.speed!r}, delivery={self.delivery!r}, "
            f"total={self.total})"
        )
