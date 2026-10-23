"""Консольное приложение «Почтовые отправления».

Расчёт стоимости и срока доставки письма, бандероли и посылки
с сохранением результатов в SQLite и экспортом отчётов в Word и Excel.
"""
import math
import sqlite3

from postal_service.analytics import (
    cheapest_quote,
    compare_options,
    fastest_quote,
    summarize_history,
)
from postal_service.database import (
    load_items,
    load_quotes,
    save_item,
    save_quote,
)
from postal_service.items import Banderol, ITEM_CLASSES, Letter, Parcel
from postal_service.pricing import Quote
from postal_service.report import export_excel, export_word
from postal_service.tariffs import DeliveryMethod, DeliverySpeed, MAX_DISTANCE_KM


# ----------------------------------------------------------------------------
# Ввод данных с проверкой
# ----------------------------------------------------------------------------
def read_text(message):
    while True:
        value = input(message).strip()
        if value:
            return value
        print("Ошибка: значение не может быть пустым.")


def read_number(message, allow_zero=False, max_value=None):
    """Читает число (допускается запятая как разделитель).

    max_value - необязательная верхняя граница (включительно).
    """
    while True:
        raw = input(message).strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            print("Ошибка: необходимо ввести число.")
            continue

        if not math.isfinite(value):
            print("Ошибка: необходимо ввести конечное число.")
        elif value < 0 or (value == 0 and not allow_zero):
            if allow_zero:
                print("Ошибка: число не может быть отрицательным.")
            else:
                print("Ошибка: число должно быть больше нуля.")
        elif max_value is not None and value > max_value:
            print(f"Ошибка: значение не может превышать {max_value:g}.")
        else:
            return value


def read_yes_no(message):
    while True:
        answer = input(message + " (д/н): ").strip().lower()
        if answer in ("д", "да", "y", "yes"):
            return True
        if answer in ("н", "нет", "n", "no"):
            return False
        print("Ошибка: введите «д» или «н».")


def read_choice(title, options):
    """Показывает пронумерованный список и возвращает выбранный элемент."""
    print(title)
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")

    while True:
        raw = input("Ваш выбор: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"Ошибка: введите число от 1 до {len(options)}.")


# ----------------------------------------------------------------------------
# Работа с отправлениями
# ----------------------------------------------------------------------------
def max_side_cm(item_class):
    """Наибольшее допустимое значение одного измерения, см."""
    if hasattr(item_class, "MAX_DIMENSIONS_CM"):
        return max(item_class.MAX_DIMENSIONS_CM)
    return item_class.MAX_SIDE_CM


def print_limits(item_class):
    """Выводит ограничения выбранного типа отправления."""
    print(f"Ограничения для типа «{item_class.TYPE_NAME}»:")
    print(f"  масса: не более {item_class.MAX_WEIGHT_KG:g} кг")
    if hasattr(item_class, "MAX_DIMENSIONS_CM"):
        sizes = " x ".join(f"{x:g}" for x in item_class.MAX_DIMENSIONS_CM)
        print(f"  габариты: не более {sizes} см (измерения можно вводить в любом порядке)")
    else:
        print(f"  габариты: наибольшая сторона не более {item_class.MAX_SIDE_CM:g} см, "
              f"сумма трёх измерений не более {item_class.MAX_SUM_CM:g} см")


def read_common_parameters(item_class):
    print_limits(item_class)
    side = max_side_cm(item_class)
    sender = read_text("Отправитель: ")
    recipient = read_text("Получатель: ")
    weight = read_number(
        f"Масса, кг (максимум {item_class.MAX_WEIGHT_KG:g}): ",
        max_value=item_class.MAX_WEIGHT_KG,
    )
    length = read_number(f"Длина, см (максимум {side:g}): ", max_value=side)
    width = read_number(f"Ширина, см (максимум {side:g}): ", max_value=side)
    height = read_number(f"Высота, см (максимум {side:g}): ", max_value=side)
    return sender, recipient, weight, length, width, height


def register_item(items, item):
    save_item(item)
    items[item.item_id] = item
    print(f"Отправление сохранено: {item}")


def add_letter(items):
    print("\n--- Новое письмо ---")
    common = read_common_parameters(Letter)
    notification = read_yes_no("Уведомление о вручении")
    register_item(items, Letter(*common, with_notification=notification))


def add_banderol(items):
    print("\n--- Новая бандероль ---")
    common = read_common_parameters(Banderol)
    printed = read_yes_no("Печатная продукция (книги, журналы)")
    register_item(items, Banderol(*common, is_printed=printed))


def add_parcel(items):
    print("\n--- Новая посылка ---")
    common = read_common_parameters(Parcel)
    declared = read_number("Объявленная ценность, руб. (0 - без страховки, ограничений нет): ",
                           allow_zero=True)
    fragile = read_yes_no("Хрупкое отправление")
    register_item(items, Parcel(*common, declared_value=declared, fragile=fragile))


def show_items(items):
    if not items:
        print("Отправлений пока нет. Создайте письмо, бандероль или посылку.")
        return False

    print("\n--- Отправления ---")
    for item in items.values():
        print(f"{item}")
    return True


def choose_item(items):
    if not show_items(items):
        return None

    while True:
        raw = input("Введите номер отправления: ").strip()
        if raw.isdigit() and int(raw) in items:
            return items[int(raw)]
        print("Ошибка: отправления с таким номером нет.")


def read_distance():
    while True:
        distance = read_number(f"Расстояние доставки, км (до {MAX_DISTANCE_KM:g}): ")
        if distance <= MAX_DISTANCE_KM:
            return distance
        print(f"Ошибка: расстояние не может превышать {MAX_DISTANCE_KM:g} км.")


# ----------------------------------------------------------------------------
# Расчёты
# ----------------------------------------------------------------------------
def calculate_cost(items):
    item = choose_item(items)
    if item is None:
        return

    distance = read_distance()
    speed = read_choice(
        "\nСрок доставки:",
        list(DeliverySpeed),
    )
    method = read_choice("\nТип доставки:", list(DeliveryMethod))

    quote = Quote(item, distance, speed, method)

    print(f"\nОтправление: {item}")
    for label, amount in quote.breakdown():
        print(f"  {label:<45}{amount:>12.2f} руб.")
    print(f"Ожидаемый срок: {quote.delivery_days} дн., "
          f"дата доставки: {quote.delivery_date:%d.%m.%Y}")

    quote_id = save_quote(quote)
    print(f"Результат расчёта сохранён в базе данных (№{quote_id}).")


def compare_all_options(items):
    item = choose_item(items)
    if item is None:
        return

    distance = read_distance()
    quotes = compare_options(item, distance)
    cheapest = cheapest_quote(quotes)
    fastest = fastest_quote(quotes)

    print(f"\n--- Все варианты доставки: {item} ---")
    print(f"{'Срок доставки':<14}{'Тип доставки':<26}{'Цена, руб.':>12}"
          f"{'Дней':>6}  Дата")
    for quote in quotes:
        mark = ""
        if quote is cheapest:
            mark += " <- дешевле всего"
        if quote is fastest:
            mark += " <- быстрее всего"
        print(f"{quote.speed.title:<14}{quote.delivery.title:<26}"
              f"{quote.total:>12.2f}{quote.delivery_days:>6}  "
              f"{quote.delivery_date:%d.%m.%Y}{mark}")


def show_history():
    history = load_quotes()
    if not history:
        print("Расчёты пока не выполнялись.")
        return

    print("\n--- История расчётов ---")
    for row in history:
        print(
            f"№{row['id']}: {ITEM_CLASSES[row['item_type']].TYPE_NAME} №{row['shipment_id']}, "
            f"{row['distance_km']:g} км, "
            f"{DeliverySpeed.from_code(row['speed']).title}, "
            f"{DeliveryMethod.from_code(row['delivery_method']).title}: "
            f"{row['total_cost']:.2f} руб., {row['delivery_days']} дн."
        )

    summary = summarize_history(history)
    print("\n--- Статистика ---")
    print(f"Всего расчётов: {summary['count']}")
    print(f"Общая сумма: {summary['total_sum']:.2f} руб.")
    print(f"Средняя стоимость: {summary['average']:.2f} руб.")
    print(f"Минимум: {summary['min']:.2f} руб., максимум: {summary['max']:.2f} руб.")
    for code, entry in summary["by_type"].items():
        print(f"  {ITEM_CLASSES[code].TYPE_NAME}: расчётов {entry['count']}, "
              f"на сумму {entry['total_sum']:.2f} руб.")


# ----------------------------------------------------------------------------
# Главное меню
# ----------------------------------------------------------------------------
def print_menu():
    print("\n========== ПОЧТОВЫЕ ОТПРАВЛЕНИЯ ==========")
    print("1. Создать письмо")
    print("2. Создать бандероль")
    print("3. Создать посылку")
    print("4. Список отправлений")
    print("5. Рассчитать стоимость и срок доставки")
    print("6. Сравнить все варианты доставки")
    print("7. История расчётов и статистика")
    print("8. Сохранить отчёт в Word (.docx)")
    print("9. Сохранить отчёт в Excel (.xlsx)")
    print("0. Выход")


def main():
    items = load_items()

    while True:
        print_menu()

        try:
            choice = input("\nВыберите пункт меню: ").strip()

            if choice == "1":
                add_letter(items)
            elif choice == "2":
                add_banderol(items)
            elif choice == "3":
                add_parcel(items)
            elif choice == "4":
                show_items(items)
            elif choice == "5":
                calculate_cost(items)
            elif choice == "6":
                compare_all_options(items)
            elif choice == "7":
                show_history()
            elif choice == "8":
                path = export_word(items, load_quotes())
                print(f"Отчёт Word сохранён: {path}")
            elif choice == "9":
                path = export_excel(items, load_quotes())
                print(f"Отчёт Excel сохранён: {path}")
            elif choice == "0":
                print("Завершение работы.")
                break
            else:
                print("Неизвестная команда.")

        except (ValueError, TypeError, OSError, sqlite3.Error) as error:
            print(f"Ошибка: {error}")
        except EOFError:
            print("\nВвод завершён. Завершение работы.")
            break


if __name__ == "__main__":
    main()