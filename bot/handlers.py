from __future__ import annotations

from typing import Any

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .database import Database
from .keyboards import JOKE_BUTTON, STORY_BUTTON, main_menu_keyboard, rating_keyboard
from .schemas import RatingCallback
from .states import AddEventState
from .texts import HELP_TEXT, START_GREETING, added_event_message, global_summary_text, personal_summary_text
from .utils import build_personal_summary, parse_period

TYPE_BY_TEXT = {
    JOKE_BUTTON: "joke",
    STORY_BUTTON: "story",
}

TYPE_LABELS = {
    "joke": "анекдот",
    "story": "кулстори",
}


def register_handlers(dp: Dispatcher, database: Database) -> None:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = await _ensure_user(database, message)
        await message.answer(START_GREETING, reply_markup=main_menu_keyboard())
        await _debug_user(message, user)

    @router.message(Command(commands=["joke", "story"]))
    async def cmd_add_event(message: Message, command: CommandObject) -> None:
        type_code = command.command
        assert type_code in TYPE_LABELS
        user = await _ensure_user(database, message)
        if not command.args:
            await message.reply("Формат: /{} <минуты> <оценка (1-5)>".format(type_code))
            return
        parts = command.args.split()
        if len(parts) != 2:
            await message.reply("Нужно передать ровно два параметра: минуты и оценку.")
            return
        minutes, rating = parts
        if not minutes.isdigit() or int(minutes) <= 0:
            await message.reply("Минуты должны быть положительным числом.")
            return
        if not rating.isdigit():
            await message.reply("Оценка должна быть числом 1-5.")
            return
        rating_value = int(rating)
        if rating_value < 1 or rating_value > 5:
            await message.reply("Оценка должна быть в диапазоне 1-5.")
            return

        await database.insert_event(user_id=user.id, type_code=type_code, spent_minutes=int(minutes), rating=rating_value)
        await _send_summary(message, database, user_id=user.id, type_code=type_code, minutes=int(minutes), rating=rating_value)

    @router.message(F.text.in_(TYPE_BY_TEXT.keys()))
    async def choose_type(message: Message, state: FSMContext) -> None:
        user = await _ensure_user(database, message)
        type_code = TYPE_BY_TEXT[message.text]
        await state.update_data(user_id=user.id, type_code=type_code)
        await state.set_state(AddEventState.waiting_for_minutes)
        await message.answer("Сколько минут заняло?", reply_markup=ReplyKeyboardRemove())

    @router.message(AddEventState.waiting_for_minutes)
    async def process_minutes(message: Message, state: FSMContext) -> None:
        if message.text is None or not message.text.isdigit():
            await message.reply("Введи количество минут, целое число больше нуля.")
            return
        minutes = int(message.text)
        if minutes <= 0:
            await message.reply("Минуты должны быть положительным числом.")
            return
        await state.update_data(minutes=minutes)
        await state.set_state(AddEventState.waiting_for_rating)
        await message.answer("Оценка? Жми звёзды.", reply_markup=rating_keyboard())

    @router.callback_query(AddEventState.waiting_for_rating, RatingCallback.filter())
    async def process_rating(callback: CallbackQuery, callback_data: RatingCallback, state: FSMContext) -> None:
        data = await state.get_data()
        user_id = data.get("user_id")
        type_code = data.get("type_code")
        minutes = data.get("minutes")
        rating = callback_data.value
        if user_id is None or type_code not in TYPE_LABELS or minutes is None:
            await callback.answer("Что-то пошло не так, попробуй ещё раз.", show_alert=True)
            await state.clear()
            return

        try:
            await database.insert_event(user_id=user_id, type_code=type_code, spent_minutes=minutes, rating=rating)
        except ValueError as err:
            await callback.answer(str(err), show_alert=True)
            return

        if callback.message:
            await callback.message.edit_reply_markup()
            await _send_summary(callback.message, database, user_id=user_id, type_code=type_code, minutes=minutes, rating=rating)
        await callback.answer("Зафиксировано!")
        await state.clear()

    @router.message(Command("me"))
    async def cmd_me(message: Message, command: CommandObject) -> None:
        user = await _ensure_user(database, message)
        period = parse_period(command.args.strip()) if command.args else "week"
        records = await database.personal_stats(user.id, period)
        summary = build_personal_summary(records)
        enriched = _ensure_all_types(summary)
        text = personal_summary_text(enriched)
        await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode=None)

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())

    @router.message(Command("top"))
    async def cmd_top(message: Message, command: CommandObject) -> None:
        await _ensure_user(database, message)
        period = "week"
        min_records = 5
        if command.args:
            parts = command.args.split()
            if parts:
                period = parse_period(parts[0])
            if len(parts) > 1 and parts[1].isdigit():
                min_records = max(1, int(parts[1]))

        tops = await database.global_top(period, min_records)
        text = _format_top(tops)
        await message.answer(text, reply_markup=main_menu_keyboard())

    @router.message(Command("cancel"))
    async def cmd_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Отменил. Жми кнопку, чтобы начать снова.", reply_markup=main_menu_keyboard())

    dp.include_router(router)


async def _ensure_user(database: Database, message: Message) -> Any:
    user_obj = message.from_user
    if user_obj is None:
        raise RuntimeError("No user information in message")
    first_name = user_obj.first_name or user_obj.full_name or "Безымянный"
    return await database.get_or_create_user(
        telegram_id=user_obj.id,
        username=user_obj.username,
        first_name=first_name,
    )


async def _send_summary(message: Message, database: Database, *, user_id: int, type_code: str, minutes: int, rating: int) -> None:
    weekly_records = await database.weekly_personal_summary(user_id)
    personal_summary = build_personal_summary(weekly_records)
    enriched_summary = _ensure_all_types(personal_summary)
    personal_text = personal_summary_text(enriched_summary)
    ranks = await database.weekly_global_positions(user_id)
    global_text = global_summary_text(ranks)
    text = added_event_message(
        TYPE_LABELS[type_code],
        minutes,
        rating,
        personal_text,
        global_text,
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


def _ensure_all_types(stats: dict[str, dict[str, int | float]]) -> dict[str, dict[str, int | float]]:
    enriched: dict[str, dict[str, int | float]] = {}
    for code, label in TYPE_LABELS.items():
        record = stats.get(code, {"count": 0, "minutes": 0, "rating": 0.0})
        enriched[label] = record
    return enriched


def _format_top(tops: dict[str, Any]) -> str:
    sections = []
    sections.append(_format_top_block("Топ анекдотов", tops.get("joke_count", []), key="total"))
    sections.append(_format_top_block("Топ кулстори", tops.get("story_count", []), key="total"))
    sections.append(_format_top_block("Топ по времени", tops.get("time", []), key="total_minutes", suffix=" мин"))
    sections.append(
        _format_top_block("Топ по средней оценке", tops.get("rating", []), key="avg_rating", suffix="", decimals=2)
    )
    return "\n\n".join(sections)


def _format_top_block(title: str, rows: Any, key: str, suffix: str = "", decimals: int = 0) -> str:
    if not rows:
        return f"{title}: пока пусто"
    lines = [title]
    for index, row in enumerate(rows, start=1):
        value = row[key]
        if value is None:
            continue
        if decimals:
            value_str = f"{float(value):.{decimals}f}"
        else:
            value_str = str(value)
        display_name = row.get("display_name") or "без имени"
        lines.append(f"#{index} {display_name}: {value_str}{suffix}")
    return "\n".join(lines)


async def _debug_user(message: Message, user: Any) -> None:
    # Заглушка для возможного будущего логирования/отладки.
    _ = message, user

