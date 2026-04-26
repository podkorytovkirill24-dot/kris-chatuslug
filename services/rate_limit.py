from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, delay_seconds: float = 0.7) -> None:
        self.delay_seconds = delay_seconds
        self._last_seen: dict[tuple[int, str], float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        event_type = "other"

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            event_type = "message"
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            event_type = "callback"

        if user_id is None:
            return await handler(event, data)

        key = (user_id, event_type)
        now = time.monotonic()
        delta = now - self._last_seen[key]
        if delta < self.delay_seconds:
            if isinstance(event, CallbackQuery):
                await event.answer("Слишком часто, попробуйте чуть позже.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("Слишком часто отправляете запросы. Подождите немного.")
            return None

        self._last_seen[key] = now
        return await handler(event, data)
