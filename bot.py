"""Telegram-бот магазину: сповіщення про замовлення, керування статусами, перевірка статусу клієнтом."""
import logging
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from config import ADMIN_CHAT_ID, PAYMENT_METHODS, SHOP_NAME, STATUSES

log = logging.getLogger(__name__)
router = Router()


class TrackOrder(StatesGroup):
    waiting = State()


def is_admin(user_id: int) -> bool:
    return bool(ADMIN_CHAT_ID) and user_id == ADMIN_CHAT_ID


def status_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    for key, label in STATUSES.items():
        if key != "new":
            kb.button(text=label, callback_data=f"os:{order_id}:{key}")
    kb.adjust(2)
    return kb.as_markup()


def format_order(order: dict) -> str:
    grind = {"beans": "зерно", "filter": "помел під фільтр", "espresso": "помел під еспресо"}
    lines = [
        f"<b>Замовлення #{order['id']}</b> · {STATUSES.get(order['status'], order['status'])}",
        "",
    ]
    for item in order["items"]:
        lines.append(f"• {escape(item['name'])} ({grind.get(item['grind'], item['grind'])}) × {item['qty']} — {item['price'] * item['qty']} ₴")
    lines += [
        "",
        f"Товари: {order['subtotal']} ₴ · Доставка: {order['delivery'] or 'безкоштовно'}{' ₴' if order['delivery'] else ''}",
        f"<b>Разом: {order['total']} ₴</b> · {PAYMENT_METHODS.get(order['payment'], order['payment'])}",
        "",
        f"👤 {escape(order['name'])} · 📞 {escape(order['phone'])}",
        f"📦 Нова Пошта: {escape(order['city'])}, {escape(order['branch'])}",
    ]
    if order.get("comment"):
        lines.append(f"💬 {escape(order['comment'])}")
    lines.append(f"🕒 {order['created_at'].replace('T', ' ')}")
    return "\n".join(lines)


async def notify_admin(bot: Bot, order: dict) -> None:
    if not ADMIN_CHAT_ID:
        log.warning("ADMIN_CHAT_ID не задано — сповіщення про замовлення #%s не надіслано", order["id"])
        return
    try:
        await bot.send_message(ADMIN_CHAT_ID, "🛒 Нове " + format_order(order)[1:], reply_markup=status_kb(order["id"]))
    except Exception:
        log.exception("Не вдалося надіслати сповіщення")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    text = (
        f"Привіт! Це бот <b>{escape(SHOP_NAME)}</b> ☕\n"
        "Тут можна перевірити статус замовлення — надішліть /status."
    )
    if is_admin(message.from_user.id):
        text += "\n\nАдмін: /orders — останні замовлення, /stats — виручка та статистика."
    await message.answer(text)


@router.message(Command("status"))
async def status_start(message: Message, state: FSMContext) -> None:
    await state.set_state(TrackOrder.waiting)
    await message.answer("Надішліть номер замовлення та останні 4 цифри телефону через пробіл.\nНаприклад: <code>12 4567</code>")


@router.message(TrackOrder.waiting, F.text)
async def status_check(message: Message, state: FSMContext) -> None:
    match = re.fullmatch(r"#?(\d+)\s+(\d{4})", message.text.strip())
    if not match:
        await message.answer("Формат: номер і 4 цифри телефону, наприклад <code>12 4567</code>")
        return
    order = db.get_order(int(match.group(1)))
    # Без збігу телефону не показуємо, чи існує замовлення
    if not order or re.sub(r"\D", "", order["phone"])[-4:] != match.group(2):
        await message.answer("Замовлення не знайдено. Перевірте номер і цифри телефону.")
        return
    await state.clear()
    await message.answer(
        f"Замовлення <b>#{order['id']}</b>: {STATUSES[order['status']]}\nСума: {order['total']} ₴"
    )


@router.callback_query(F.data.startswith("os:"))
async def change_status(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Недостатньо прав", show_alert=True)
        return
    _, order_id, status = call.data.split(":")
    order = db.set_status(int(order_id), status)
    if order is None:
        await call.answer("Не знайдено", show_alert=True)
        return
    await call.message.edit_text(format_order(order), reply_markup=status_kb(order["id"]))
    await call.answer(STATUSES[status])


@router.message(Command("orders"))
async def orders(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    items = db.list_orders(limit=5)
    if not items:
        await message.answer("Замовлень поки немає.")
        return
    for order in reversed(items):
        await message.answer(format_order(order), reply_markup=status_kb(order["id"]))


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    s = db.stats()
    lines = [
        "📊 <b>Статистика магазину</b>",
        f"Виручка сьогодні: {s['revenue_today']} ₴",
        f"Виручка всього: {s['revenue']} ₴",
        f"Середній чек: {s['avg_check']} ₴",
        f"Замовлень: {s['total']}",
    ]
    lines += [f"{label}: {s[key]}" for key, label in STATUSES.items()]
    if s["top"]:
        lines.append("\n🏆 Топ: " + ", ".join(f"{escape(t['name'])} ({t['qty']})" for t in s["top"]))
    await message.answer("\n".join(lines))
