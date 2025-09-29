START_GREETING = "йо! готов считать анекдоты и кулстори. жми кнопку."

HELP_TEXT = (
    "Доступные команды:\n"
    "/start — приветствие и регистрация.\n"
    "/help — показать это сообщение.\n"
    "/joke &lt;минуты&gt; &lt;оценка&gt; — добавить анекдот в один шаг.\n"
    "/story &lt;минуты&gt; &lt;оценка&gt; — добавить кулстори в один шаг.\n"
    "/me [period] — личная статистика. Периоды: day, week, month, all (по умолчанию week).\n"
    "/top [period] [min] — глобальные топы. Период как выше, min — минимум записей для рейтинга (по умолчанию 5).\n"
    "/cancel — отменить текущий ввод."
)


def added_event_message(type_label: str, minutes: int, rating: int, personal_summary: str, global_summary: str) -> str:
    return (
        f"Добавил: {type_label}, потрачено твоего времени: {minutes} мин, оценка {rating}.\n"
        f"{personal_summary}\n"
        f"{global_summary}"
    )


def personal_summary_text(stats: dict[str, dict[str, int | float]]) -> str:
    lines = ["Твоя неделя:"]
    for type_label, values in stats.items():
        lines.append(
            f"{type_label}: {values['count']} шт, {values['minutes']} мин, средняя оценка {values['rating']}"
        )
    return "\n".join(lines)


def global_summary_text(ranks: dict[str, int | None]) -> str:
    parts: list[str] = []
    joke_rank = ranks.get("joke_rank")
    story_rank = ranks.get("story_rank")
    time_rank = ranks.get("time_rank")
    if joke_rank:
        parts.append(f"анекдоты #{joke_rank}")
    if story_rank:
        parts.append(f"кулстори #{story_rank}")
    if time_rank:
        parts.append(f"время #{time_rank}")
    if not parts:
        return "Пока без глобальных позиций, но всё впереди!"
    joined = ", ".join(parts)
    return f"Глобал: ты на {joined} за неделю."

