from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import config
from database import db
from keyboards.user import (
    back_keyboard,
    confirm_text_keyboard,
    crypto_payment_keyboard,
    main_user_keyboard,
    payment_keyboard,
    service_plans_keyboard,
    services_keyboard,
)
from services.crypto_pay import CryptoPayError, create_crypto_invoice, is_crypto_invoice_paid
from services.notifier import notify_admins_about_request

router = Router()


class PurchaseStates(StatesGroup):
    waiting_custom_text = State()
    waiting_payment = State()


STATUS_TEXT = {
    "pending_payment": "💳 Ожидает оплаты",
    "pending_admin": "🕵️ На проверке администратора",
    "approved": "✅ Активна",
    "expired": "⌛ Истекла",
    "rejected": "❌ Отклонена",
    "cancelled": "🚫 Отменена",
}


def _fmt_price(price: float) -> str:
    return f"{price:g}"


def _fmt_iso(iso_value: str | None) -> str:
    if not iso_value:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_value)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso_value


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    is_admin = message.from_user.id in config.admin_ids
    if config.welcome_sticker_id:
        try:
            await message.answer_sticker(config.welcome_sticker_id)
        except Exception:
            pass
    await message.answer(
        "👋 Добро пожаловать в сервис-бота.\nВыберите действие:",
        reply_markup=main_user_keyboard(is_admin=is_admin),
    )


@router.callback_query(F.data == "user:buy")
async def buy_service_entry(call: CallbackQuery) -> None:
    services = await db.get_enabled_services()
    if not services:
        await call.message.edit_text("Сейчас нет доступных услуг.")
        await call.answer()
        return
    await call.message.edit_text(
        "🧩 Выберите услугу:",
        reply_markup=services_keyboard([dict(item) for item in services]),
    )
    await call.answer()


@router.callback_query(F.data == "user:my_requests")
async def my_requests(call: CallbackQuery) -> None:
    rows = await db.get_user_requests(call.from_user.id, limit=10)
    if not rows:
        await call.message.edit_text(
            "У вас пока нет заявок.",
            reply_markup=main_user_keyboard(is_admin=call.from_user.id in config.admin_ids),
        )
        await call.answer()
        return
    lines = ["📄 Ваши последние заявки:"]
    for row in rows:
        lines.append(
            f"#{row['id']} | {row['service_title']} | {int(row['selected_days'] or 0)} дн. | "
            f"{_fmt_price(float(row['selected_price_usdt'] or 0))} USDT | "
            f"{STATUS_TEXT.get(row['status'], row['status'])}"
        )
        if row["status"] == "approved" and row["expires_at"]:
            lines.append(f"  до: {_fmt_iso(row['expires_at'])}")
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=main_user_keyboard(is_admin=call.from_user.id in config.admin_ids),
    )
    await call.answer()


@router.callback_query(F.data == "user:back_main")
async def back_main(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_user_keyboard(is_admin=call.from_user.id in config.admin_ids),
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_service:"))
async def choose_service(call: CallbackQuery) -> None:
    service_id = int(call.data.split(":")[1])
    service = await db.get_service(service_id)
    if not service or int(service["is_enabled"]) == 0:
        await call.answer("Услуга недоступна.", show_alert=True)
        return

    plans = await db.get_service_plans(service_id, only_enabled=True)
    if not plans:
        await call.answer("Для этой услуги пока нет активных тарифов.", show_alert=True)
        return

    await call.message.edit_text(
        f"🧩 Услуга: {service['title']}\n\nВыберите срок:",
        reply_markup=service_plans_keyboard(service_id, [dict(p) for p in plans]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_plan:"))
async def choose_service_plan(call: CallbackQuery, state: FSMContext) -> None:
    _, service_id_s, plan_id_s = call.data.split(":")
    service_id = int(service_id_s)
    plan_id = int(plan_id_s)

    service = await db.get_service(service_id)
    plan = await db.get_service_plan(plan_id)
    if not service or int(service["is_enabled"]) == 0 or not plan or int(plan["is_enabled"]) == 0:
        await call.answer("Тариф недоступен.", show_alert=True)
        return
    is_priority = await db.is_priority_username(call.from_user.username)
    selected_price = 0.0 if is_priority else float(plan["price_usdt"])

    await state.update_data(
        service_id=service_id,
        service_title=str(service["title"]),
        service_plan_id=plan_id,
        selected_days=int(plan["days"]),
        selected_price_usdt=selected_price,
        is_priority=is_priority,
    )
    await state.set_state(PurchaseStates.waiting_custom_text)
    priority_note = "\n👑 Ваш приоритет активен: этот заказ будет бесплатным." if is_priority else ""
    await call.message.answer(
        f"Вы выбрали: {service['title']}\n"
        f"Тариф: {int(plan['days'])} дн. / {_fmt_price(selected_price)} USDT\n"
        f"{priority_note}\n\n"
        "✍️ Теперь отправьте текст для услуги.",
        reply_markup=back_keyboard(f"user:back_plans:{service_id}", "⬅️ К тарифам"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("user:back_plans:"))
async def back_to_plans(call: CallbackQuery, state: FSMContext) -> None:
    service_id = int(call.data.split(":")[2])
    await state.clear()
    service = await db.get_service(service_id)
    if not service or int(service["is_enabled"]) == 0:
        await call.answer("Услуга недоступна.", show_alert=True)
        return
    plans = await db.get_service_plans(service_id, only_enabled=True)
    if not plans:
        await call.answer("Для этой услуги пока нет активных тарифов.", show_alert=True)
        return
    await call.message.edit_text(
        f"🧩 Услуга: {service['title']}\n\nВыберите срок:",
        reply_markup=service_plans_keyboard(service_id, [dict(p) for p in plans]),
    )
    await call.answer()


@router.message(PurchaseStates.waiting_custom_text)
async def custom_text_received(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    service_id = int(data["service_id"])
    text_content = (message.text or "").strip()
    if len(text_content) < 2:
        await message.answer(
            "Текст слишком короткий. Введите более подробный текст.",
            reply_markup=back_keyboard(f"user:back_plans:{service_id}", "⬅️ К тарифам"),
        )
        return

    await state.update_data(text_content=text_content)
    await message.answer(
        f"Проверьте данные:\n\n"
        f"Услуга: {data['service_title']}\n"
        f"Тариф: {data['selected_days']} дн. / {_fmt_price(float(data['selected_price_usdt']))} USDT\n"
        f"Текст:\n{text_content}\n\n"
        "Подтвердить?",
        reply_markup=confirm_text_keyboard(),
    )


@router.callback_query(F.data == "confirm_text:no")
async def confirm_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Операция отменена.")
    await call.answer()


@router.callback_query(F.data == "confirm_text:yes")
async def confirm_create_request(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    request_id = await db.create_request(
        user_id=call.from_user.id,
        username=call.from_user.username,
        service_id=int(data["service_id"]),
        service_plan_id=int(data["service_plan_id"]),
        selected_days=int(data["selected_days"]),
        selected_price_usdt=float(data["selected_price_usdt"]),
        text_content=str(data["text_content"]),
        status="pending_payment",
    )
    request = await db.get_request(request_id)
    is_priority = bool(data.get("is_priority"))
    if is_priority:
        approved = await db.approve_request(request_id)
        if approved:
            await notify_admins_about_request(bot, dict(approved))
        await state.clear()
        if approved:
            await call.message.answer(
                f"👑 Приоритет применён: заявка #{request_id} оформлена бесплатно.\n"
                f"Услуга: {approved['service_title']}\n"
                f"Срок: {int(approved['selected_days'])} дн.\n"
                f"Действует до: {_fmt_iso(approved['expires_at'])}"
            )
        else:
            await call.message.answer(
                f"👑 Приоритет применён: заявка #{request_id} оформлена бесплатно и активирована."
            )
        await call.answer("Оформлено бесплатно.")
        return

    await state.set_state(PurchaseStates.waiting_payment)
    await state.update_data(request_id=request_id)

    if config.payment_mode == "crypto_pay":
        if not config.crypto_pay_api_token:
            await call.message.answer(
                "Ошибка оплаты: не задан CRYPTO_PAY_API_TOKEN в .env.\n"
                "Обратитесь к администратору."
            )
            await call.answer()
            return
        try:
            amount = float(request["selected_price_usdt"])
            invoice_id, pay_url = await create_crypto_invoice(
                amount=amount,
                request_id=request_id,
                service_title=str(request["service_title"]),
                user_id=call.from_user.id,
            )
            await db.set_request_invoice(request_id, invoice_id, pay_url)
            await call.message.answer(
                f"🧾 Заявка #{request_id} создана\n"
                f"Услуга: {request['service_title']}\n"
                f"Срок: {int(request['selected_days'])} дн.\n"
                f"💰 Сумма: {_fmt_price(float(request['selected_price_usdt']))} USDT\n\n"
                "Оплатите счёт и нажмите «Проверить оплату».",
                reply_markup=crypto_payment_keyboard(request_id, pay_url),
            )
        except (CryptoPayError, Exception):
            await call.message.answer(
                "Не удалось создать ссылку на оплату. Попробуйте снова через пару секунд."
            )
    else:
        await call.message.answer(
            "Оплата (тестовый режим):\n"
            f"Услуга: {request['service_title']}\n"
            f"Срок: {int(request['selected_days'])} дн.\n"
            f"Сумма: {_fmt_price(float(request['selected_price_usdt']))} USDT\n\n"
            "После оплаты через @send нажмите кнопку ниже.",
            reply_markup=payment_keyboard(request_id),
        )
    await call.answer()


@router.callback_query(F.data.startswith("payment:cancel:"))
async def payment_cancel(call: CallbackQuery, state: FSMContext) -> None:
    request_id = int(call.data.split(":")[2])
    req = await db.get_request(request_id)
    if not req or int(req["user_id"]) != call.from_user.id:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
    await db.update_request_status(request_id, "cancelled")
    await state.clear()
    await call.message.edit_text("Заявка отменена.")
    await call.answer()


@router.callback_query(F.data.startswith("payment:done:"))
async def payment_done(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if config.payment_mode == "crypto_pay":
        await call.answer(
            "В этом режиме оплата только по ссылке. Нажмите «Оплатить», затем «Проверить оплату».",
            show_alert=True,
        )
        return

    request_id = int(call.data.split(":")[2])
    req = await db.get_request(request_id)
    if not req or int(req["user_id"]) != call.from_user.id:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
    if req["status"] != "pending_payment":
        await call.answer("Оплата уже подтверждена ранее.", show_alert=True)
        return

    await db.update_request_status(request_id, "pending_admin")
    updated_req = await db.get_request(request_id)
    if updated_req:
        await notify_admins_about_request(bot, dict(updated_req))
    await state.clear()
    await call.message.edit_text("Платеж отмечен, заявка отправлена администраторам на проверку.")
    await call.answer("Заявка отправлена на проверку.")


@router.callback_query(F.data.startswith("payment:check:"))
async def payment_check(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    request_id = int(call.data.split(":")[2])
    req = await db.get_request(request_id)
    if not req or int(req["user_id"]) != call.from_user.id:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
    if req["status"] != "pending_payment":
        await call.answer("Оплата уже подтверждена ранее.", show_alert=True)
        return

    invoice_id = req["invoice_id"]
    if not invoice_id:
        await call.answer("Инвойс не найден для этой заявки.", show_alert=True)
        return

    paid = await is_crypto_invoice_paid(int(invoice_id))
    if not paid:
        await call.answer("Оплата пока не найдена. Попробуйте через 10-20 секунд.")
        return

    await db.update_request_status(request_id, "pending_admin")
    updated_req = await db.get_request(request_id)
    if updated_req:
        await notify_admins_about_request(bot, dict(updated_req))
    await state.clear()
    await call.message.edit_text("✅ Оплата подтверждена. Заявка отправлена администраторам на проверку.")
    await call.answer("Оплата подтверждена.")
