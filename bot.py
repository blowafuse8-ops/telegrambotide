import sqlite3
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ----------------- НАСТРОЙКИ -----------------
TOKEN = "7512515821:AAGKP4iysC3YfmZ9zje7NS2VstyazOm0dD0"
ADMIN_IDS = [7817856373, 966731654]
CHANNEL_ID = "-1003157439297"
BANK_CARD = "2204 1201 3108 2352"
BANK_NAME = "ЮMoney bank"
BOT_NAME = "Убежище Х"
SEARCH_COST = 10  # Стоимость поиска в Coins (обновлено с 20 на 10)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ----------------- БАЗА ДАННЫХ -----------------
def init_db():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        posts_count INTEGER DEFAULT 0,
        joined_date TEXT
    )
    """)

    # Таблица постов
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        anon INTEGER,
        status TEXT,
        media_type TEXT,
        media_ids TEXT,
        created_at TEXT,
        moderated_by INTEGER,
        moderated_at TEXT
    )
    """)

    # Таблица платежей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount_coins INTEGER,
        price INTEGER,
        status TEXT,
        screenshot TEXT,
        created_at TEXT,
        moderated_by INTEGER,
        moderated_at TEXT
    )
    """)

    # Таблица заявок на удаление
    cur.execute("""
    CREATE TABLE IF NOT EXISTS delete_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        screenshot TEXT,
        status TEXT,
        created_at TEXT
    )
    """)

    # Таблица заявок на поиск людей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS search_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        request_type TEXT,  -- 'photo' или 'text'
        data TEXT,          -- текст запроса или описание к фото
        photo_id TEXT,      -- file_id фото (если есть)
        status TEXT,        -- 'pending', 'answered'
        created_at TEXT,
        answered_by INTEGER,
        answered_at TEXT,
        answer_text TEXT
    )
    """)

    # Добавляем новые колонки если их нет
    try:
        cur.execute("ALTER TABLE users ADD COLUMN posts_count INTEGER DEFAULT 0")
    except:
        pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN joined_date TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE posts ADD COLUMN moderated_by INTEGER")
    except:
        pass
    try:
        cur.execute("ALTER TABLE posts ADD COLUMN moderated_at TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE payments ADD COLUMN moderated_by INTEGER")
    except:
        pass
    try:
        cur.execute("ALTER TABLE payments ADD COLUMN moderated_at TEXT")
    except:
        pass

    conn.commit()
    conn.close()

def register_user(user_id: int, username: str | None):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
    exists = cur.fetchone()
    
    if not exists:
        cur.execute("""
            INSERT INTO users (id, username, balance, posts_count, joined_date) 
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, 0, 0, datetime.now(timezone.utc).isoformat()))
    else:
        cur.execute("""
            UPDATE users SET username = ? 
            WHERE id = ? AND (username IS NULL OR username != ?)
        """, (username, user_id, username))
    
    conn.commit()
    conn.close()

def get_balance(user_id: int) -> int:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0

def update_balance(user_id: int, amount: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id, username, balance, posts_count) VALUES (?, ?, ?, ?)", 
                (user_id, None, 0, 0))
    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_username_from_db(user_id: int) -> str | None:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res and res[0] else None

def get_all_users() -> list:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT id FROM users")
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    return users

def get_stats() -> dict:
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM posts")
    total_posts = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM posts WHERE status='approved'")
    approved_posts = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM posts WHERE status='pending'")
    pending_posts = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(balance) FROM users")
    total_coins = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='approved'")
    total_payments = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(amount_coins) FROM payments WHERE status='approved'")
    coins_sold = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM search_requests")
    total_searches = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM search_requests WHERE status='pending'")
    pending_searches = cur.fetchone()[0]
    
    conn.close()
    
    return {
        "total_users": total_users,
        "total_posts": total_posts,
        "approved_posts": approved_posts,
        "pending_posts": pending_posts,
        "total_coins": total_coins,
        "total_payments": total_payments,
        "coins_sold": coins_sold,
        "total_searches": total_searches,
        "pending_searches": pending_searches
    }

# ----------------- FSM -----------------
class PostState(StatesGroup):
    waiting_for_post = State()

class QuestionState(StatesGroup):
    waiting_for_question = State()
    waiting_for_answer = State()

class BuyCoinsState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_screenshot = State()

class DeletePostState(StatesGroup):
    waiting_for_info = State()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_coin_amount = State()
    waiting_for_coin_operation = State()
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_media = State()
    waiting_for_search_answer = State()

# FSM для поиска людей
class SearchStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_text_data = State()

# ----------------- КНОПКИ -----------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Предложить пост", callback_data="menu_post")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="menu_balance")],
        [InlineKeyboardButton(text="🔍 Найти человека", callback_data="menu_search")],
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="help_question")]
    ])

def post_choice_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 От своего имени", callback_data="post_self")],
        [InlineKeyboardButton(text="👻 Анонимно", callback_data="post_anon")],
        [InlineKeyboardButton(text="🗑 Удалить пост (5 Coins)", callback_data="post_delete")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

# Меню поиска
def search_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Поиск по фото", callback_data="search_photo")],
        [InlineKeyboardButton(text="📝 Поиск по данным", callback_data="search_text")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

def payment_admin_markup(payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"payment_approve_{payment_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"payment_reject_{payment_id}")
        ]
    ])

def moderation_markup(post_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"moderate_approve_{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"moderate_reject_{post_id}")
        ]
    ])

def delete_request_admin_markup(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"del_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"del_reject_{request_id}")
        ]
    ])

# Кнопка для ответа на поисковый запрос
def search_request_admin_markup(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Ответить на запрос", callback_data=f"search_answer_{request_id}")
        ]
    ])

# ИЗМЕНЕНО: меню баланса с новой кнопкой "Заработать Coins"
def balance_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить Coins", callback_data="balance_buy")],
        [InlineKeyboardButton(text="💰 Заработать Coins", callback_data="balance_earn")],  # НОВАЯ КНОПКА
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Выдать Coins", callback_data="admin_add_coins")],
        [InlineKeyboardButton(text="💸 Забрать Coins", callback_data="admin_remove_coins")],
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔍 Заявки на поиск", callback_data="admin_search_requests")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])

# ----------------- СТАРТ -----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    text = (
        f"👋 <b>Добро пожаловать в Убежище!</b>\n\n"
        f"• За каждый одобренный пост вы получаете <b>1 Coin</b>💰 \n\n"
        f"🔍 <b>Новая функция:</b>\n"
        f"• Поиск людей по фото или данным (<b>{SEARCH_COST} Coins</b>)\n\n"
        f"Выберите действие 👇"
    )
    await message.answer(text, reply_markup=main_menu())

# ----------------- ПОИСК ЛЮДЕЙ -----------------
@dp.callback_query(F.data == "menu_search")
async def menu_search(cb: CallbackQuery):
    text = (
        "🔍 <b>ПОИСК ЛЮДЕЙ</b>\n\n"
        "Мы поможем найти человека по фото или известным данным.\n\n"
        "🔎 <b>Как работает:</b>\n"
        "1. Вы выбираете способ поиска\n"
        "2. Отправляете фото или данные\n"
        f"3. С вас списывается <b>{SEARCH_COST} Coins</b>\n"
        "4. Мы ищем информацию в течение часа\n"
        "5. Вы получаете результат\n\n"
        "Выберите способ поиска:"
    )
    await cb.message.edit_text(text, reply_markup=search_menu())
    await cb.answer()

@dp.callback_query(F.data == "search_photo")
async def search_photo(cb: CallbackQuery, state: FSMContext):
    # Проверяем баланс
    balance = get_balance(cb.from_user.id)
    if balance < SEARCH_COST:
        await cb.message.edit_text(
            f"❌ У вас недостаточно Coins.\n\n"
            f"💰 Баланс: {balance} Coins\n"
            f"💎 Нужно: {SEARCH_COST} Coins\n\n"
            f"Купите или заработайте Coins:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Купить Coins", callback_data="menu_balance")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_search")]
            ])
        )
        await cb.answer()
        return
    
    await state.set_state(SearchStates.waiting_for_photo)
    await cb.message.edit_text(
        "📸 <b>ПОИСК ПО ФОТО</b>\n\n"
        "Отправьте ЧЕТКОЕ фото лица человека.\n\n"
        "📋 <b>Что указать в подписи к фото (необязательно):</b>\n"
        "• Имя, возраст\n"
        "• Где сделано фото\n"
        "• Любые известные данные\n\n"
        "🎯 <b>Что хотите узнать:</b>\n"
        "• Номер телефона\n"
        "• Адрес проживания\n"
        "• Социальные сети\n"
        "• Любые другие данные\n\n"
        f"💰 <b>Стоимость: {SEARCH_COST} Coins</b>\n"
        "⏳ <b>Время ожидания: до 1 часа</b>\n\n"
        "📸 Отправьте фото (можно с подписью):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_search")]
        ])
    )
    await cb.answer()

@dp.message(SearchStates.waiting_for_photo, F.photo)
async def handle_search_photo(message: Message, state: FSMContext):
    # Проверяем баланс еще раз
    balance = get_balance(message.from_user.id)
    if balance < SEARCH_COST:
        await message.answer(
            f"❌ Недостаточно Coins. Баланс: {balance}, нужно: {SEARCH_COST}",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    # Получаем фото и подпись
    photo_id = message.photo[-1].file_id
    caption = message.caption or "Без описания"
    
    # Списываем Coins
    update_balance(message.from_user.id, -SEARCH_COST)
    
    # Сохраняем заявку в БД
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO search_requests 
        (user_id, request_type, data, photo_id, status, created_at) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        "photo",
        caption,
        photo_id,
        "pending",
        datetime.now(timezone.utc).isoformat()
    ))
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    # Подтверждение пользователю
    await message.answer(
        f"✅ <b>ЗАЯВКА ПРИНЯТА!</b>\n\n"
        f"📸 Фото получено\n"
        f"📝 Описание: {caption[:100]}{'...' if len(caption) > 100 else ''}\n"
        f"💰 Списано: {SEARCH_COST} Coins\n\n"
        f"⏳ Ожидайте результат в течение 1 часа.\n"
        f"Мы пришлем ответ в этот чат.",
        reply_markup=main_menu()
    )
    await state.clear()
    
    # Уведомление админам
    username = message.from_user.username
    pretty_user = f"@{username}" if username else str(message.from_user.id)
    
    caption_text = (
        f"🔍 <b>НОВАЯ ЗАЯВКА НА ПОИСК (ID: {request_id})</b>\n\n"
        f"👤 От: {pretty_user}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"📸 Тип: Поиск по фото\n"
        f"💰 Списано: {SEARCH_COST} Coins\n"
        f"📝 Описание: {caption}\n\n"
        f"Нажмите кнопку, чтобы ответить пользователю:"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo_id,
                caption=caption_text,
                reply_markup=search_request_admin_markup(request_id)
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

@dp.callback_query(F.data == "search_text")
async def search_text(cb: CallbackQuery, state: FSMContext):
    # Проверяем баланс
    balance = get_balance(cb.from_user.id)
    if balance < SEARCH_COST:
        await cb.message.edit_text(
            f"❌ У вас недостаточно Coins.\n\n"
            f"💰 Баланс: {balance} Coins\n"
            f"💎 Нужно: {SEARCH_COST} Coins\n\n"
            f"Купите или заработайте Coins:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Купить Coins", callback_data="menu_balance")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_search")]
            ])
        )
        await cb.answer()
        return
    
    await state.set_state(SearchStates.waiting_for_text_data)
    await cb.message.edit_text(
        "📝 <b>ПОИСК ПО ДАННЫМ</b>\n\n"
        "Напишите ВСЕ что знаете о человеке и что хотели бы узнать об этом человеке!\n\n"
        "📋 <b>ЧТО УКАЗАТЬ:</b>\n"
        "• Фамилия, имя, отчество\n"
        "• Дата рождения\n"
        "• Номер телефона\n"
        "• Город/регион\n"
        "• Место работы/учебы\n"
        "• Социальные сети\n"
        "• Любая другая информация\n\n"
        "🎯 <b>ЧТО ХОТИТЕ УЗНАТЬ:</b>\n"
        "• Номер телефона\n"
        "• Адрес проживания\n"
        "• Место работы\n"
        "• Семейное положение\n"
        "• Социальные сети\n"
        "• Фотографии\n"
        "• Любые другие данные\n\n"
        "💡 <b>Пример:</b>\n"
        '"Ищу Иванова Ивана Ивановича, примерно 30 лет, Москва. Нужен номер телефона и адрес. Знаю что работал в Газпроме."\n\n'
        f"💰 <b>Стоимость: {SEARCH_COST} Coins</b>\n"
        "⏳ <b>Время ожидания: до 1 часа</b>\n\n"
        "✍️ Отправьте данные одним сообщением:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_search")]
        ])
    )
    await cb.answer()

@dp.message(SearchStates.waiting_for_text_data, F.text)
async def handle_search_text(message: Message, state: FSMContext):
    # Проверяем баланс
    balance = get_balance(message.from_user.id)
    if balance < SEARCH_COST:
        await message.answer(
            f"❌ Недостаточно Coins. Баланс: {balance}, нужно: {SEARCH_COST}",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    
    text_data = message.text
    
    # Списываем Coins
    update_balance(message.from_user.id, -SEARCH_COST)
    
    # Сохраняем заявку в БД
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO search_requests 
        (user_id, request_type, data, status, created_at) 
        VALUES (?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        "text",
        text_data,
        "pending",
        datetime.now(timezone.utc).isoformat()
    ))
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    # Подтверждение пользователю
    await message.answer(
        f"✅ <b>ЗАЯВКА ПРИНЯТА!</b>\n\n"
        f"📝 Данные получены:\n"
        f"{text_data[:200]}{'...' if len(text_data) > 200 else ''}\n\n"
        f"💰 Списано: {SEARCH_COST} Coins\n\n"
        f"⏳ Ожидайте результат в течение 1 часа.\n"
        f"Мы пришлем ответ в этот чат.",
        reply_markup=main_menu()
    )
    await state.clear()
    
    # Уведомление админам
    username = message.from_user.username
    pretty_user = f"@{username}" if username else str(message.from_user.id)
    
    caption = (
        f"🔍 <b>НОВАЯ ЗАЯВКА НА ПОИСК (ID: {request_id})</b>\n\n"
        f"👤 От: {pretty_user}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"📝 Тип: Поиск по данным\n"
        f"💰 Списано: {SEARCH_COST} Coins\n"
        f"📄 Данные:\n{text_data}\n\n"
        f"Нажмите кнопку, чтобы ответить пользователю:"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                caption,
                reply_markup=search_request_admin_markup(request_id)
            )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# ----------------- ОТВЕТ АДМИНА НА ПОИСКОВЫЙ ЗАПРОС -----------------
@dp.callback_query(F.data.startswith("search_answer_"))
async def search_answer(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    request_id = int(cb.data.split("_")[-1])
    
    # Получаем информацию о запросе
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, request_type, data, status 
        FROM search_requests WHERE id=?
    """, (request_id,))
    request = cur.fetchone()
    conn.close()
    
    if not request:
        await cb.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    user_id, req_type, req_data, status = request
    
    if status != "pending":
        await cb.answer("❌ На эту заявку уже ответили", show_alert=True)
        return
    
    await state.update_data(search_request_id=request_id, search_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_search_answer)
    
    await cb.message.answer(
        f"💬 Введите ответ для пользователя (ID: {user_id})\n\n"
        f"Запрос: {req_type}\n"
        f"Данные: {req_data[:100]}...\n\n"
        f"Напишите результат поиска:"
    )
    await cb.answer()

@dp.message(AdminStates.waiting_for_search_answer)
async def send_search_answer(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        await state.clear()
        return
    
    data = await state.get_data()
    request_id = data.get("search_request_id")
    user_id = data.get("search_user_id")
    answer_text = message.text
    
    # Обновляем статус заявки в БД
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        UPDATE search_requests 
        SET status='answered', answered_by=?, answered_at=?, answer_text=?
        WHERE id=?
    """, (message.from_user.id, datetime.now(timezone.utc).isoformat(), answer_text, request_id))
    conn.commit()
    conn.close()
    
    # Отправляем ответ пользователю
    try:
        await bot.send_message(
            user_id,
            f"🔍 <b>РЕЗУЛЬТАТ ПОИСКА</b>\n\n"
            f"По вашему запросу найден результат:\n\n"
            f"{answer_text}\n\n"
            f"Спасибо за обращение!"
        )
        await message.answer("✅ Ответ отправлен пользователю")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки пользователю: {e}")
    
    await state.clear()

# ----------------- АДМИН: ПРОСМОТР ЗАЯВОК НА ПОИСК -----------------
@dp.callback_query(F.data == "admin_search_requests")
async def admin_search_requests(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, request_type, data, status, created_at 
        FROM search_requests 
        WHERE status='pending'
        ORDER BY created_at DESC
        LIMIT 10
    """)
    requests = cur.fetchall()
    conn.close()
    
    if not requests:
        await cb.message.edit_text(
            "📭 Нет ожидающих заявок на поиск",
            reply_markup=admin_menu()
        )
        await cb.answer()
        return
    
    text = "🔍 <b>Ожидающие заявки на поиск:</b>\n\n"
    for req in requests:
        req_id, user_id, req_type, data, status, created = req
        text += f"ID: {req_id} | {req_type} | От: {user_id}\n"
        text += f"📄 {data[:50]}...\n"
        text += f"🕐 {created[:19]}\n\n"
    
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()

# ----------------- АДМИН ПАНЕЛЬ -----------------
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    
    text = "👑 <b>Панель администратора</b>\n\nВыберите действие:"
    await message.answer(text, reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    stats = get_stats()
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"📝 Всего постов: <b>{stats['total_posts']}</b>\n"
        f"✅ Одобрено: <b>{stats['approved_posts']}</b>\n"
        f"⏳ В очереди: <b>{stats['pending_posts']}</b>\n"
        f"💰 Всего Coins в обороте: <b>{stats['total_coins']}</b>\n"
        f"💳 Продано Coins: <b>{stats['coins_sold']}</b>\n"
        f"🔄 Всего оплат: <b>{stats['total_payments']}</b>\n"
        f"🔍 Заявок на поиск: <b>{stats['total_searches']}</b>\n"
        f"⏳ Ожидают ответа: <b>{stats['pending_searches']}</b>"
    )
    
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()

# ----------------- АДМИН: ВЫДАТЬ/ЗАБРАТЬ COINS -----------------
@dp.callback_query(F.data == "admin_add_coins")
async def admin_add_coins(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(operation="add")
    await cb.message.edit_text(
        "💰 Введите ID пользователя, которому хотите выдать Coins:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
    )
    await cb.answer()

@dp.callback_query(F.data == "admin_remove_coins")
async def admin_remove_coins(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(operation="remove")
    await cb.message.edit_text(
        "💸 Введите ID пользователя, у которого хотите забрать Coins:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
    )
    await cb.answer()

@dp.message(AdminStates.waiting_for_user_id)
async def admin_process_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        await state.clear()
        return
    
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите корректный ID (только цифры)")
        return
    
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT id, username, balance FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        await message.answer("❌ Пользователь с таким ID не найден в базе")
        await state.clear()
        return
    
    data = await state.get_data()
    operation = data.get("operation")
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_coin_amount)
    
    username = user[1] or "без username"
    balance = user[2]
    
    if operation == "add":
        await message.answer(
            f"💰 Пользователь: ID {user_id} (@{username})\n"
            f"Текущий баланс: {balance} Coins\n\n"
            f"Введите количество Coins для добавления:"
        )
    else:
        await message.answer(
            f"💸 Пользователь: ID {user_id} (@{username})\n"
            f"Текущий баланс: {balance} Coins\n\n"
            f"Введите количество Coins для списания:"
        )

@dp.message(AdminStates.waiting_for_coin_amount)
async def admin_process_coin_amount(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        await state.clear()
        return
    
    try:
        amount = int(message.text.strip())
    except:
        await message.answer("❌ Введите число")
        return
    
    if amount <= 0:
        await message.answer("❌ Число должно быть больше 0")
        return
    
    data = await state.get_data()
    user_id = data.get("target_user_id")
    operation = data.get("operation")
    
    if operation == "add":
        update_balance(user_id, amount)
        await message.answer(f"✅ Пользователю ID {user_id} добавлено {amount} Coins")
        try:
            await bot.send_message(user_id, f"💰 Вам начислено {amount} Coins администратором.")
        except:
            pass
    else:
        bal = get_balance(user_id)
        if bal < amount:
            await message.answer(f"❌ У пользователя недостаточно средств. Баланс: {bal} Coins")
            await state.clear()
            return
        update_balance(user_id, -amount)
        await message.answer(f"✅ У пользователя ID {user_id} списано {amount} Coins")
        try:
            await bot.send_message(user_id, f"💸 У вас списано {amount} Coins администратором.")
        except:
            pass
    
    await message.answer("👑 Возврат в админ-панель", reply_markup=admin_menu())
    await state.clear()

# ----------------- АДМИН: РАССЫЛКА -----------------
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await cb.message.edit_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправьте текст для рассылки.\n"
        "Можно также прикрепить фото (одно) к сообщению.\n\n"
        "После отправки сообщения с текстом (и опционально фото), "
        "рассылка будет запущена всем пользователям бота.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
    )
    await cb.answer()

@dp.message(AdminStates.waiting_for_broadcast_text, F.content_type.in_([ContentType.TEXT, ContentType.PHOTO]))
async def admin_process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        await state.clear()
        return
    
    text = message.caption or message.text or ""
    photo_id = message.photo[-1].file_id if message.photo else None
    
    users = get_all_users()
    
    if not users:
        await message.answer("❌ Нет пользователей для рассылки")
        await state.clear()
        return
    
    await message.answer(
        f"📢 Начинаю рассылку {len(users)} пользователям...\n"
        f"Текст: {text[:100]}...\n"
        f"{'С фото' if photo_id else 'Без фото'}\n\n"
        f"Это может занять некоторое время."
    )
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            if photo_id:
                await bot.send_photo(user_id, photo_id, caption=text)
            else:
                await bot.send_message(user_id, text)
            success += 1
        except Exception as e:
            failed += 1
            print(f"Ошибка отправки пользователю {user_id}: {e}")
        
        await asyncio.sleep(0.05)
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📊 Статистика:\n"
        f"✅ Успешно: {success}\n"
        f"❌ Не удалось: {failed}"
    )
    
    await message.answer("👑 Возврат в админ-панель", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_back")
async def admin_back(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.clear()
    await cb.message.edit_text(
        "👑 <b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=admin_menu()
    )
    await cb.answer()

# ----------------- МЕНЮ НАЗАД / ПОСТ -----------------
@dp.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.message.edit_text(
        "👋 Главное меню. Выберите действие 👇",
        reply_markup=main_menu()
    )
    await cb.answer()

@dp.callback_query(F.data == "menu_post")
async def menu_post(cb: CallbackQuery):
    await cb.message.edit_text("📝 Как вы хотите опубликовать пост?", reply_markup=post_choice_menu())
    await cb.answer()

# ----------------- СОЗДАНИЕ ПОСТА -----------------
@dp.callback_query(F.data.in_(["post_self", "post_anon"]))
async def post_create(cb: CallbackQuery, state: FSMContext):
    anon = 1 if cb.data == "post_anon" else 0

    register_user(cb.from_user.id, cb.from_user.username)

    await state.update_data(anon=anon)
    await state.set_state(PostState.waiting_for_post)
    await cb.message.edit_text("✍️ Отправьте текст и/или медиа для поста. (Можно одно фото/видео и подпись)",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                   [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_post")]
                               ]))
    await cb.answer()

@dp.message(PostState.waiting_for_post, F.content_type.in_([ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO]))
async def handle_post(message: Message, state: FSMContext):
    data = await state.get_data()
    anon = data.get("anon", 0)
    created = datetime.now(timezone.utc).isoformat()

    text = message.caption or message.text or ""
    media_type = None
    media_id = None

    if message.photo:
        media_type = "photo"
        media_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_id = message.video.file_id

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO posts (user_id, text, anon, status, media_type, media_ids, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message.from_user.id, text, anon, "pending", media_type, media_id, created)
    )
    post_id = cur.lastrowid
    conn.commit()
    conn.close()

    await message.answer(
        "✅ Ваш пост отправлен на модерацию. После одобрения он появится в канале.",
        reply_markup=main_menu()
    )
    await state.clear()

    username = message.from_user.username
    pretty_user = f"@{username}" if username else str(message.from_user.id)
    caption_header = f"📢 Новый пост (ID {post_id})\nОт: {pretty_user}\nАноним: {'Да' if anon else 'Нет'}"
    for admin in ADMIN_IDS:
        try:
            if media_type == "photo":
                await bot.send_photo(admin, media_id, caption=f"{caption_header}\n\n{text}", reply_markup=moderation_markup(post_id))
            elif media_type == "video":
                await bot.send_video(admin, media_id, caption=f"{caption_header}\n\n{text}", reply_markup=moderation_markup(post_id))
            else:
                await bot.send_message(admin, f"{caption_header}\n\n{text}", reply_markup=moderation_markup(post_id))
        except Exception:
            pass

# ----------------- МОДЕРАЦИЯ ПОСТОВ -----------------
@dp.callback_query(F.data.startswith("moderate_approve_"))
async def moderate_approve(cb: CallbackQuery):
    post_id = int(cb.data.split("_")[-1])
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, text, anon, media_type, media_ids, status FROM posts WHERE id=?", (post_id,))
    post = cur.fetchone()
    if not post:
        await cb.answer("Пост не найден.", show_alert=True)
        conn.close()
        return

    user_id, text, anon, media_type, media_id, status = post
    if status != "pending":
        await cb.answer("Этот пост уже обработан.", show_alert=True)
        conn.close()
        return

    username = get_username_from_db(user_id)
    if username:
        author_text = f"👤 @{username}\n\n"
    else:
        author_text = f"👤 <a href='tg://user?id={user_id}'>пользователь</a>\n\n"

    if anon:
        channel_text = text or ""
    else:
        channel_text = author_text + (text or "")

    try:
        if media_type == "photo":
            await bot.send_photo(CHANNEL_ID, media_id, caption=channel_text)
        elif media_type == "video":
            await bot.send_video(CHANNEL_ID, media_id, caption=channel_text)
        else:
            await bot.send_message(CHANNEL_ID, channel_text)
    except Exception:
        await cb.answer("Ошибка при публикации в канал.", show_alert=True)
        conn.close()
        return

    # Начисляем 1 Coin за одобренный пост
    update_balance(user_id, 1)

    cur.execute("UPDATE posts SET status='approved', moderated_by=?, moderated_at=? WHERE id=?", 
                (cb.from_user.id, datetime.now(timezone.utc).isoformat(), post_id))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(user_id, "✅ Ваш пост одобрен и опубликован в канале!\n💰 +1 Coin начислен за публикацию.")
    except:
        pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await cb.answer("Пост опубликован ✅ +1 Coin автору")

@dp.callback_query(F.data.startswith("moderate_reject_"))
async def moderate_reject(cb: CallbackQuery):
    post_id = int(cb.data.split("_")[-1])
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, status FROM posts WHERE id=?", (post_id,))
    post = cur.fetchone()
    if not post:
        await cb.answer("Пост не найден.", show_alert=True)
        conn.close()
        return

    user_id, status = post
    if status != "pending":
        await cb.answer("Этот пост уже обработан.", show_alert=True)
        conn.close()
        return

    cur.execute("UPDATE posts SET status='rejected', moderated_by=?, moderated_at=? WHERE id=?", 
                (cb.from_user.id, datetime.now(timezone.utc).isoformat(), post_id))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(user_id, "❌ Ваш пост отклонён модератором.")
    except:
        pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await cb.answer("Пост отклонён ❌")

# ----------------- УДАЛЕНИЕ ПОСТА (ЗА 5 COINS) -----------------
@dp.callback_query(F.data == "post_delete")
async def post_delete_start(cb: CallbackQuery, state: FSMContext):
    register_user(cb.from_user.id, cb.from_user.username)
    bal = get_balance(cb.from_user.id)
    cost = 5
    if bal < cost:
        await cb.message.edit_text(
            f"⚠️ У вас недостаточно средств для подачи заявки на удаление.\n\nБаланс: {bal} Coins\nНе хватает: {cost - bal} Coins",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_post")]])
        )
        await cb.answer()
        return

    await state.set_state(DeletePostState.waiting_for_info)
    await cb.message.edit_text(
        "🗑 Отправьте ссылку на пост или скриншот поста, который хотите удалить.\n\n"
        "После отправки заявка пойдёт администраторам. Оплата (5 Coins) будет списана только после подтверждения админом.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_post")]
        ])
    )
    await cb.answer()

@dp.message(DeletePostState.waiting_for_info, F.content_type.in_([ContentType.TEXT, ContentType.PHOTO]))
async def handle_delete_request(message: Message, state: FSMContext):
    register_user(message.from_user.id, message.from_user.username)
    text = message.text or ""
    screenshot = message.photo[-1].file_id if message.photo else None
    created = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO delete_requests (user_id, message, screenshot, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (message.from_user.id, text, screenshot, "pending", created))
    rid = cur.lastrowid
    conn.commit()
    conn.close()

    await message.answer(
        "✅ Ваша заявка на удаление отправлена администраторам. Ожидайте проверки.",
        reply_markup=main_menu()
    )
    await state.clear()

    username = message.from_user.username
    pretty_user = f"@{username}" if username else str(message.from_user.id)
    caption = (
        f"🗑 <b>Заявка на удаление поста</b>\n\n"
        f"👤 Пользователь: {pretty_user}\n"
        f"🆔 ID заявки: {rid}\n\n"
        f"{text}\n\n"
        "Пожалуйста, вручную удалите пост в канале, затем нажмите ✅ чтобы подтвердить удаление и списать 5 Coins, "
        "или ❌ чтобы отклонить заявку."
    )
    for admin in ADMIN_IDS:
        try:
            if screenshot:
                await bot.send_photo(admin, screenshot, caption=caption, reply_markup=delete_request_admin_markup(rid))
            else:
                await bot.send_message(admin, caption, reply_markup=delete_request_admin_markup(rid))
        except:
            pass

@dp.callback_query(F.data.startswith("del_approve_"))
async def approve_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("У вас нет прав.", show_alert=True)
        return

    rid = int(cb.data.split("_")[-1])
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, status FROM delete_requests WHERE id=?", (rid,))
    row = cur.fetchone()
    if not row:
        await cb.answer("Заявка не найдена.", show_alert=True)
        conn.close()
        return
    user_id, status = row
    if status != "pending":
        await cb.answer("Заявка уже обработана.", show_alert=True)
        conn.close()
        return

    bal = get_balance(user_id)
    cost = 5
    if bal < cost:
        cur.execute("UPDATE delete_requests SET status='rejected' WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        try:
            await bot.send_message(user_id, f"❌ Не удалось удалить пост — у вас недостаточно средств (нужно {cost} Coins).")
        except:
            pass
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except:
            pass
        await cb.answer("Пользователь не имеет достаточного баланса — заявка отклонена.")
        return

    update_balance(user_id, -cost)
    cur.execute("UPDATE delete_requests SET status='approved' WHERE id=?", (rid,))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(user_id, "✅ Ваша заявка на удаление поста одобрена. С вас списано 5 Coins.")
    except:
        pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await cb.answer("Заявка на удаление одобрена ✅")

@dp.callback_query(F.data.startswith("del_reject_"))
async def reject_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("У вас нет прав.", show_alert=True)
        return

    rid = int(cb.data.split("_")[-1])
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, status FROM delete_requests WHERE id=?", (rid,))
    row = cur.fetchone()
    if not row:
        await cb.answer("Заявка не найдена.", show_alert=True)
        conn.close()
        return
    user_id, status = row
    if status != "pending":
        await cb.answer("Заявка уже обработана.", show_alert=True)
        conn.close()
        return

    cur.execute("UPDATE delete_requests SET status='rejected' WHERE id=?", (rid,))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(user_id, "❌ Ваша заявка на удаление поста отклонена.")
    except:
        pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await cb.answer("Заявка отклонена ❌")

# ----------------- НОВАЯ ФУНКЦИЯ: ЗАРАБОТАТЬ COINS -----------------
@dp.callback_query(F.data == "balance_earn")
async def balance_earn(cb: CallbackQuery):
    text = (
        "💰 <b>КАК ЗАРАБОТАТЬ COINS</b>\n\n"
        "✨ <b>Самый простой способ:</b>\n"
        "📝 <b>Предлагайте свои посты в канал!</b>\n\n"
        "🔹 <b>Как это работает:</b>\n"
        "1. Нажмите «Предложить пост» в главном меню\n"
        "2. Отправьте пост (текст, фото, видео)\n"
        "3. Если администратор одобрит ваш пост\n"
        "4. Вы получаете <b>+1 Coin</b> на баланс!\n\n"
        "🔹 <b>Преимущества:</b>\n"
        "• Ваш пост увидит вся аудитория канала\n"
        "• Вы зарабатываете Coins\n"
        "• Можно копить на платные услуги\n\n"
        "⬇️ <b>Начните зарабатывать прямо сейчас!</b>"
    )
    
    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Предложить пост", callback_data="menu_post")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_balance")]
        ])
    )
    await cb.answer()

# ----------------- БАЛАНС / ПОКУПКА COINS -----------------
@dp.callback_query(F.data == "menu_balance")
async def menu_balance(cb: CallbackQuery):
    register_user(cb.from_user.id, cb.from_user.username)
    bal = get_balance(cb.from_user.id)
    text = f"💎 Ваш баланс: <b>{bal} Coins</b>"
    await cb.message.edit_text(text, reply_markup=balance_menu())
    await cb.answer()

@dp.callback_query(F.data == "balance_buy")
async def balance_buy(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("Введите количество Coins для покупки (1 Coin = 50 ₽, максимум 100):")
    await state.set_state(BuyCoinsState.waiting_for_amount)
    await cb.answer()

@dp.message(BuyCoinsState.waiting_for_amount)
async def handle_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except:
        return await message.answer("Введите число от 1 до 100.")

    if amount < 1 or amount > 100:
        return await message.answer("⚠️ Можно купить от 1 до 100 Coins.")

    price = amount * 50
    await state.update_data(amount_coins=amount, price=price)
    await state.set_state(BuyCoinsState.waiting_for_screenshot)

    await message.answer(
        f"💳 <b>Оплата</b>\n\n"
        f"Сумма: <b>{price} ₽</b>\n"
        f"Количество: <b>{amount} Coins</b>\n\n"
        f"Переведите деньги на карту:\n<code>{BANK_CARD}</code> — {BANK_NAME}\n"
        "В комментарии укажите свой @username или ID.\n\n"
        "📸 После перевода отправьте скриншот сюда."
    )

@dp.message(BuyCoinsState.waiting_for_screenshot, F.photo)
async def handle_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount_coins", 0)
    price = data.get("price", 0)
    screenshot_id = message.photo[-1].file_id
    created = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, amount_coins, price, status, screenshot, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (message.from_user.id, amount, price, "pending", screenshot_id, created)
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()

    await message.answer(
        "✅ Ваш запрос принят на проверку. Ожидайте подтверждения администратора.",
        reply_markup=main_menu()
    )
    await state.clear()

    markup = payment_admin_markup(pid)
    username = message.from_user.username
    pretty_user = f"@{username}" if username else str(message.from_user.id)
    caption = (
        f"💰 <b>Новый платёж</b>\n\n"
        f"👤 Пользователь: {pretty_user}\n"
        f"💎 Coins: {amount}\n"
        f"💳 Сумма: {price} ₽\n"
        f"🆔 ID платежа: {pid}\n\n"
        f"Нажмите ✅ чтобы подтвердить и зачислить Coins, или ❌ чтобы отклонить."
    )
    for admin in ADMIN_IDS:
        try:
            await bot.send_photo(admin, screenshot_id, caption=caption, reply_markup=markup)
        except:
            try:
                await bot.send_message(admin, caption, reply_markup=markup)
            except:
                pass

@dp.callback_query(F.data.startswith("payment_approve_"))
async def payment_approve(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return

    pid = int(cb.data.split("_")[-1])
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, amount_coins, status FROM payments WHERE id=?", (pid,))
    payment = cur.fetchone()
    if not payment:
        await cb.answer("Платёж не найден.", show_alert=True)
        conn.close()
        return

    user_id, amount, status = payment
    if status != "pending":
        await cb.answer("Этот платёж уже обработан.", show_alert=True)
        conn.close()
        return

    update_balance(user_id, amount)
    cur.execute("UPDATE payments SET status='approved', moderated_by=?, moderated_at=? WHERE id=?", 
                (cb.from_user.id, datetime.now(timezone.utc).isoformat(), pid))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(user_id, f"✅ Ваш платёж подтвержден! Вам зачислено {amount} Coins.")
    except:
        pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await cb.answer("Платёж подтверждён ✅")

@dp.callback_query(F.data.startswith("payment_reject_"))
async def payment_reject(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return

    pid = int(cb.data.split("_")[-1])
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, status FROM payments WHERE id=?", (pid,))
    payment = cur.fetchone()
    if not payment:
        await cb.answer("Платёж не найден.", show_alert=True)
        conn.close()
        return

    user_id, status = payment
    if status != "pending":
        await cb.answer("Этот платёж уже обработан.", show_alert=True)
        conn.close()
        return

    cur.execute("UPDATE payments SET status='rejected', moderated_by=?, moderated_at=? WHERE id=?", 
                (cb.from_user.id, datetime.now(timezone.utc).isoformat(), pid))
    conn.commit()
    conn.close()

    try:
        await bot.send_message(user_id, "❌ Ваш запрос отклонен.")
    except:
        pass

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    await cb.answer("Платёж отклонён ❌")

# ----------------- ВОПРОСЫ -----------------
@dp.callback_query(F.data == "help_question")
async def help_question(cb: CallbackQuery, state: FSMContext):
    await state.set_state(QuestionState.waiting_for_question)
    await cb.message.edit_text(
        "💬 <b>ЗАДАТЬ ВОПРОС</b>\n\n"
        "Напишите ваш вопрос — администратор ответит вам лично.\n\n"
        "✍️ Введите ваш вопрос:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ])
    )
    await cb.answer()

@dp.message(QuestionState.waiting_for_question)
async def send_question(message: Message, state: FSMContext):
    register_user(message.from_user.id, message.from_user.username)
    text = f"📩 Вопрос от @{message.from_user.username or message.from_user.id}:\n\n{message.text}"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ответить пользователю", callback_data=f"answer_question_{message.from_user.id}")]
            ]))
        except:
            pass
    
    await message.answer(
        "✅ Ваш вопрос отправлен администратору.\n\nОжидайте ответа в этом чате.",
        reply_markup=main_menu()
    )
    await state.clear()

@dp.callback_query(F.data.startswith("answer_question_"))
async def answer_question(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("❌ Нет доступа", show_alert=True)
        return
    
    user_id = int(cb.data.split("_")[-1])
    await state.update_data(reply_to_user=user_id)
    await state.set_state(QuestionState.waiting_for_answer)
    
    await cb.message.answer(f"💬 Введите ответ пользователю (ID {user_id}):")
    await cb.answer()

@dp.message(QuestionState.waiting_for_answer)
async def send_answer_to_user(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        await state.clear()
        return
    
    data = await state.get_data()
    user_id = data.get("reply_to_user")
    if not user_id:
        await message.answer("❌ Не удалось определить пользователя.")
        await state.clear()
        return

    try:
        await bot.send_message(
            user_id,
            f"💬 <b>Ответ от администратора:</b>\n\n{message.text}"
        )
        await message.answer("✅ Ответ отправлен пользователю.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение пользователю: {e}")
    
    await state.clear()

# ----------------- АДМИН: /addcoin -----------------
@dp.message(Command("addcoin"))
async def add_coin_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ У вас нет прав на выполнение этой команды.")
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])
    except (IndexError, ValueError):
        return await message.answer("Использование: /addcoin <user_id> <amount>")

    update_balance(user_id, amount)
    await message.answer(f"✅ Пользователю {user_id} добавлено {amount} Coins.")
    try:
        await bot.send_message(user_id, f"💰 Вам начислено {amount} Coins администратором.")
    except:
        pass

# ----------------- ЗАПУСК -----------------
async def main():
    init_db()
    print("🤖 Бот запущен.")
    print("👑 Админ-панель: /admin")
    print("💰 За одобренный пост начисляется 1 Coin")
    print(f"🔍 Поиск людей: {SEARCH_COST} Coins")
    print("✅ Кнопки всегда активны, /start не нужен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

