from html import escape

from aiogram import Bot

from config import config
from keyboards.admin import request_decision_keyboard


def _format_admin_request_html(request_row: dict) -> str:
    username = request_row.get("username")
    username_line = f"@{escape(str(username))}" if username else "без username"
    amount = float(request_row.get("selected_price_usdt", 0) or 0)
    price_text = f"{amount:g}"
    header = "🔥 <b>Новая заявка</b>"
    if amount <= 0:
        header = "👑 <b>Новая бесплатная заявка (приоритет)</b>"
    text_content = escape(str(request_row.get("text_content") or ""))
    return (
        f"{header}\n\n"
        f"ID заявки: <code>{request_row['id']}</code>\n"
        f"user_id: <code>{request_row['user_id']}</code>\n"
        f"username: {username_line}\n"
        f"Услуга: {escape(str(request_row['service_title']))}\n"
        f"Тариф: {int(request_row.get('selected_days') or 0)} дн. / {price_text} USDT\n"
        f"Текст:\n<pre>{text_content}</pre>"
    )


async def notify_admins_about_request(bot: Bot, request_row: dict) -> None:
    text = _format_admin_request_html(request_row)
    kb = request_decision_keyboard(request_row["id"])
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            continue
