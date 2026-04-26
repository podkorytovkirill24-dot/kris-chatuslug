from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from config import config
from database import db


async def run_broadcast_scheduler(bot: Bot, tick_seconds: int = 15) -> None:
    while True:
        try:
            now_iso = datetime.utcnow().isoformat()
            tasks = await db.get_due_broadcast_tasks(now_iso)
            for task in tasks:
                kwargs = {}
                if task["target_thread_id"] is not None:
                    kwargs["message_thread_id"] = int(task["target_thread_id"])
                try:
                    await bot.send_message(
                        chat_id=int(task["target_chat_id"]),
                        text=task["message_text"],
                        **kwargs,
                    )
                except Exception as exc:
                    logging.exception(
                        "Ошибка отправки рассылки task_id=%s: %s",
                        task["id"],
                        exc,
                    )
                finally:
                    await db.update_broadcast_schedule(task["id"], int(task["interval_minutes"]))

            expired_requests = await db.get_expired_unnotified_requests(now_iso)
            for req in expired_requests:
                username = req["username"] or "без username"
                text = (
                    "⌛ Срок услуги истек\n\n"
                    f"Заявка: #{req['id']}\n"
                    f"Услуга: {req['service_title']}\n"
                    f"user_id: {req['user_id']}\n"
                    f"username: @{username}\n"
                    f"Тариф: {int(req['selected_days'] or 0)} дн.\n\n"
                    "Нужно снять услугу у пользователя."
                )
                for admin_id in config.admin_ids:
                    try:
                        await bot.send_message(admin_id, text)
                    except Exception as exc:
                        logging.exception(
                            "Ошибка отправки уведомления об истечении request_id=%s: %s",
                            req["id"],
                            exc,
                        )
                try:
                    await bot.send_message(
                        int(req["user_id"]),
                        f"⌛ Срок услуги «{req['service_title']}» истек.",
                    )
                except Exception:
                    pass
                await db.set_request_expired(int(req["id"]))
        except Exception as exc:
            logging.exception("Ошибка в планировщике рассылок: %s", exc)

        await asyncio.sleep(tick_seconds)
