import logging

from aiogram import Router
from aiogram.types import ErrorEvent

router = Router()


@router.error()
async def on_error(event: ErrorEvent) -> bool:
    logging.exception("Необработанная ошибка: %s", event.exception)
    return True
