from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Управление услугами", callback_data="admin:services")],
            [InlineKeyboardButton(text="📥 Заявки на проверку", callback_data="admin:requests")],
            [InlineKeyboardButton(text="📚 Логи заявок", callback_data="admin:logs")],
            [InlineKeyboardButton(text="👑 Приоритет бесплатно", callback_data="admin:priority")],
            [InlineKeyboardButton(text="📣 Рассылки", callback_data="admin:broadcasts")],
        ]
    )


def admin_service_actions_keyboard(service_id: int, is_enabled: int) -> InlineKeyboardMarkup:
    toggle_text = "🔴 Отключить" if is_enabled else "🟢 Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Тарифы (дни/цена)", callback_data=f"adm_plan:list:{service_id}")],
            [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_svc:toggle:{service_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:services")],
        ]
    )


def admin_services_list_keyboard(services: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for service in services:
        status = "🟢" if int(service["is_enabled"]) else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {service['title']}",
                    callback_data=f"adm_svc:open:{service['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_plans_keyboard(service_id: int, plans: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for plan in plans:
        status = "🟢" if int(plan["is_enabled"]) else "🔴"
        price_text = f"{float(plan['price_usdt']):g}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {int(plan['days'])} дн. — {price_text} USDT",
                    callback_data=f"adm_plan:open:{plan['id']}:{service_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ Добавить тариф", callback_data=f"adm_plan:add:{service_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ К услуге", callback_data=f"adm_svc:open:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_plan_item_keyboard(plan_id: int, service_id: int, is_enabled: int) -> InlineKeyboardMarkup:
    toggle_text = "Выключить" if is_enabled else "Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"⚙️ {toggle_text}", callback_data=f"adm_plan:toggle:{plan_id}:{service_id}")],
            [InlineKeyboardButton(text="🕒 Изменить срок", callback_data=f"adm_plan:edit_days:{plan_id}:{service_id}")],
            [InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"adm_plan:edit_price:{plan_id}:{service_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_plan:delete:{plan_id}:{service_id}")],
            [InlineKeyboardButton(text="⬅️ К тарифам", callback_data=f"adm_plan:list:{service_id}")],
        ]
    )


def request_decision_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать текст", callback_data=f"adm_req:copy:{request_id}")],
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm_req:approve:{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_req:reject:{request_id}"),
            ]
        ]
    )


def admin_broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать рассылку", callback_data="adm_bc:create")],
            [InlineKeyboardButton(text="Список рассылок", callback_data="adm_bc:list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main")],
        ]
    )


def admin_priority_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Выдать приоритет", callback_data="adm_priority:add")],
            [InlineKeyboardButton(text="➖ Снять приоритет", callback_data="adm_priority:remove")],
            [InlineKeyboardButton(text="📋 Список приоритетов", callback_data="adm_priority:list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:main")],
        ]
    )


def admin_broadcast_item_keyboard(task_id: int, is_enabled: int) -> InlineKeyboardMarkup:
    toggle_text = "Выключить" if is_enabled else "Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"adm_bc:toggle:{task_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"adm_bc:delete:{task_id}")],
        ]
    )


def back_keyboard(callback_data: str, text: str = "⬅️ Назад") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]]
    )
