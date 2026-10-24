import pytest

from postal_service.items import (
    Banderol,
    ITEM_CLASSES,
    Letter,
    Parcel,
    PostalItem,
)



def make_letter(**kwargs):
    params = dict(sender="Иванов", recipient="Петров", weight_kg=0.05,
                  length_cm=22.9, width_cm=16.2, height_cm=0.5)
    params.update(kwargs)
    return Letter(**params)


def make_banderol(**kwargs):
    params = dict(sender="Иванов", recipient="Петров", weight_kg=2,
                  length_cm=40, width_cm=30, height_cm=20)
    params.update(kwargs)
    return Banderol(**params)


def make_parcel(**kwargs):
    params = dict(sender="Иванов", recipient="Петров", weight_kg=10,
                  length_cm=50, width_cm=40, height_cm=30)
    params.update(kwargs)
    return Parcel(**params)


# ---- абстрактный класс и наследование -------------------------------------
def test_abstract_class_cannot_be_instantiated():
    with pytest.raises(TypeError):
        PostalItem("A", "B", 1, 1, 1, 1)


def test_inheritance_hierarchy():
    for item in (make_letter(), make_banderol(), make_parcel()):
        assert isinstance(item, PostalItem)


def test_type_codes_and_names():
    assert make_letter().type_code == "letter"
    assert make_banderol().type_code == "banderol"
    assert make_parcel().type_code == "parcel"
    assert make_letter().type_name == "Письмо"
    assert make_banderol().type_name == "Бандероль"
    assert make_parcel().type_name == "Посылка"


def test_registry_matches_type_codes():
    for code, cls in ITEM_CLASSES.items():
        assert cls.TYPE_CODE == code


# ---- управляемые атрибуты ----------------------------------------------------
def test_text_fields_are_stripped_and_validated():
    letter = make_letter(sender="  Иванов  ")
    assert letter.sender == "Иванов"
    with pytest.raises(ValueError):
        make_letter(recipient="   ")
    with pytest.raises(TypeError):
        make_letter(sender=123)


def test_numeric_fields_validation():
    with pytest.raises(ValueError):
        make_parcel(weight_kg=0)
    with pytest.raises(ValueError):
        make_parcel(length_cm=-5)
    with pytest.raises(TypeError):
        make_parcel(width_cm="30")
    with pytest.raises(TypeError):
        make_parcel(height_cm=True)
    with pytest.raises(ValueError):
        make_parcel(weight_kg=float("inf"))
    with pytest.raises(ValueError):
        make_parcel(weight_kg=float("nan"))


def test_setter_validates_after_creation():
    parcel = make_parcel()
    parcel.weight_kg = 12.5
    assert parcel.weight_kg == 12.5
    with pytest.raises(ValueError):
        parcel.weight_kg = -1
    assert parcel.weight_kg == 12.5


def test_item_id_validation():
    assert make_letter().item_id is None
    assert make_letter(item_id=5).item_id == 5
    with pytest.raises(ValueError):
        make_letter(item_id=0)
    with pytest.raises(TypeError):
        make_letter(item_id="1")


def test_flag_attributes_must_be_bool():
    with pytest.raises(TypeError):
        make_letter(with_notification="да")
    with pytest.raises(TypeError):
        make_banderol(is_printed=1)
    with pytest.raises(TypeError):
        make_parcel(fragile="yes")


def test_declared_value_validation():
    assert make_parcel(declared_value=0).declared_value == 0.0
    with pytest.raises(ValueError):
        make_parcel(declared_value=-1)


# ---- объём и расчётная масса ---------------------------------------------------
def test_letter_ignores_volume():
    letter = make_letter()
    assert letter.volumetric_weight_kg == 0.0
    assert letter.billable_weight_kg == 0.05


def test_banderol_volumetric_weight_is_billable():
    banderol = make_banderol()  # 40*30*20 = 24000 см3 / 6000 = 4 кг > 2 кг
    assert banderol.volume_cm3 == 24000
    assert banderol.volumetric_weight_kg == 4.0
    assert banderol.billable_weight_kg == 4.0


def test_parcel_actual_weight_is_billable_when_heavier():
    parcel = make_parcel(weight_kg=15, length_cm=20, width_cm=20, height_cm=20)
    # объёмная масса 8000/5000 = 1.6 кг < 15 кг
    assert parcel.volumetric_weight_kg == 1.6
    assert parcel.billable_weight_kg == 15.0


# ---- ограничения типов -----------------------------------------------------------
def test_letter_limits():
    with pytest.raises(ValueError):
        make_letter(weight_kg=0.51)
    with pytest.raises(ValueError):
        make_letter(height_cm=2.5)
    with pytest.raises(ValueError):
        make_letter(length_cm=36)
    # допустимый максимум; порядок измерений не важен
    make_letter(weight_kg=0.5, length_cm=2, width_cm=35, height_cm=25)


def test_banderol_limits():
    with pytest.raises(ValueError):
        make_banderol(weight_kg=5.1)
    with pytest.raises(ValueError):
        make_banderol(length_cm=61, width_cm=10, height_cm=10)
    with pytest.raises(ValueError):
        make_banderol(length_cm=40, width_cm=30, height_cm=21)  # сумма 91
    make_banderol(weight_kg=5, length_cm=40, width_cm=30, height_cm=20)  # сумма 90


def test_parcel_limits():
    with pytest.raises(ValueError):
        make_parcel(weight_kg=20.1)
    with pytest.raises(ValueError):
        make_parcel(length_cm=121, width_cm=10, height_cm=10)
    with pytest.raises(ValueError):
        make_parcel(length_cm=100, width_cm=70, height_cm=51)  # сумма 221
    make_parcel(weight_kg=20, length_cm=100, width_cm=70, height_cm=50)  # сумма 220


def test_limits_are_checked_again_by_method():
    parcel = make_parcel()
    parcel.weight_kg = 25  # сеттер допускает, ограничения проверяет check_limits
    with pytest.raises(ValueError):
        parcel.check_limits()


# ---- доплаты ----------------------------------------------------------------------
def test_letter_extras():
    assert make_letter().calculate_extras(100) == 0.0
    assert make_letter(with_notification=True).calculate_extras(100) == 25.0


def test_banderol_extras():
    assert make_banderol().calculate_extras(420) == 0.0
    assert make_banderol(is_printed=True).calculate_extras(420) == pytest.approx(-63.0)


def test_parcel_extras():
    assert make_parcel().calculate_extras(1860) == 0.0
    assert make_parcel(declared_value=5000).calculate_extras(1860) == pytest.approx(150.0)
    assert make_parcel(fragile=True).calculate_extras(1860) == pytest.approx(279.0)
    both = make_parcel(declared_value=5000, fragile=True)
    assert both.calculate_extras(1860) == pytest.approx(429.0)


def test_options_for_database():
    assert make_letter(with_notification=True).options() == {"with_notification": True}
    assert make_banderol(is_printed=True).options() == {"is_printed": True}
    assert make_parcel(declared_value=100, fragile=True).options() == {
        "declared_value": 100.0, "fragile": True,
    }


# ---- dunder-методы ------------------------------------------------------------------
def test_str_of_items():
    assert str(make_letter()) == "Письмо: Иванов - Петров, 0.05 кг"
    assert "с уведомлением" in str(make_letter(with_notification=True))
    assert str(make_banderol(item_id=3)).startswith("Бандероль №3:")
    assert "печатная продукция" in str(make_banderol(is_printed=True))
    text = str(make_parcel(declared_value=5000, fragile=True))
    assert "ценность 5000 руб." in text and "хрупкое" in text


def test_repr_of_items():
    assert repr(make_letter()).startswith("Letter(item_id=None, sender='Иванов'")
    assert "is_printed=True" in repr(make_banderol(is_printed=True))
    assert "declared_value=5000.0" in repr(make_parcel(declared_value=5000))
