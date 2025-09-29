from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .schemas import RatingCallback


JOKE_BUTTON = "➕ Анекдот"
STORY_BUTTON = "➕ Кулстори"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=JOKE_BUTTON), KeyboardButton(text=STORY_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери тип записи или команду",
    )


def rating_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="★" * value + "☆" * (5 - value), callback_data=RatingCallback(value=value).pack())
        for value in range(1, 6)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

