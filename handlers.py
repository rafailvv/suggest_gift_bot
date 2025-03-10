import os
import csv
import random
import datetime
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, FSInputFile, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.formatting import Text

from data import product_search_instance

router = Router()

# Пути к файлам логирования сессий, популярности товаров и dataset
SESSIONS_LOG_FILE = "sessions.csv"
POPULAR_PRODUCTS_FILE = "popular_products.csv"
DATASET_FILE = "dataset.csv"

# Инициализация CSV-файлов (если не существуют)
if not os.path.exists(SESSIONS_LOG_FILE):
    with open(SESSIONS_LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "user_id", "username", "event", "text"])

if not os.path.exists(POPULAR_PRODUCTS_FILE):
    with open(POPULAR_PRODUCTS_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Сохраняем: name, category, description, price, link, count
        writer.writerow(["name", "category", "description", "price", "link", "count"])

def log_session(user: types.User, event: str, text: str):
    """Записывает событие сессии в CSV-файл."""
    timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    with open(SESSIONS_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user.id, user.username or "", event, text])

def update_popular_product(product: dict):
    """Обновляет или добавляет запись о товаре в файле популярности."""
    # Считываем текущие данные
    rows = []
    found = False
    if os.path.exists(POPULAR_PRODUCTS_FILE):
        with open(POPULAR_PRODUCTS_FILE, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Сравнение по уникальному идентификатору товара можно сделать по name и link
                if row["name"] == product["name"] and row["link"] == product["link"]:
                    row["count"] = str(int(row["count"]) + 1)
                    found = True
                rows.append(row)
    # Если не найден, добавляем новую запись
    if not found:
        rows.append({
            "name": product["name"],
            "category": product["category"],
            "description": product["description"],
            "price": product["price"],
            "link": product["link"],
            "count": "1"
        })
    # Записываем обновлённые данные
    with open(POPULAR_PRODUCTS_FILE, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = ["name", "category", "description", "price", "link", "count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def get_top_popular_products(top_n=3):
    """Возвращает список топовых популярных товаров."""
    products = []
    if os.path.exists(POPULAR_PRODUCTS_FILE):
        with open(POPULAR_PRODUCTS_FILE, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Преобразуем счётчик в число
                row["count"] = int(row["count"])
                products.append(row)
    # Сортируем по убыванию count
    products = sorted(products, key=lambda x: x["count"], reverse=True)
    return products[:top_n]

class QueryState(StatesGroup):
    waiting_for_clarification = State()

class DatasetState(StatesGroup):
    waiting_for_dataset = State()

@router.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    log_session(message.from_user, "start", message.text)
    popular_button = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Популярные товары")]
    ], resize_keyboard=True)
    await message.answer("Привет! Напиши, что ты ищешь", reply_markup=popular_button)

@router.message(Command("sessions"))
async def sessions_handler(message: types.Message):
    if not os.path.exists(SESSIONS_LOG_FILE):
        await message.answer("Данных о сессиях пока нет.")
        return

    with open(SESSIONS_LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        await message.answer("Данных о сессиях пока нет.")
        return

    table_lines = []
    for row in rows:
        table_lines.append("\t".join(row))
    table_text = "\n".join(table_lines)

    temp_filename = "sessions_export.txt"
    with open(temp_filename, "w", encoding="utf-8") as f:
        f.write(table_text)
    await message.answer_document(FSInputFile(temp_filename))
    os.remove(temp_filename)

# Команда для отображения агрегированной статистики
@router.message(Command("stats"))
async def stats_handler(message: types.Message):
    """
    Команда для менеджера: выводит агрегированную статистику по запросам и рекомендациям.
    Рекомендациями, не приведшими к покупке, считаются случаи, когда по запросу не было отправлено результатов.
    """
    if not os.path.exists(SESSIONS_LOG_FILE):
        await message.answer("Нет данных для статистики.")
        return

    event_counts = {}
    with open(SESSIONS_LOG_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            event = row["event"]
            event_counts[event] = event_counts.get(event, 0) + 1

    query_count = event_counts.get("query", 0)
    result_sent_count = event_counts.get("result_sent", 0)

    stats_text = [
        "<b>Статистика по сессиям:</b>",
        f"<b>Старт сессии (start):</b> {event_counts.get('start', 0)}",
        f"<b>Запросы (query):</b> {query_count}",
        f"<b>Уточнения (clarification):</b> {event_counts.get('clarification', 0)}",
        f"<b>Отправленные рекомендации (result_sent):</b> {result_sent_count}",
    ]

    await message.answer("\n".join(stats_text), parse_mode="HTML")

# Команда для вывода конкретных запросов, по которым не были отправлены рекомендации
@router.message(Command("failed_queries"))
async def failed_queries_handler(message: types.Message):
    """
    Команда для менеджера: выводит список конкретных запросов,
    по которым не были отправлены рекомендации (нет события result_sent после запроса).
    """
    if not os.path.exists(SESSIONS_LOG_FILE):
        await message.answer("Нет данных для анализа.")
        return

    # Читаем логи и группируем события по пользователям
    user_events = {}
    with open(SESSIONS_LOG_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = row["user_id"]
            try:
                ts = datetime.datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            row["timestamp_dt"] = ts
            user_events.setdefault(user_id, []).append(row)

    non_conversion_queries = []
    for user_id, events in user_events.items():
        events = sorted(events, key=lambda r: r["timestamp_dt"])
        i = 0
        while i < len(events):
            event = events[i]
            if event["event"] == "query":
                query_event = event
                j = i + 1
                conversion_found = False
                while j < len(events) and events[j]["event"] != "query":
                    if events[j]["event"] == "result_sent":
                        conversion_found = True
                        break
                    j += 1
                if not conversion_found:
                    non_conversion_queries.append(query_event)
            i += 1

    if not non_conversion_queries:
        await message.answer("Все запросы привели к отправке рекомендаций.")
        return

    lines = ["<b>Запросы без отправленных рекомендаций:</b>"]
    for q in non_conversion_queries:
        timestamp = q["timestamp"]
        user_id = q["user_id"]
        username = q["username"] if q["username"] else "N/A"
        query_text = q["text"]
        lines.append(f"{timestamp} | User: {user_id} ({username}) | Запрос: {query_text}")

    await message.answer("\n".join(lines), parse_mode="HTML")

# Команда для получения файла dataset.csv
@router.message(Command("get_dataset"))
async def get_dataset_handler(message: types.Message):
    if not os.path.exists(DATASET_FILE):
        await message.answer("Файл dataset.csv не найден.")
        return
    await message.answer_document(FSInputFile(DATASET_FILE))

# Команда для обновления файла dataset.csv (режим ожидания файла)
@router.message(Command("update_dataset"))
async def update_dataset_command(message: types.Message, state: FSMContext):
    await state.set_state(DatasetState.waiting_for_dataset)
    await message.answer("Пришлите, пожалуйста, новый файл dataset.csv.")

# Обработчик получения файла для обновления dataset.csv
@router.message(DatasetState.waiting_for_dataset)
async def update_dataset_handler(message: types.Message, state: FSMContext):
    if not message.document:
        await message.answer("Пожалуйста, отправьте файл с именем dataset.csv.")
        return
    document = message.document
    if document.file_name != "dataset.csv":
        await message.answer("Пожалуйста, отправьте файл с именем dataset.csv.")
        return
    await message.bot.download_file_by_id(document.file_id, destination=DATASET_FILE)
    await message.answer("Файл dataset.csv успешно обновлен.")
    await state.clear()

# Обработчик для отображения популярных товаров по нажатию кнопки
@router.message(F.text == "Популярные товары")
async def popular_products_handler(message: types.Message):
    top_products = get_top_popular_products()
    if not top_products:
        await message.answer("Популярных товаров пока нет.")
        return

    for product in top_products:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти", url=product['link'])]
        ])
        text = (
            f"<b>{product['name']}</b>\n\n"
            f"<b>Категория:</b> {product['category']}\n\n"
            f"{product['description']}\n\n"
            f"<b>Цена:</b> {product['price']} руб.\n"
            f"<b>Количество запросов:</b> {product['count']}"
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(QueryState.waiting_for_clarification)
async def clarification_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    original_query = data.get("original_query", "")
    accumulated = data.get("accumulated_clarification", "")
    new_input = message.text.strip()

    if accumulated:
        new_accumulated = f"{accumulated} {new_input}"
    else:
        new_accumulated = new_input

    combined_query = f"{original_query} {new_accumulated}"
    await state.update_data(accumulated_clarification=new_accumulated)
    log_session(message.from_user, "clarification", f"Original: {original_query} | New: {new_input}")

    results, need_clarification = product_search_instance.search(combined_query)

    if need_clarification:
        clarifying_texts = [
            "По комбинированному запросу товаров не найдено. Попробуйте указать, какие параметры для вас наиболее важны (например, цвет, размер, материал или бренд)",
            "Не удалось найти подходящие товары по вашему уточнению. Опишите, пожалуйста, подробнее, что именно вы ищете, и какие характеристики для вас приоритетны",
            "Комбинированный запрос не дал результатов. Уточните, пожалуйста, дополнительные детали, такие как стиль, бренд или желаемый ценовой диапазон",
            "Похоже, что результата недостаточно. Сообщите, пожалуйста, дополнительные параметры (например, функционал, материал или размер), чтобы найти лучший вариант",
            "По вашему уточнению товаров не найдено. Попробуйте подробнее описать, что именно вам нужно: укажите, какие характеристики для вас важны"
        ]
        clarifying_question = random.choice(clarifying_texts)
        await message.answer(clarifying_question)
        return

    for product in results:
        update_popular_product(product)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти", url=product['link'])]
        ])
        text = (
            f"<b>{product['name']}</b>\n\n"
            f"<b>Категория:</b> {product['category']}\n\n"
            f"{product['description']}\n\n"
            f"<b>Цена:</b> {product['price']} руб."
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        log_session(message.from_user, "result_sent", f"Product: {product['name']} | Price: {product['price']}")
    await message.answer("Если ещё что-то ищите, напишите 👇")
    await state.clear()

@router.message()
async def initial_query_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    query = message.text
    log_session(message.from_user, "query", query)
    results, need_clarification = product_search_instance.search(query)

    if need_clarification:
        await state.update_data(original_query=query, accumulated_clarification="")
        clarifying_texts = [
            "Пожалуйста, уточните: какие характеристики товара для вас наиболее важны (например, цвет, размер, материал, бренд)?",
            "Не могли бы вы подробнее описать, что именно ищете? Укажите, пожалуйста, предпочтения по стилю, цене или функционалу",
            "Чтобы подобрать для вас оптимальный товар, сообщите, пожалуйста, дополнительные детали: желаемый бренд, ценовой диапазон или особенности",
            "Опишите, пожалуйста, какие критерии для вас являются приоритетными: качество, цвет, размер или дополнительные функции",
            "Уточните, пожалуйста, какие именно параметры вас интересуют, чтобы я смог найти товар, максимально соответствующий вашим ожиданиям"
        ]
        clarifying_question = random.choice(clarifying_texts)
        await state.set_state(QueryState.waiting_for_clarification)
        await message.answer(
            f"По вашему запросу не удалось найти достаточно подходящих товаров.\n\n{clarifying_question}"
        )
        return

    for product in results:
        update_popular_product(product)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти", url=product['link'])]
        ])
        text = (
            f"<b>{product['name']}</b>\n\n"
            f"Категория: {product['category']}\n\n"
            f"{product['description']}\n\n"
            f"Цена: {product['price']}"
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        log_session(message.from_user, "result_sent", f"Product: {product['name']} | Price: {product['price']}")

    await message.answer("Если ещё что-то ищите, напишите 👇")
