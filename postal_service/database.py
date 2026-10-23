"""Сохранение отправлений и результатов расчётов в SQLite (модуль sqlite3)."""
import sqlite3
from contextlib import closing
from pathlib import Path

from .items import ITEM_CLASSES, Banderol, Letter, Parcel, PostalItem
from .pricing import Quote

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "postal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL CHECK (item_type IN ('letter', 'banderol', 'parcel')),
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    weight_kg REAL NOT NULL CHECK (weight_kg > 0),
    length_cm REAL NOT NULL CHECK (length_cm > 0),
    width_cm REAL NOT NULL CHECK (width_cm > 0),
    height_cm REAL NOT NULL CHECK (height_cm > 0),
    with_notification INTEGER NOT NULL DEFAULT 0,
    is_printed INTEGER NOT NULL DEFAULT 0,
    declared_value REAL NOT NULL DEFAULT 0,
    fragile INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER NOT NULL,
    distance_km REAL NOT NULL,
    speed TEXT NOT NULL,
    delivery_method TEXT NOT NULL,
    billable_weight_kg REAL NOT NULL,
    base_fee REAL NOT NULL,
    weight_cost REAL NOT NULL,
    distance_cost REAL NOT NULL,
    transport_cost REAL NOT NULL,
    extras REAL NOT NULL,
    delivery_fee REAL NOT NULL,
    total_cost REAL NOT NULL,
    delivery_days INTEGER NOT NULL,
    delivery_date TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id)
);
"""


def initialize_database(db_path=None):
    """Создаёт файл БД и таблицы (если их ещё нет). Возвращает путь к файлу."""
    db_path = Path(DB_PATH if db_path is None else db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as connection:
        connection.executescript(SCHEMA)

    return db_path


def _connect(db_path=None):
    """Открывает соединение с включёнными внешними ключами."""
    db_path = initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def save_item(item, db_path=None):
    """Сохраняет новое отправление, присваивает ему item_id и возвращает его."""
    if not isinstance(item, PostalItem):
        raise TypeError("Ожидается объект PostalItem")
    if item.item_id is not None:
        raise ValueError("Отправление уже сохранено в базе")

    options = item.options()

    with closing(_connect(db_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO shipments (
                item_type, sender, recipient, weight_kg,
                length_cm, width_cm, height_cm,
                with_notification, is_printed, declared_value, fragile
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.type_code,
                item.sender,
                item.recipient,
                item.weight_kg,
                item.length_cm,
                item.width_cm,
                item.height_cm,
                int(options.get("with_notification", False)),
                int(options.get("is_printed", False)),
                float(options.get("declared_value", 0.0)),
                int(options.get("fragile", False)),
            ),
        )
        new_id = cursor.lastrowid

    item.item_id = new_id
    return new_id


def _row_to_item(row):
    """Восстанавливает объект отправления по строке таблицы shipments."""
    item_type = row["item_type"]
    if item_type not in ITEM_CLASSES:
        raise ValueError(f"Неизвестный тип отправления в базе: {item_type!r}")

    common = (
        row["sender"], row["recipient"], row["weight_kg"],
        row["length_cm"], row["width_cm"], row["height_cm"],
    )

    if item_type == Letter.TYPE_CODE:
        return Letter(*common, with_notification=bool(row["with_notification"]),
                      item_id=row["id"])
    if item_type == Banderol.TYPE_CODE:
        return Banderol(*common, is_printed=bool(row["is_printed"]),
                        item_id=row["id"])
    return Parcel(*common, declared_value=row["declared_value"],
                  fragile=bool(row["fragile"]), item_id=row["id"])


def load_items(db_path=None):
    """Загружает все отправления. Возвращает словарь {id: объект}."""
    with closing(_connect(db_path)) as connection:
        rows = connection.execute("SELECT * FROM shipments ORDER BY id").fetchall()

    items = {}
    for row in rows:
        item = _row_to_item(row)
        items[item.item_id] = item
    return items


def save_quote(quote, db_path=None):
    """Сохраняет результат расчёта и возвращает id записи."""
    if not isinstance(quote, Quote):
        raise TypeError("Ожидается объект Quote")
    if quote.item.item_id is None:
        raise ValueError("Сначала сохраните отправление в базе")

    with closing(_connect(db_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT INTO quotes (
                shipment_id, distance_km, speed, delivery_method,
                billable_weight_kg, base_fee, weight_cost, distance_cost,
                transport_cost, extras, delivery_fee, total_cost,
                delivery_days, delivery_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.item.item_id,
                quote.distance_km,
                quote.speed.code,
                quote.delivery.code,
                quote.billable_weight_kg,
                quote.base_fee,
                quote.weight_cost,
                quote.distance_cost,
                quote.transport_cost,
                quote.extras,
                quote.delivery_fee,
                quote.total,
                quote.delivery_days,
                quote.delivery_date.isoformat(),
            ),
        )
        return cursor.lastrowid


def load_quotes(db_path=None):
    """Загружает историю расчётов (список словарей) вместе с данными отправления."""
    with closing(_connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT q.*, s.item_type, s.sender, s.recipient
            FROM quotes AS q
            JOIN shipments AS s ON s.id = q.shipment_id
            ORDER BY q.id
            """
        ).fetchall()

    return [dict(row) for row in rows]
