"""Справочники тарифов: срочность доставки, способ вручения, округление денег."""
import math
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

# Максимально допустимое расстояние (половина длины экватора Земли), км
MAX_DISTANCE_KM = 20000.0



def round_money(value):
    """Округляет сумму до копеек по правилу «половина вверх» (а не банковскому)."""
    rounded = Decimal(repr(float(value))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    # "+ 0.0" превращает возможный -0.0 в 0.0
    return float(rounded) + 0.0


class DeliverySpeed(Enum):
    """Срок (срочность) доставки.

    Значение элемента: (код, название, коэффициент к тарифу,
    средняя скорость доставки км/сутки, суток на обработку).
    """

    STANDARD = ("standard", "Стандартная", 1.0, 400.0, 2)
    FAST = ("fast", "Ускоренная", 1.5, 700.0, 1)
    EXPRESS = ("express", "Экспресс", 2.0, 1000.0, 0)

    def __init__(self, code, title, multiplier, km_per_day, handling_days):
        self.code = code
        self.title = title
        self.multiplier = multiplier
        self.km_per_day = km_per_day
        self.handling_days = handling_days

    def estimate_days(self, distance_km):
        """Срок доставки в сутках: дорога + обработка, но не менее 1 суток."""
        travel_days = math.ceil(distance_km / self.km_per_day)
        return max(1, travel_days + self.handling_days)

    @classmethod
    def from_code(cls, code):
        for member in cls:
            if member.code == code:
                return member
        raise ValueError(f"Неизвестный вариант срочности: {code!r}")

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"DeliverySpeed.{self.name}"


class DeliveryMethod(Enum):
    """Тип (способ) доставки и вручения.

    Значение элемента: (код, название, фиксированная плата, руб.).
    """

    OFFICE = ("office", "До отделения связи", 0.0)
    REGISTERED = ("registered", "Заказное (под подпись)", 60.0)
    COURIER = ("courier", "Курьером до двери", 250.0)

    def __init__(self, code, title, fee):
        self.code = code
        self.title = title
        self.fee = fee

    @classmethod
    def from_code(cls, code):
        for member in cls:
            if member.code == code:
                return member
        raise ValueError(f"Неизвестный способ доставки: {code!r}")

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"DeliveryMethod.{self.name}"
