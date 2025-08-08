import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, Contact,
    KeyboardButton, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties  # << BU YANGI QATOR
import aiosqlite
from datetime import datetime

TOKEN = "8410400629:AAG9pnnFjcba7RkdmMVqOp8MhFVysLdC6rw"  # ← bu yerga o'z bot tokeningizni qo'ying

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

DB_NAME = "users.db"
ADMIN_ID = 8152258436  # ← bu yerga o'zingizning Telegram ID raqamingizni qo'ying

# === HOLATLAR ===
class RegisterState(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()

class AdminState(StatesGroup):
    in_admin = State()


# === BAZA ISHLARI ===
async def create_tables():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                name TEXT,
                phone TEXT,
                reg_date TEXT
            )
        """)
        await db.commit()

async def get_user_by_telegram_id(telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return await cursor.fetchone()

async def get_next_user_id():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT MAX(id) FROM users")
        max_id = await cursor.fetchone()
        return (max_id[0] or 0) + 1

async def add_user(telegram_id, username, name, phone):
    reg_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, username, name, phone, reg_date)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, username, name, phone, reg_date))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users")
        return await cursor.fetchall()


# === KLAVIATURALAR ===

def user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Premium bo‘limi"), KeyboardButton(text="Stars bo‘limi")],
            [KeyboardButton(text="Hisobim"), KeyboardButton(text="Pul kiritish")],
            [KeyboardButton(text="Qo‘llab-quvvatlash")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Statistika"), KeyboardButton(text="Foydalanuvchilar ro'yxati")],
            [KeyboardButton(text="Pul to‘ldirish"), KeyboardButton(text="Pul yechish")],
            [KeyboardButton(text="Kanal ulash"), KeyboardButton(text="Chiqish")]
        ],
        resize_keyboard=True
    )


# === FOYDALANUVCHI /start ===
@router.message(CommandStart())
async def start_handler(msg: Message, state: FSMContext):
    user = await get_user_by_telegram_id(msg.from_user.id)
    if user:
        await msg.answer(f"👋 <b>Bo'timizga qaytganingizdan xursandmiz, {user[3]}!</b>", reply_markup=user_menu())
    else:
        await msg.answer("👋 Salom! Ismingizni kiriting:")
        await state.set_state(RegisterState.waiting_for_name)

@router.message(RegisterState.waiting_for_name)
async def get_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    contact_button = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Kontaktni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await msg.answer("📞 Telefon raqamingizni yuboring:", reply_markup=contact_button)
    await state.set_state(RegisterState.waiting_for_contact)

@router.message(RegisterState.waiting_for_contact, F.contact)
async def get_contact(msg: Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    phone = msg.contact.phone_number
    username = msg.from_user.username or "yo‘q"
    telegram_id = msg.from_user.id

    await add_user(telegram_id, username, name, phone)
    user_id = await get_user_by_telegram_id(telegram_id)

    await msg.answer(
        f"✅ Ro‘yxatdan o‘tdingiz!\n🆔 Sizning ID: <b>{user_id[0]}</b>",
        reply_markup=user_menu()
    )
    await state.clear()


# === ADMIN PANEL ===
@router.message(Command("rawidovich"))
async def enter_admin(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("❌ Siz admin emassiz.")
        return
    await state.set_state(AdminState.in_admin)
    await msg.answer(f"👑 Admin panelga xush kelibsiz, {msg.from_user.first_name}!", reply_markup=admin_menu())

@router.message(AdminState.in_admin, F.text == "Chiqish")
async def admin_exit(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("👋 Oddiy foydalanuvchi paneliga qaytdingiz.", reply_markup=user_menu())

@router.message(AdminState.in_admin, F.text == "Statistika")
async def admin_stats(msg: Message):
    users = await get_all_users()
    await msg.answer(f"📊 Bot foydalanuvchilari soni: <b>{len(users)}</b>")

@router.message(AdminState.in_admin, F.text == "Foydalanuvchilar ro'yxati")
async def list_users(msg: Message):
    users = await get_all_users()
    text = "👥 Foydalanuvchilar:\n\n"
    for user in users:
        text += f"{user[0]}. {user[3]} | @{user[2]} | {user[4]}\n"
    await msg.answer(text if users else "Foydalanuvchi topilmadi.")


# === BOSHLASH ===
dp.include_router(router)

async def main():
    await create_tables()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
