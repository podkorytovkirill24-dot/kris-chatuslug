from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from config import config


DEFAULT_SERVICES = [
    ("prefix", "Префикс", 1),
    ("pinned_message", "Закреплённое сообщение", 1),
    ("mandatory_subscription", "Обязательная подписка", 1),
    ("message_broadcast", "Рассылка сообщений", 1),
]

DEFAULT_PLANS = {
    "prefix": [(10, 1.0), (20, 2.0), (30, 3.0)],
    "pinned_message": [(6, 1.0), (12, 1.5), (24, 2.5)],
    "mandatory_subscription": [(10, 1.0), (20, 2.0), (30, 3.0)],
    "message_broadcast": [(3, 1.5), (6, 3.0)],
}


def normalize_username(raw: str) -> str:
    return raw.strip().lstrip("@").lower()


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._conn is None:
            parent_dir = os.path.dirname(os.path.abspath(self.path))
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            self._conn = await aiosqlite.connect(self.path)
            self._conn.row_factory = aiosqlite.Row

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cur = await self._conn.execute(query, params)
            await self._conn.commit()
            return cur

    async def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cur = await self._conn.execute(query, params)
            row = await cur.fetchone()
            await cur.close()
            return row

    async def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        await self.connect()
        assert self._conn is not None
        async with self._lock:
            cur = await self._conn.execute(query, params)
            rows = await cur.fetchall()
            await cur.close()
            return rows

    async def init(self) -> None:
        await self._execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        await self._execute(
            """
            CREATE TABLE IF NOT EXISTS service_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                days INTEGER NOT NULL,
                price_usdt REAL NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(service_id, days),
                FOREIGN KEY(service_id) REFERENCES services(id)
            )
            """
        )
        await self._execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                service_id INTEGER NOT NULL,
                service_plan_id INTEGER,
                selected_days INTEGER NOT NULL DEFAULT 0,
                selected_price_usdt REAL NOT NULL DEFAULT 0,
                text_content TEXT NOT NULL,
                invoice_id INTEGER,
                invoice_url TEXT,
                status TEXT NOT NULL,
                approved_at TEXT,
                expires_at TEXT,
                expiry_notified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(service_id) REFERENCES services(id),
                FOREIGN KEY(service_plan_id) REFERENCES service_plans(id)
            )
            """
        )
        await self._execute(
            """
            CREATE TABLE IF NOT EXISTS broadcast_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                target_chat_id INTEGER NOT NULL,
                target_thread_id INTEGER,
                interval_minutes INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                last_sent_at TEXT,
                next_run_at TEXT NOT NULL
            )
            """
        )
        await self._execute(
            """
            CREATE TABLE IF NOT EXISTS priority_users (
                user_id INTEGER PRIMARY KEY,
                granted_by INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._execute(
            """
            CREATE TABLE IF NOT EXISTS priority_usernames (
                username TEXT PRIMARY KEY,
                granted_by INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        await self._migrate_services_table()
        await self._migrate_requests_table()
        await self._seed_services()
        await self._seed_default_plans()

    async def _migrate_services_table(self) -> None:
        rows = await self._fetchall("PRAGMA table_info(services)")
        columns = {row["name"] for row in rows}
        if "is_enabled" not in columns:
            await self._execute("ALTER TABLE services ADD COLUMN is_enabled INTEGER NOT NULL DEFAULT 1")

    async def _migrate_requests_table(self) -> None:
        rows = await self._fetchall("PRAGMA table_info(requests)")
        columns = {row["name"] for row in rows}

        migrate_columns: list[tuple[str, str]] = [
            ("invoice_id", "INTEGER"),
            ("invoice_url", "TEXT"),
            ("service_plan_id", "INTEGER"),
            ("selected_days", "INTEGER NOT NULL DEFAULT 0"),
            ("selected_price_usdt", "REAL NOT NULL DEFAULT 0"),
            ("approved_at", "TEXT"),
            ("expires_at", "TEXT"),
            ("expiry_notified", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for col, col_type in migrate_columns:
            if col not in columns:
                await self._execute(f"ALTER TABLE requests ADD COLUMN {col} {col_type}")

    async def _seed_services(self) -> None:
        for key, title, is_enabled in DEFAULT_SERVICES:
            await self._execute(
                """
                INSERT OR IGNORE INTO services(key, title, is_enabled)
                VALUES(?, ?, ?)
                """,
                (key, title, is_enabled),
            )

    async def _seed_default_plans(self) -> None:
        services = await self.get_all_services()
        for service in services:
            key = service["key"]
            plans = DEFAULT_PLANS.get(key, [])
            existing = await self.get_service_plans(int(service["id"]), only_enabled=False)
            existing_days = {int(p["days"]) for p in existing}
            for days, price in plans:
                if days not in existing_days:
                    await self.upsert_service_plan(int(service["id"]), days, float(price))

    async def get_enabled_services(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM services WHERE is_enabled = 1 ORDER BY id")

    async def get_all_services(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM services ORDER BY id")

    async def get_service(self, service_id: int) -> aiosqlite.Row | None:
        return await self._fetchone("SELECT * FROM services WHERE id = ?", (service_id,))

    async def toggle_service(self, service_id: int) -> None:
        await self._execute(
            "UPDATE services SET is_enabled = CASE is_enabled WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
            (service_id,),
        )

    async def get_service_plans(self, service_id: int, only_enabled: bool = False) -> list[aiosqlite.Row]:
        if only_enabled:
            return await self._fetchall(
                "SELECT * FROM service_plans WHERE service_id = ? AND is_enabled = 1 ORDER BY days ASC",
                (service_id,),
            )
        return await self._fetchall(
            "SELECT * FROM service_plans WHERE service_id = ? ORDER BY days ASC",
            (service_id,),
        )

    async def get_service_plan(self, plan_id: int) -> aiosqlite.Row | None:
        return await self._fetchone("SELECT * FROM service_plans WHERE id = ?", (plan_id,))

    async def upsert_service_plan(self, service_id: int, days: int, price_usdt: float) -> int:
        now = datetime.utcnow().isoformat()
        existing = await self._fetchone(
            "SELECT id FROM service_plans WHERE service_id = ? AND days = ?",
            (service_id, days),
        )
        if existing:
            plan_id = int(existing["id"])
            await self._execute(
                """
                UPDATE service_plans
                SET price_usdt = ?, is_enabled = 1, updated_at = ?
                WHERE id = ?
                """,
                (price_usdt, now, plan_id),
            )
            return plan_id

        cur = await self._execute(
            """
            INSERT INTO service_plans(service_id, days, price_usdt, is_enabled, created_at, updated_at)
            VALUES(?, ?, ?, 1, ?, ?)
            """,
            (service_id, days, price_usdt, now, now),
        )
        return int(cur.lastrowid)

    async def toggle_service_plan(self, plan_id: int) -> None:
        await self._execute(
            "UPDATE service_plans SET is_enabled = CASE is_enabled WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
            (plan_id,),
        )

    async def delete_service_plan(self, plan_id: int) -> None:
        await self._execute("DELETE FROM service_plans WHERE id = ?", (plan_id,))

    async def update_service_plan_price(self, plan_id: int, price_usdt: float) -> None:
        now = datetime.utcnow().isoformat()
        await self._execute(
            "UPDATE service_plans SET price_usdt = ?, updated_at = ? WHERE id = ?",
            (price_usdt, now, plan_id),
        )

    async def update_service_plan_days(self, plan_id: int, days: int) -> bool:
        plan = await self.get_service_plan(plan_id)
        if not plan:
            return False
        service_id = int(plan["service_id"])
        conflict = await self._fetchone(
            "SELECT id FROM service_plans WHERE service_id = ? AND days = ? AND id != ?",
            (service_id, days, plan_id),
        )
        if conflict:
            return False
        now = datetime.utcnow().isoformat()
        await self._execute(
            "UPDATE service_plans SET days = ?, updated_at = ? WHERE id = ?",
            (days, now, plan_id),
        )
        return True

    async def create_request(
        self,
        user_id: int,
        username: str | None,
        service_id: int,
        service_plan_id: int,
        selected_days: int,
        selected_price_usdt: float,
        text_content: str,
        status: str = "pending_payment",
    ) -> int:
        now = datetime.utcnow().isoformat()
        cur = await self._execute(
            """
            INSERT INTO requests(
                user_id, username, service_id, service_plan_id,
                selected_days, selected_price_usdt, text_content,
                status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                service_id,
                service_plan_id,
                selected_days,
                selected_price_usdt,
                text_content,
                status,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)

    async def get_request(self, request_id: int) -> aiosqlite.Row | None:
        return await self._fetchone(
            """
            SELECT r.*, s.title AS service_title
            FROM requests r
            JOIN services s ON s.id = r.service_id
            WHERE r.id = ?
            """,
            (request_id,),
        )

    async def get_pending_requests(self) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT r.*, s.title AS service_title
            FROM requests r
            JOIN services s ON s.id = r.service_id
            WHERE r.status = 'pending_admin'
            ORDER BY r.created_at ASC
            """
        )

    async def get_requests_log(self, limit: int = 50) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT r.*, s.title AS service_title
            FROM requests r
            JOIN services s ON s.id = r.service_id
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    async def get_user_requests(self, user_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT r.*, s.title AS service_title
            FROM requests r
            JOIN services s ON s.id = r.service_id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )

    async def update_request_status(self, request_id: int, status: str) -> None:
        now = datetime.utcnow().isoformat()
        await self._execute(
            "UPDATE requests SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, request_id),
        )

    async def approve_request(self, request_id: int) -> aiosqlite.Row | None:
        req = await self.get_request(request_id)
        if not req:
            return None
        now = datetime.utcnow()
        days = int(req["selected_days"] or 0)
        expires_at = (now + timedelta(days=days)).isoformat() if days > 0 else None
        await self._execute(
            """
            UPDATE requests
            SET status = 'approved', approved_at = ?, expires_at = ?, updated_at = ?, expiry_notified = 0
            WHERE id = ?
            """,
            (now.isoformat(), expires_at, now.isoformat(), request_id),
        )
        return await self.get_request(request_id)

    async def set_request_expired(self, request_id: int) -> None:
        now = datetime.utcnow().isoformat()
        await self._execute(
            """
            UPDATE requests
            SET status = 'expired', expiry_notified = 1, updated_at = ?
            WHERE id = ?
            """,
            (now, request_id),
        )

    async def get_expired_unnotified_requests(self, now_iso: str) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT r.*, s.title AS service_title
            FROM requests r
            JOIN services s ON s.id = r.service_id
            WHERE r.status = 'approved'
              AND r.expires_at IS NOT NULL
              AND r.expires_at <= ?
              AND r.expiry_notified = 0
            ORDER BY r.expires_at ASC
            """,
            (now_iso,),
        )

    async def set_request_invoice(self, request_id: int, invoice_id: int, invoice_url: str) -> None:
        now = datetime.utcnow().isoformat()
        await self._execute(
            "UPDATE requests SET invoice_id = ?, invoice_url = ?, updated_at = ? WHERE id = ?",
            (invoice_id, invoice_url, now, request_id),
        )

    async def create_broadcast_task(
        self,
        admin_id: int,
        target_chat_id: int,
        target_thread_id: int | None,
        interval_minutes: int,
        message_text: str,
    ) -> int:
        now = datetime.utcnow()
        next_run_at = (now + timedelta(minutes=interval_minutes)).isoformat()
        cur = await self._execute(
            """
            INSERT INTO broadcast_tasks(
                admin_id, target_chat_id, target_thread_id, interval_minutes, message_text, is_enabled, next_run_at
            )
            VALUES(?, ?, ?, ?, ?, 1, ?)
            """,
            (admin_id, target_chat_id, target_thread_id, interval_minutes, message_text, next_run_at),
        )
        return int(cur.lastrowid)

    async def get_broadcast_tasks(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM broadcast_tasks ORDER BY id DESC")

    async def get_due_broadcast_tasks(self, now_iso: str) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT * FROM broadcast_tasks
            WHERE is_enabled = 1 AND next_run_at <= ?
            ORDER BY next_run_at ASC
            """,
            (now_iso,),
        )

    async def update_broadcast_schedule(self, task_id: int, interval_minutes: int) -> None:
        now = datetime.utcnow()
        last_sent = now.isoformat()
        next_run = (now + timedelta(minutes=interval_minutes)).isoformat()
        await self._execute(
            "UPDATE broadcast_tasks SET last_sent_at = ?, next_run_at = ? WHERE id = ?",
            (last_sent, next_run, task_id),
        )

    async def toggle_broadcast_task(self, task_id: int) -> None:
        await self._execute(
            """
            UPDATE broadcast_tasks
            SET is_enabled = CASE is_enabled WHEN 1 THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            (task_id,),
        )

    async def delete_broadcast_task(self, task_id: int) -> None:
        await self._execute("DELETE FROM broadcast_tasks WHERE id = ?", (task_id,))

    async def set_priority_user(self, user_id: int, granted_by: int) -> None:
        now = datetime.utcnow().isoformat()
        await self._execute(
            """
            INSERT INTO priority_users(user_id, granted_by, created_at)
            VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET granted_by = excluded.granted_by, created_at = excluded.created_at
            """,
            (user_id, granted_by, now),
        )

    async def remove_priority_user(self, user_id: int) -> None:
        await self._execute("DELETE FROM priority_users WHERE user_id = ?", (user_id,))

    async def is_priority_user(self, user_id: int) -> bool:
        row = await self._fetchone("SELECT 1 FROM priority_users WHERE user_id = ?", (user_id,))
        return row is not None

    async def get_priority_users(self, limit: int = 100) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT user_id, granted_by, created_at
            FROM priority_users
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    async def set_priority_username(self, username: str, granted_by: int) -> None:
        norm_username = normalize_username(username)
        now = datetime.utcnow().isoformat()
        await self._execute(
            """
            INSERT INTO priority_usernames(username, granted_by, created_at)
            VALUES(?, ?, ?)
            ON CONFLICT(username) DO UPDATE
            SET granted_by = excluded.granted_by, created_at = excluded.created_at
            """,
            (norm_username, granted_by, now),
        )

    async def remove_priority_username(self, username: str) -> None:
        norm_username = normalize_username(username)
        await self._execute("DELETE FROM priority_usernames WHERE username = ?", (norm_username,))

    async def is_priority_username(self, username: str | None) -> bool:
        if not username:
            return False
        norm_username = normalize_username(username)
        row = await self._fetchone("SELECT 1 FROM priority_usernames WHERE username = ?", (norm_username,))
        return row is not None

    async def get_priority_usernames(self, limit: int = 100) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """
            SELECT username, granted_by, created_at
            FROM priority_usernames
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )


db = Database(config.db_path)
