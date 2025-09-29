from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class RatingCallback(CallbackData, prefix="rating"):
    value: int

