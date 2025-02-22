import random
from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from data import product_search_instance

router = Router()


class QueryState(StatesGroup):
    waiting_for_clarification = State()


# При /start сбрасываем состояние и приветствуем пользователя
@router.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Напиши, что ты ищешь.")

# Обработчик ответа на уточняющий вопрос (состояние waiting_for_clarification)
@router.message(QueryState.waiting_for_clarification)
async def clarification_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    original_query = data.get("original_query", "")
    accumulated = data.get("accumulated_clarification", "")
    new_input = message.text.strip()

    # Обновляем накопленные уточнения: если уже что-то было, добавляем пробел и новое уточнение
    if accumulated:
        new_accumulated = f"{accumulated} {new_input}"
    else:
        new_accumulated = new_input

    combined_query = f"{original_query} {new_accumulated}"
    await state.update_data(accumulated_clarification=new_accumulated)

    results, need_clarification = product_search_instance.search(combined_query)

    if need_clarification:
        clarifying_texts = [
            "По комбинированному запросу товаров не найдено. Попробуйте указать, какие параметры для вас наиболее важны (например, цвет, размер, материал или бренд).",
            "Не удалось найти подходящие товары по вашему уточнению. Опишите, пожалуйста, подробнее, что именно вы ищете, и какие характеристики для вас приоритетны.",
            "Комбинированный запрос не дал результатов. Уточните, пожалуйста, дополнительные детали, такие как стиль, бренд или желаемый ценовой диапазон.",
            "Похоже, что результата недостаточно. Сообщите, пожалуйста, дополнительные параметры (например, функционал, материал или размер), чтобы найти лучший вариант.",
            "По вашему уточнению товаров не найдено. Попробуйте подробнее описать, что именно вам нужно: укажите, какие характеристики для вас важны."
        ]
        clarifying_question = random.choice(clarifying_texts)
        await message.answer(clarifying_question)
        # Остаёмся в состоянии, ожидая нового уточнения
        return

    # Если товары найдены – отправляем результаты
    for product in results:
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
    await message.answer("Если ещё что-то ищите, напишите.")
    # Сбрасываем состояние после успешного поиска
    await state.clear()


# Основной обработчик запросов, когда нет активного состояния
@router.message()
async def initial_query_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    query = message.text
    results, need_clarification = product_search_instance.search(query)

    # Если товаров недостаточно найдено – переходим в режим уточнения
    if need_clarification:
        # Сохраняем исходный запрос и сбрасываем накопленные уточнения
        await state.update_data(original_query=query, accumulated_clarification="")
        clarifying_texts = [
            "Пожалуйста, уточните: какие характеристики товара для вас наиболее важны (например, цвет, размер, материал, бренд)?",
            "Не могли бы вы подробнее описать, что именно ищете? Укажите, пожалуйста, предпочтения по стилю, цене или функционалу.",
            "Чтобы подобрать для вас оптимальный товар, сообщите, пожалуйста, дополнительные детали: желаемый бренд, ценовой диапазон или особенности.",
            "Опишите, пожалуйста, какие критерии для вас являются приоритетными: качество, цвет, размер или дополнительные функции.",
            "Уточните, пожалуйста, какие именно параметры вас интересуют, чтобы я смог найти товар, максимально соответствующий вашим ожиданиям."
        ]
        clarifying_question = random.choice(clarifying_texts)
        await state.set_state(QueryState.waiting_for_clarification)
        await message.answer(
            f"По вашему запросу не удалось найти достаточно подходящих товаров.\n\n{clarifying_question}"
        )
        return

    # Если товары найдены – отправляем каждый товар отдельным сообщением
    for product in results:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти", url=product['link'])]
        ])
        text = (
            f"<b>{product['name']}</b>\n"
            f"Категория: {product['category']}\n\n"
            f"{product['description']}\n\n"
            f"Цена: {product['price']}"
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    # В данном примере блок дополнительного уточнения закомментирован
    # Если нужно добавить дополнительное уточнение, можно раскомментировать соответствующий блок ниже
    """
    if random.random() < 0.3:
        await state.update_data(original_query=query, accumulated_clarification="")
        clarifying_texts = [
            "Уточните, какие параметры для вас особенно важны (например, материал, цвет, размер или бренд)?",
            "Можете рассказать подробнее, что именно вас интересует? Возможно, указать дополнительные характеристики или желаемый ценовой диапазон.",
            "Для более точного подбора товара укажите, пожалуйста, дополнительные детали: стиль, функциональность или конкретные особенности.",
            "Опишите, пожалуйста, дополнительные параметры, такие как качество, бренд или особенности дизайна.",
            "Поделитесь, пожалуйста, более детальной информацией: какие критерии (например, цвет, материал, функционал) для вас являются решающими?"
        ]
        clarifying_question = random.choice(clarifying_texts)
        await state.set_state(QueryState.waiting_for_clarification)
        await message.answer(clarifying_question)
    """
