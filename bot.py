#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nomer sotish boti
"""

import asyncio
import logging
import os
import threading
import time
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8636663665:AAHpJ7y4JgN-CvozM6QEPjQRxcsMZTV9qC8")
ADMIN_ID = None
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Laziz_Abduahadov")
SELLER_USERNAME = os.environ.get("SELLER_USERNAME", "@Laziz_Abduahadov")


def start_keepalive():
    try:
        port = int(os.environ.get("PORT", "8080"))
    except (TypeError, ValueError):
        port = 8080
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import socketserver

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    class Server(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

    try:
        server = Server(("0.0.0.0", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"HTTP keepalive {port} portda ishga tushdi")
    except Exception as e:
        print(f"HTTP keepalive ochilmadi: {e}")


def _render_self_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/") or "http://127.0.0.1:8080"
    while True:
        time.sleep(300)
        try:
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                code = resp.status
                print(f"self-ping OK ({code}) from {url}")
        except Exception as e:
            print(f"self-ping FAIL: {e}")


ICONS = {
    "phone": "\U0001f4de",
    "globe": "\U0001f30d",
    "money": "\U0001f4b5",
    "seller": "\U0001f464",
    "check": "\u2705",
    "cross": "\u274c",
    "chart": "\U0001f4ca",
    "gear": "\u2699\ufe0f",
    "trash": "\U0001f5d1\ufe0f",
    "new": "\U0001f195",
    "crown": "\U0001f451",
    "star": "\u2b50",
    "back": "\u2b05\ufe0f",
    "cart": "\U0001f6d2",
    "coin": "\U0001fa99",
    "menu": "\U0001f30c",
}


def build_btn(text, icon=None):
    return types.KeyboardButton(text=f"{icon} {text}" if icon else text)


T_GET = f"{ICONS['phone']} Nomer olish"
T_MENU = f"{ICONS['cart']} Menyu"
A_ADD = f"{ICONS['new']} Nomer qo'shish"
A_DEL = f"{ICONS['trash']} Nomer o'chirish"
A_SELL = f"{ICONS['seller']} Sotuvchi username"
A_STATS = f"{ICONS['chart']} Statistika"
A_ADDADMIN = f"{ICONS['crown']} Admin qo'shish"
A_MENU = f"{ICONS['menu']} Menyu"


def user_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [build_btn("Nomer olish", icon=ICONS["phone"]),
         build_btn("Menyu", icon=ICONS["cart"])],
    ], resize_keyboard=True, input_field_placeholder="Bo'limni tanlang \U0001f447")


def admin_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [build_btn("Nomer qo'shish", icon=ICONS["new"]),
         build_btn("Nomer o'chirish", icon=ICONS["trash"])],
        [build_btn("Sotuvchi username", icon=ICONS["seller"]),
         build_btn("Admin qo'shish", icon=ICONS["crown"])],
        [build_btn("Statistika", icon=ICONS["chart"]),
         build_btn("Menyu", icon=ICONS["menu"])],
    ], resize_keyboard=True)


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u274c Bekor qilish", callback_data="cancel_fsm")]
    ])


def countries_list():
    seen = []
    for n in numbers.values():
        if n["status"] == "active" and n["country"] not in seen:
            seen.append(n["country"])
    return seen


def countries_ikb():
    btns = []
    for i, c in enumerate(countries_list()):
        count = sum(1 for n in numbers.values() if n["country"] == c and n["status"] == "active")
        btns.append([InlineKeyboardButton(
            text=f"{ICONS['globe']} {c} ({count} ta)",
            callback_data=f"cnt:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=btns) if btns else None


router = Router()
bot = Bot(token=BOT_TOKEN)
bot_username_str = ""


class AddNumberFSM(StatesGroup):
    country = State()
    number = State()
    price = State()


class DeleteNumberFSM(StatesGroup):
    number = State()


class SellerFSM(StatesGroup):
    username = State()


class AddAdminFSM(StatesGroup):
    uid = State()


numbers = {}
next_id = 1
# stats tuples: ("agreed"/"rejected"/"sold", amount)
stats_log = []
admin_users = set()


def save_number(country, number, price):
    global next_id
    numbers[next_id] = {
        "id": next_id, "country": country, "number": number,
        "price": price, "status": "active",
    }
    for n in numbers.values():
        n["country_count"] = sum(1 for x in numbers.values() if x["country"] == n["country"])
    next_id += 1


def is_admin(user_id, username=None):
    if user_id == ADMIN_ID:
        return True
    if user_id in admin_users:
        return True
    if username and username.lower() == ADMIN_USERNAME.lower():
        return True
    return False


def number_list_ikb(country):
    btns = []
    for n in numbers.values():
        if n["country"] == country and n["status"] == "active":
            btns.append([InlineKeyboardButton(
                text=f"{ICONS['phone']} {n['number']} - {n['price']} so'm",
                callback_data=f"num:{n['id']}")])
    btns.append([InlineKeyboardButton(text="\u2b05\ufe0f Orqaga", callback_data="back_countries")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def number_info_ikb(num_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u2705 Kelishildi", callback_data=f"agree:{num_id}"),
         InlineKeyboardButton(text="\u274c Bu nomer kelishilmaydi", callback_data=f"reject:{num_id}")],
        [InlineKeyboardButton(text="\u2b05\ufe0f Orqaga", callback_data="back_countries")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    global bot_username_str
    if not bot_username_str:
        me = await bot.get_me()
        bot_username_str = me.username or ""
    await message.answer(
        f"\U0001f4de <b>NOMER OLISH BOTI</b>\n\n"
        f"Quyidagi bo'limdan foydalaning \U0001f447",
        parse_mode=ParseMode.HTML, reply_markup=user_menu_kb())


@router.message(F.text == T_GET)
async def nomer_olish(message: Message):
    ck = countries_ikb()
    if not ck:
        await message.answer("\U0001f4de Hozircha nomerlar yo'q, keyinroq keling!")
        return
    await message.answer(
        f"\U0001f30d <b>Davlatni tanlang:</b>",
        parse_mode=ParseMode.HTML, reply_markup=ck)


@router.callback_query(F.data == "back_countries")
async def back_countries(callback: CallbackQuery):
    await callback.message.edit_text(
        f"\U0001f30d <b>Davlatni tanlang:</b>",
        parse_mode=ParseMode.HTML, reply_markup=countries_ikb())
    await callback.answer()


@router.callback_query(F.data.startswith("cnt:"))
async def cnt_selected(callback: CallbackQuery):
    try:
        idx = int(callback.data.split(":", 1)[1])
        clist = countries_list()
        if idx < 0 or idx >= len(clist):
            await callback.answer("Xato!", show_alert=True)
            return
        country = clist[idx]
    except Exception:
        await callback.answer("Xato!", show_alert=True)
        return
    kb = number_list_ikb(country)
    if not kb.inline_keyboard or len(kb.inline_keyboard) == 1:
        await callback.answer("Bu davlatda nomer qolmagan!", show_alert=True)
        return
    await callback.message.edit_text(
        f"{ICONS['globe']} <b>{country}</b> — nomerlari:",
        parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("num:"))
async def num_selected(callback: CallbackQuery):
    num_id = int(callback.data.split(":", 1)[1])
    n = numbers.get(num_id)
    if not n or n["status"] != "active":
        await callback.answer("Bu nomer olingan!", show_alert=True)
        return
    await callback.message.edit_text(
        f"{ICONS['phone']} <b>Nomer:</b> <code>{n['number']}</code>\n"
        f"{ICONS['globe']} <b>Davlat:</b> {n['country']}\n"
        f"{ICONS['money']} <b>Narx:</b> {n['price']} so'm\n\n"
        f"{ICONS['seller']} <b>Sotuvchi:</b> {SELLER_USERNAME}\n\n"
        f"Kelishilgach nomer beriladi. Tugmani bosing:",
        parse_mode=ParseMode.HTML, reply_markup=number_info_ikb(num_id))
    await callback.answer()


@router.callback_query(F.data.startswith("agree:"))
async def num_agree(callback: CallbackQuery):
    num_id = int(callback.data.split(":", 1)[1])
    n = numbers.get(num_id)
    if not n:
        await callback.answer("Nomer topilmadi!", show_alert=True)
        return
    if n["status"] == "active":
        n["status"] = "sold"
        stats_log.append(("agreed", n["price"]))
        buyer = callback.from_user.username or callback.from_user.id
        text = (
            f"\u2705 <b>Kelishildi!</b> \u2705\n\n"
            f"{ICONS['phone']} Nomer: <code>{n['number']}</code>\n"
            f"{ICONS['globe']} Davlat: {n['country']}\n"
            f"{ICONS['money']} Narx: {n['price']} so'm\n\n"
            f"{ICONS['seller']} Sotuvchi: {SELLER_USERNAME}\n"
            f"Xaridor: @{buyer}"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        await notify_admin(f"\U0001f4de <b>Nomer kelishildi!</b>\n\n{text}")
    else:
        await callback.answer("Bu nomer allaqachon ko'rib chiqilgan!", show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("reject:"))
async def num_reject(callback: CallbackQuery):
    num_id = int(callback.data.split(":", 1)[1])
    n = numbers.get(num_id)
    if not n:
        await callback.answer("Nomer topilmadi!", show_alert=True)
        return
    if n["status"] == "active":
        n["status"] = "declined"
        stats_log.append(("rejected", n["price"]))
        buyer = callback.from_user.username or callback.from_user.id
        text = (
            f"\u274c <b>Bu nomer kelishilmaydi</b>\n\n"
            f"{ICONS['phone']} Nomer: <code>{n['number']}</code>\n"
            f"{ICONS['globe']} Davlat: {n['country']}\n"
            f"{ICONS['seller']} Sotuvchi: {SELLER_USERNAME}\n"
            f"Xaridor: @{buyer}"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        await notify_admin(f"\U0001f4de <b>Nomer kelishilmadi!</b>\n\n{text}")
    else:
        await callback.answer("Bu nomer allaqachon ko'rib chiqilgan!", show_alert=True)
    await callback.answer()


@router.message(F.text == T_MENU)
async def back_to_main(message: Message):
    await message.answer("\U0001f30c Asosiy menyu", reply_markup=user_menu_kb())


@router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("\u274c Bekor qilindi")
    await callback.answer()


async def notify_admin(text):
    global ADMIN_ID
    if not ADMIN_ID:
        return
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode=ParseMode.HTML)
    except Exception:
        pass


# ---------------- ADMIN ----------------

@router.message(Command("akam"))
async def cmd_akam(message: Message):
    args = message.text.split()
    if len(args) < 2 or args[1] != "admin123":
        await message.answer(f"{ICONS['cross']} Noto'g'ri buyruq!", parse_mode=ParseMode.HTML)
        return
    global ADMIN_ID
    user_id = message.from_user.id
    username = (message.from_user.username or "").lower()
    if ADMIN_ID:
        if username == ADMIN_USERNAME.lower():
            ADMIN_ID = user_id
            admin_users.add(user_id)
            await message.answer(
                f"{ICONS['crown']} <b>Admin Panel</b>\n\n"
                f"{ICONS['check']} Siz asosiy admin sifatida tiklandingiz!",
                parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())
        else:
            await message.answer(
                f"{ICONS['cross']} <b>Admin allaqachon o'rnatilgan!</b>",
                parse_mode=ParseMode.HTML)
        return
    ADMIN_ID = user_id
    admin_users.add(user_id)
    await message.answer(
        f"{ICONS['crown']} <b>Admin Panel</b>\n\n"
        f"{ICONS['check']} Siz admin bo'ldingiz!\n\n"
        f"{ICONS['gear']} Bo'limni tanlang:",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id, message.from_user.username):
        await message.answer(f"{ICONS['cross']} Siz admin emassiz!", parse_mode=ParseMode.HTML)
        return
    await message.answer(
        f"{ICONS['crown']} <b>ADMIN PANEL</b>\n\n"
        f"{ICONS['gear']} Bo'limni tanlang:",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())


@router.message(F.text == A_ADDADMIN)
async def admin_add_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        return
    await message.answer(
        f"{ICONS['crown']} <b>Admin qo'shish</b>\n\n"
        f"Yangi adminning Telegram <b>ID</b> raqamini yuboring.\n"
        f"<i>ID olish: @userinfobot ga xabar yuboring</i>",
        parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
    await state.set_state(AddAdminFSM.uid)


@router.message(AddAdminFSM.uid)
async def admin_add_admin_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            f"{ICONS['cross']} <b>ID raqam bo'lishi kerak!</b>\n\nQayta yuboring:",
            parse_mode=ParseMode.HTML)
        return
    uid = int(text)
    if uid == ADMIN_ID:
        await message.answer(
            f"{ICONS['cross']} Bu asosiy admin — yana qo'shish shart emas!",
            parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())
        await state.clear()
        return
    admin_users.add(uid)
    await message.answer(
        f"{ICONS['check']} <b>Admin qo'shildi!</b>\n\n"
        f"<code>{uid}</code> endi admin hisoblanadi.",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())
    await state.clear()


@router.message(F.text == A_ADD)
async def admin_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        return
    await message.answer(
        f"{ICONS['new']} <b>Nomer qo'shish</b>\n\n"
        f"{ICONS['globe']} <b>Davlat nomini</b> yozing (masalan: O'zbekiston):",
        parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
    await state.set_state(AddNumberFSM.country)


@router.message(AddNumberFSM.country)
async def add_country_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    if not message.text.strip():
        await message.answer("Davlat nomini kiriting:", reply_markup=cancel_kb())
        return
    await state.update_data(country=message.text.strip())
    await message.answer(
        f"{ICONS['phone']} <b>Nomer raqamini</b> yozing:",
        parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
    await state.set_state(AddNumberFSM.number)


@router.message(AddNumberFSM.number)
async def add_number_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    if not message.text.strip():
        await message.answer("Nomer raqamini kiriting:", reply_markup=cancel_kb())
        return
    await state.update_data(number=message.text.strip())
    await message.answer(
        f"{ICONS['money']} <b>Narxini</b> so'mda yozing (masalan: 50000):",
        parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
    await state.set_state(AddNumberFSM.price)


@router.message(AddNumberFSM.price)
async def add_price_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("Narx to'g'ri raqam bo'lishi kerak! Qayta yozing:", reply_markup=cancel_kb())
        return
    data = await state.get_data()
    price = int(text)
    save_number(data["country"], data["number"], price)
    await state.clear()
    await message.answer(
        f"{ICONS['check']} <b>Nomer qo'shildi!</b>\n\n"
        f"{ICONS['globe']} Davlat: {data['country']}\n"
        f"{ICONS['phone']} Nomer: <code>{data['number']}</code>\n"
        f"{ICONS['money']} Narx: {price} so'm",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())


@router.message(F.text == A_DEL)
async def admin_delete(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        return
    active = [n for n in numbers.values() if n["status"] == "active"]
    if not active:
        await message.answer(
            f"{ICONS['cross']} Ochirishga nomer yo'q!", parse_mode=ParseMode.HTML,
            reply_markup=admin_menu_kb())
        return
    lines = "\n".join(
        f"{n['id']}. {n['country']} — <code>{n['number']}</code> — {n['price']} so'm"
        for n in active)
    await message.answer(
        f"{ICONS['trash']} <b>Nomer o'chirish</b>\n\n"
        f"O'chirmoqchi bo'lgan nomerning <b>ID raqamini</b> yuboring:\n\n{lines}",
        parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
    await state.set_state(DeleteNumberFSM.number)


@router.message(DeleteNumberFSM.number)
async def delete_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("ID raqam bo'lishi kerak! Qayta yozing:", reply_markup=cancel_kb())
        return
    num_id = int(text)
    if num_id not in numbers:
        await message.answer(f"{ICONS['cross']} Bunday ID topilmadi!", parse_mode=ParseMode.HTML)
        return
    removed = numbers.pop(num_id)
    for n in numbers.values():
        n["country_count"] = sum(1 for x in numbers.values() if x["country"] == n["country"])
    await state.clear()
    await message.answer(
        f"{ICONS['check']} <b>O'chirildi!</b>\n\n"
        f"{ICONS['globe']} {removed['country']}\n"
        f"{ICONS['phone']} <code>{removed['number']}</code>",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())


@router.message(F.text == A_SELL)
async def admin_seller(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, message.from_user.username):
        return
    await message.answer(
        f"{ICONS['seller']} <b>Sotuvchi username</b>\n\n"
        f"Hozirgi: {SELLER_USERNAME}\n\n"
        f"Yangi usernameni yozing (masalan: @Laziz_Abduahadov):",
        parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
    await state.set_state(SellerFSM.username)


@router.message(SellerFSM.username)
async def seller_input(message: Message, state: FSMContext):
    global SELLER_USERNAME
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    new_val = message.text.strip()
    if not new_val:
        await message.answer("Username kiriting:", reply_markup=cancel_kb())
        return
    if not new_val.startswith("@"):
        new_val = "@" + new_val
    SELLER_USERNAME = new_val
    await state.clear()
    await message.answer(
        f"{ICONS['check']} <b>Sotuvchi yangilandi:</b> {SELLER_USERNAME}",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())


@router.message(F.text == A_STATS)
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id, message.from_user.username):
        return
    total = len(numbers)
    active = sum(1 for n in numbers.values() if n["status"] == "active")
    sold = sum(1 for n in numbers.values() if n["status"] == "sold")
    declined = sum(1 for n in numbers.values() if n["status"] == "declined")
    agreed_count = sum(1 for s in stats_log if s[0] == "agreed")
    rejected_count = sum(1 for s in stats_log if s[0] == "rejected")
    total_revenue = sum(s[1] for s in stats_log if s[0] in ("agreed", "rejected"))
    await message.answer(
        f"{ICONS['chart']} <b>Statistika</b>\n\n"
        f"{ICONS['new']} Jami nomerlar: <b>{total}</b>\n"
        f"{ICONS['check']} Faol nomerlar: <b>{active}</b>\n"
        f"{ICONS['money']} Sotilgan: <b>{sold}</b>\n"
        f"{ICONS['cross']} Rad etilgan: <b>{declined}</b>\n"
        f"{ICONS['check']} Kelishilganlar: <b>{agreed_count}</b>\n"
        f"{ICONS['cross']} Kelishilmaganlar: <b>{rejected_count}</b>\n"
        f"{ICONS['money']} Jami summa: <b>{total_revenue} so'm</b>",
        parse_mode=ParseMode.HTML, reply_markup=admin_menu_kb())


async def main():
    global bot
    if os.environ.get("PORT"):
        start_keepalive()
    if os.environ.get("RENDER_EXTERNAL_URL"):
        threading.Thread(target=_render_self_ping, daemon=True).start()
        print("self-ping ishga tushdi (300 soniya)")
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    global bot_username_str
    bot_username_str = me.username or ""
    logger.info(f"Bot ishga tushdi: @{bot_username_str}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())