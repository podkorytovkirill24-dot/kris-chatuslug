from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _format_price(price: float) -> str:
    return f"{price:g}"


def main_user_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🛒 Купить услугу", callback_data="user:buy")],
        [InlineKeyboardButton(text="📄 Мои заявки", callback_data="user:my_requests")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙️ Админка", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_keyboard(services: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for service in services:
        rows.append(
            [InlineKeyboardButton(text=f"🧩 {service['title']}", callback_data=f"buy_service:{service['id']}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="user:back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_plans_keyboard(service_id: int, plans: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for plan in plans:
        price_text = _format_price(float(plan["price_usdt"]))
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"⏳ {int(plan['days'])} дн. — {price_text} USDT",
                    callback_data=f"buy_plan:{service_id}:{plan['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ К услугам", callback_data="user:buy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_text_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_text:yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_text:no"),
            ]
        ]
    )


def payment_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"payment:done:{request_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"payment:cancel:{request_id}")],
        ]
    )


def crypto_payment_keyboard(request_id: int, pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"payment:check:{request_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"payment:cancel:{request_id}")],
        ]
    )


def back_keyboard(callback_data: str, text: str = "⬅️ Назад") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]]
    )
