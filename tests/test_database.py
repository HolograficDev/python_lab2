import sqlite3
from contextlib import closing

import pytest

from postal_service.database import (
    initialize_database,
    load_items,
    load_quotes,
    save_item,
    save_quote,
)
from postal_service.items import Banderol, Letter, Parcel
from postal_service.pricing import Quote
from postal_service.tariffs import DeliveryMethod, DeliverySpeed


def make_items():
    letter = Letter("Иванов", "Петров", 0.05, 22.9, 16.2, 0.5, with_notification=True)
    banderol = Banderol("Иванов", "Сидоров", 2, 40, 30, 20, is_printed=True)
    parcel = Parcel("Иванов", "Орлов", 10, 50, 40, 30,
                    declared_value=5000, fragile=True)
    return letter, banderol, parcel


def test_initialize_creates_tables(tmp_path):
    db_path = initialize_database(tmp_path / "sub" / "postal.db")
    assert db_path.exists()

    with closing(sqlite3.connect(db_path)) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"shipments", "quotes"} <= tables


def test_save_item_assigns_ids(tmp_path):
    db_path = tmp_path / "postal.db"
    letter, banderol, parcel = make_items()

    assert save_item(letter, db_path) == 1
    assert save_item(banderol, db_path) == 2
    assert save_item(parcel, db_path) == 3
    assert (letter.item_id, banderol.item_id, parcel.item_id) == (1, 2, 3)


def test_items_are_restored_with_all_fields(tmp_path):
    db_path = tmp_path / "postal.db"
    for item in make_items():
        save_item(item, db_path)

    items = load_items(db_path)
    assert list(items) == [1, 2, 3]

    letter, banderol, parcel = items[1], items[2], items[3]
    assert isinstance(letter, Letter) and letter.with_notification is True
    assert letter.recipient == "Петров" and letter.weight_kg == 0.05
    assert isinstance(banderol, Banderol) and banderol.is_printed is True
    assert banderol.billable_weight_kg == 4.0
    assert isinstance(parcel, Parcel)
    assert parcel.declared_value == 5000.0 and parcel.fragile is True


def test_data_survives_reconnect(tmp_path):
    db_path = tmp_path / "postal.db"
    save_item(make_items()[2], db_path)
    # «перезапуск»: новые вызовы заново открывают файл базы
    assert len(load_items(db_path)) == 1


def test_save_item_twice_is_rejected(tmp_path):
    db_path = tmp_path / "postal.db"
    letter = make_items()[0]
    save_item(letter, db_path)
    with pytest.raises(ValueError):
        save_item(letter, db_path)
    assert len(load_items(db_path)) == 1


def test_save_item_type_check(tmp_path):
    with pytest.raises(TypeError):
        save_item("письмо", tmp_path / "postal.db")


def test_save_and_load_quote(tmp_path):
    db_path = tmp_path / "postal.db"
    parcel = make_items()[2]
    save_item(parcel, db_path)

    quote = Quote(parcel, 2000, DeliverySpeed.EXPRESS, DeliveryMethod.COURIER)
    assert save_quote(quote, db_path) == 1

    rows = load_quotes(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["shipment_id"] == parcel.item_id
    assert row["item_type"] == "parcel"
    assert row["sender"] == "Иванов" and row["recipient"] == "Орлов"
    assert row["distance_km"] == 2000.0
    assert row["speed"] == "express" and row["delivery_method"] == "courier"
    assert row["billable_weight_kg"] == 12.0
    assert row["transport_cost"] == 1860.0
    assert row["extras"] == 429.0
    assert row["delivery_fee"] == 250.0
    assert row["total_cost"] == 2539.0
    assert row["delivery_days"] == 2
    assert row["delivery_date"] == quote.delivery_date.isoformat()


def test_quote_requires_saved_item(tmp_path):
    letter = make_items()[0]  # не сохранён в базе, item_id is None
    quote = Quote(letter, 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE)
    with pytest.raises(ValueError):
        save_quote(quote, tmp_path / "postal.db")


def test_foreign_key_constraint(tmp_path):
    db_path = tmp_path / "postal.db"
    ghost = Letter("А", "Б", 0.05, 22.9, 16.2, 0.5, item_id=999)  # нет в базе
    quote = Quote(ghost, 500, DeliverySpeed.STANDARD, DeliveryMethod.OFFICE)

    with pytest.raises(sqlite3.IntegrityError):
        save_quote(quote, db_path)
    assert load_quotes(db_path) == []


def test_save_quote_type_check(tmp_path):
    with pytest.raises(TypeError):
        save_quote("расчёт", tmp_path / "postal.db")


def test_multiple_quotes_keep_order(tmp_path):
    db_path = tmp_path / "postal.db"
    letter = make_items()[0]
    save_item(letter, db_path)

    for speed in DeliverySpeed:
        save_quote(Quote(letter, 500, speed, DeliveryMethod.OFFICE), db_path)

    rows = load_quotes(db_path)
    assert [row["speed"] for row in rows] == ["standard", "fast", "express"]
    assert [row["id"] for row in rows] == [1, 2, 3]
