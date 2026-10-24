"""Классы почтовых отправлений.

Иерархия наследования:

    PostalItem (абстрактный)
        |-- Letter    - письмо
        |-- Banderol  - бандероль
        |-- Parcel    - посылка

Все параметры отправлений - управляемые атрибуты (@property + setter),
значения проверяются при каждом присваивании.
"""
import math
from abc import ABC, abstractmethod



# ----------------------------------------------------------------------------
# Вспомогательные функции проверки значений
# ----------------------------------------------------------------------------
def _to_float(value, label):
    """Преобразует число к float; bool и нечисловые типы отклоняются."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label}: ожидается число")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label}: число должно быть конечным")
    return number


def _positive(value, label):
    number = _to_float(value, label)
    if number <= 0:
        raise ValueError(f"{label}: значение должно быть больше нуля")
    return number


def _non_negative(value, label):
    number = _to_float(value, label)
    if number < 0:
        raise ValueError(f"{label}: значение не может быть отрицательным")
    return number


def _text(value, label):
    if not isinstance(value, str):
        raise TypeError(f"{label}: ожидается строка")
    value = value.strip()
    if not value:
        raise ValueError(f"{label}: значение не может быть пустым")
    return value


def _flag(value, label):
    if not isinstance(value, bool):
        raise TypeError(f"{label}: ожидается значение True или False")
    return value


# ----------------------------------------------------------------------------
# Абстрактный базовый класс
# ----------------------------------------------------------------------------
class PostalItem(ABC):
    """Абстрактное почтовое отправление.

    Константы тарифа переопределяются в потомках:
        BASE_FEE            - базовый сбор, руб.
        WEIGHT_RATE         - плата за 1 кг расчётной массы, руб.
        DISTANCE_RATE       - плата за каждые 100 км пути, руб.
        VOLUMETRIC_DIVISOR  - делитель объёмной массы (см3 на 1 кг);
                              None - объём не учитывается.
        MAX_WEIGHT_KG       - максимально допустимая масса, кг.
    """

    TYPE_CODE = None
    TYPE_NAME = None
    BASE_FEE = 0.0
    WEIGHT_RATE = 0.0
    DISTANCE_RATE = 0.0
    VOLUMETRIC_DIVISOR = None
    MAX_WEIGHT_KG = 0.0

    def __init__(self, sender, recipient, weight_kg,
                 length_cm, width_cm, height_cm, item_id=None):
        self.item_id = item_id
        self.sender = sender
        self.recipient = recipient
        self.weight_kg = weight_kg
        self.length_cm = length_cm
        self.width_cm = width_cm
        self.height_cm = height_cm

    # ---- управляемые атрибуты ------------------------------------------------
    @property
    def item_id(self):
        return self._item_id

    @item_id.setter
    def item_id(self, value):
        if value is None:
            self._item_id = None
            return
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Идентификатор: ожидается целое число")
        if value <= 0:
            raise ValueError("Идентификатор должен быть положительным числом")
        self._item_id = value

    @property
    def sender(self):
        return self._sender

    @sender.setter
    def sender(self, value):
        self._sender = _text(value, "Отправитель")

    @property
    def recipient(self):
        return self._recipient

    @recipient.setter
    def recipient(self, value):
        self._recipient = _text(value, "Получатель")

    @property
    def weight_kg(self):
        return self._weight_kg

    @weight_kg.setter
    def weight_kg(self, value):
        self._weight_kg = _positive(value, "Масса")

    @property
    def length_cm(self):
        return self._length_cm

    @length_cm.setter
    def length_cm(self, value):
        self._length_cm = _positive(value, "Длина")

    @property
    def width_cm(self):
        return self._width_cm

    @width_cm.setter
    def width_cm(self, value):
        self._width_cm = _positive(value, "Ширина")

    @property
    def height_cm(self):
        return self._height_cm

    @height_cm.setter
    def height_cm(self, value):
        self._height_cm = _positive(value, "Высота")

    # ---- вычисляемые свойства ------------------------------------------------
    @property
    def volume_cm3(self):
        """Объём отправления, см3."""
        return self.length_cm * self.width_cm * self.height_cm

    @property
    def volumetric_weight_kg(self):
        """Объёмная масса, кг (0, если для типа объём не учитывается)."""
        if self.VOLUMETRIC_DIVISOR is None:
            return 0.0
        return round(self.volume_cm3 / self.VOLUMETRIC_DIVISOR, 3)

    @property
    def billable_weight_kg(self):
        """Расчётная масса = большая из фактической и объёмной, кг."""
        return round(max(self.weight_kg, self.volumetric_weight_kg), 3)

    # ---- абстрактный интерфейс -------------------------------------------------
    @property
    @abstractmethod
    def type_code(self):
        """Машинный код типа (используется в БД)."""

    @property
    @abstractmethod
    def type_name(self):
        """Название типа для пользователя."""

    @abstractmethod
    def check_limits(self):
        """Проверяет ограничения по массе и габаритам; при нарушении - ValueError."""

    @abstractmethod
    def calculate_extras(self, transport_cost):
        """Доплаты (+) и скидки (-) данного типа отправления, руб."""

    # ---- общие методы ------------------------------------------------------------
    def options(self):
        """Дополнительные параметры типа (для сохранения в БД)."""
        return {}

    def _dimensions(self):
        return [self.length_cm, self.width_cm, self.height_cm]

    def _check_weight(self):
        if self.weight_kg > self.MAX_WEIGHT_KG:
            raise ValueError(
                f"{self.type_name}: масса {self.weight_kg:g} кг превышает "
                f"допустимую ({self.MAX_WEIGHT_KG:g} кг)"
            )

    def _check_dimensions(self, max_side, max_sum):
        dimensions = self._dimensions()
        if max(dimensions) > max_side:
            raise ValueError(
                f"{self.type_name}: наибольшая сторона {max(dimensions):g} см "
                f"превышает допустимую ({max_side:g} см)"
            )
        if sum(dimensions) > max_sum:
            raise ValueError(
                f"{self.type_name}: сумма трёх измерений {sum(dimensions):g} см "
                f"превышает допустимую ({max_sum:g} см)"
            )

    def __str__(self):
        number = f" №{self.item_id}" if self.item_id is not None else ""
        return (
            f"{self.type_name}{number}: {self.sender} - {self.recipient}, "
            f"{self.weight_kg:g} кг"
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(item_id={self.item_id}, "
            f"sender={self.sender!r}, recipient={self.recipient!r}, "
            f"weight_kg={self.weight_kg}, length_cm={self.length_cm}, "
            f"width_cm={self.width_cm}, height_cm={self.height_cm})"
        )


# ----------------------------------------------------------------------------
# Письмо
# ----------------------------------------------------------------------------
class Letter(PostalItem):
    """Письмо: лёгкое плоское отправление, объём не учитывается."""

    TYPE_CODE = "letter"
    TYPE_NAME = "Письмо"
    BASE_FEE = 30.0
    WEIGHT_RATE = 120.0
    DISTANCE_RATE = 3.0
    VOLUMETRIC_DIVISOR = None
    MAX_WEIGHT_KG = 0.5
    # Предельные габариты (по убыванию), см: 35 x 25 x 2
    MAX_DIMENSIONS_CM = (35.0, 25.0, 2.0)
    NOTIFICATION_FEE = 25.0

    def __init__(self, sender, recipient, weight_kg,
                 length_cm, width_cm, height_cm,
                 with_notification=False, item_id=None):
        super().__init__(sender, recipient, weight_kg,
                         length_cm, width_cm, height_cm, item_id)
        self.with_notification = with_notification
        self.check_limits()

    @property
    def with_notification(self):
        """Нужно ли уведомление о вручении."""
        return self._with_notification

    @with_notification.setter
    def with_notification(self, value):
        self._with_notification = _flag(value, "Уведомление о вручении")

    @property
    def type_code(self):
        return self.TYPE_CODE

    @property
    def type_name(self):
        return self.TYPE_NAME

    def check_limits(self):
        self._check_weight()
        actual = sorted(self._dimensions(), reverse=True)
        for value, limit in zip(actual, self.MAX_DIMENSIONS_CM):
            if value > limit:
                limits = " x ".join(f"{x:g}" for x in self.MAX_DIMENSIONS_CM)
                raise ValueError(
                    f"{self.type_name}: габариты {actual[0]:g} x {actual[1]:g} x "
                    f"{actual[2]:g} см превышают допустимые {limits} см"
                )

    def calculate_extras(self, transport_cost):
        return self.NOTIFICATION_FEE if self.with_notification else 0.0

    def options(self):
        return {"with_notification": self.with_notification}

    def __str__(self):
        text = super().__str__()
        return text + (", с уведомлением" if self.with_notification else "")

    def __repr__(self):
        return (
            f"Letter(item_id={self.item_id}, sender={self.sender!r}, "
            f"recipient={self.recipient!r}, weight_kg={self.weight_kg}, "
            f"length_cm={self.length_cm}, width_cm={self.width_cm}, "
            f"height_cm={self.height_cm}, "
            f"with_notification={self.with_notification})"
        )


# ----------------------------------------------------------------------------
# Бандероль
# ----------------------------------------------------------------------------
class Banderol(PostalItem):
    """Бандероль: книги, документы, печатная продукция."""

    TYPE_CODE = "banderol"
    TYPE_NAME = "Бандероль"
    BASE_FEE = 80.0
    WEIGHT_RATE = 70.0
    DISTANCE_RATE = 6.0
    VOLUMETRIC_DIVISOR = 6000.0
    MAX_WEIGHT_KG = 5.0
    MAX_SIDE_CM = 60.0
    MAX_SUM_CM = 90.0
    PRINTED_DISCOUNT = 0.15

    def __init__(self, sender, recipient, weight_kg,
                 length_cm, width_cm, height_cm,
                 is_printed=False, item_id=None):
        super().__init__(sender, recipient, weight_kg,
                         length_cm, width_cm, height_cm, item_id)
        self.is_printed = is_printed
        self.check_limits()

    @property
    def is_printed(self):
        """Печатная продукция (книги, журналы) - действует скидка."""
        return self._is_printed

    @is_printed.setter
    def is_printed(self, value):
        self._is_printed = _flag(value, "Печатная продукция")

    @property
    def type_code(self):
        return self.TYPE_CODE

    @property
    def type_name(self):
        return self.TYPE_NAME

    def check_limits(self):
        self._check_weight()
        self._check_dimensions(self.MAX_SIDE_CM, self.MAX_SUM_CM)

    def calculate_extras(self, transport_cost):
        if self.is_printed:
            return -self.PRINTED_DISCOUNT * transport_cost
        return 0.0

    def options(self):
        return {"is_printed": self.is_printed}

    def __str__(self):
        text = super().__str__()
        return text + (", печатная продукция" if self.is_printed else "")

    def __repr__(self):
        return (
            f"Banderol(item_id={self.item_id}, sender={self.sender!r}, "
            f"recipient={self.recipient!r}, weight_kg={self.weight_kg}, "
            f"length_cm={self.length_cm}, width_cm={self.width_cm}, "
            f"height_cm={self.height_cm}, is_printed={self.is_printed})"
        )


# ----------------------------------------------------------------------------
# Посылка
# ----------------------------------------------------------------------------
class Parcel(PostalItem):
    """Посылка: тяжёлое отправление с объявленной ценностью."""

    TYPE_CODE = "parcel"
    TYPE_NAME = "Посылка"
    BASE_FEE = 150.0
    WEIGHT_RATE = 50.0
    DISTANCE_RATE = 9.0
    VOLUMETRIC_DIVISOR = 5000.0
    MAX_WEIGHT_KG = 20.0
    MAX_SIDE_CM = 120.0
    MAX_SUM_CM = 220.0
    INSURANCE_RATE = 0.03
    FRAGILE_SURCHARGE = 0.15

    def __init__(self, sender, recipient, weight_kg,
                 length_cm, width_cm, height_cm,
                 declared_value=0.0, fragile=False, item_id=None):
        super().__init__(sender, recipient, weight_kg,
                         length_cm, width_cm, height_cm, item_id)
        self.declared_value = declared_value
        self.fragile = fragile
        self.check_limits()

    @property
    def declared_value(self):
        """Объявленная ценность, руб. (0 - без страховки)."""
        return self._declared_value

    @declared_value.setter
    def declared_value(self, value):
        self._declared_value = _non_negative(value, "Объявленная ценность")

    @property
    def fragile(self):
        """Хрупкое отправление - действует надбавка за осторожное обращение."""
        return self._fragile

    @fragile.setter
    def fragile(self, value):
        self._fragile = _flag(value, "Хрупкое отправление")

    @property
    def type_code(self):
        return self.TYPE_CODE

    @property
    def type_name(self):
        return self.TYPE_NAME

    def check_limits(self):
        self._check_weight()
        self._check_dimensions(self.MAX_SIDE_CM, self.MAX_SUM_CM)

    def calculate_extras(self, transport_cost):
        extras = self.INSURANCE_RATE * self.declared_value
        if self.fragile:
            extras += self.FRAGILE_SURCHARGE * transport_cost
        return extras

    def options(self):
        return {"declared_value": self.declared_value, "fragile": self.fragile}

    def __str__(self):
        text = super().__str__()
        if self.declared_value > 0:
            text += f", ценность {self.declared_value:g} руб."
        if self.fragile:
            text += ", хрупкое"
        return text

    def __repr__(self):
        return (
            f"Parcel(item_id={self.item_id}, sender={self.sender!r}, "
            f"recipient={self.recipient!r}, weight_kg={self.weight_kg}, "
            f"length_cm={self.length_cm}, width_cm={self.width_cm}, "
            f"height_cm={self.height_cm}, declared_value={self.declared_value}, "
            f"fragile={self.fragile})"
        )


# Реестр типов: код -> класс (используется при загрузке из БД)
ITEM_CLASSES = {cls.TYPE_CODE: cls for cls in (Letter, Banderol, Parcel)}
