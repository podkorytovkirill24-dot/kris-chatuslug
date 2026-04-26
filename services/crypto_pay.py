from __future__ import annotations

import httpx

from config import config


class CryptoPayError(Exception):
    pass


async def create_crypto_invoice(
    amount: float,
    request_id: int,
    service_title: str,
    user_id: int,
) -> tuple[int, str]:
    if not config.crypto_pay_api_token:
        raise CryptoPayError("CRYPTO_PAY_API_TOKEN не задан.")

    url = f"{config.crypto_pay_base_url}/createInvoice"
    payload = {
        "currency_type": "crypto",
        "asset": "USDT",
        "amount": f"{amount:g}",
        "description": f"Оплата услуги #{request_id}: {service_title}",
        "payload": f"request_id={request_id};user_id={user_id}",
        "allow_comments": False,
        "allow_anonymous": False,
    }
    headers = {"Crypto-Pay-API-Token": config.crypto_pay_api_token}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise CryptoPayError(f"Crypto Pay вернул ошибку: {data}")

    result = data.get("result") or {}
    invoice_id = int(result.get("invoice_id"))
    pay_url = (
        result.get("pay_url")
        or result.get("mini_app_invoice_url")
        or result.get("bot_invoice_url")
    )
    if not pay_url:
        raise CryptoPayError("Crypto Pay не вернул ссылку на оплату.")
    return invoice_id, str(pay_url)


async def is_crypto_invoice_paid(invoice_id: int) -> bool:
    if not config.crypto_pay_api_token:
        return False

    url = f"{config.crypto_pay_base_url}/getInvoices"
    payload = {"invoice_ids": str(invoice_id)}
    headers = {"Crypto-Pay-API-Token": config.crypto_pay_api_token}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        return False

    items = (data.get("result") or {}).get("items") or []
    if not items:
        return False
    status = str(items[0].get("status", "")).lower()
    return status == "paid"
