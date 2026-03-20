import asyncio
import logging
import datetime
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp_socks import ProxyConnector

# --- [ КОНФИГ SteasHub ] ---
TOKEN = os.getenv("BOT_TOKEN", "8406451825:AAHC7BXCcUMjagrhisEsND9H0h6EU6V2ZfI")
PROXY_URL = os.getenv("PROXY_URL", "socks5://127.0.0.1:10808")

# Данные тарифов
PLANS = {
    "personal": {
        "name": "💎 Personal",
        "price": 150,
        "devices": 3,
        "speed": "до 1 Гбит/с",
        "locations": "🇳🇱 NL, 🇦🇹 AT, 🇷🇴 RO, 🇫🇮 FI, 🇸🇬 SG",
        "desc": "Идеально для 4K контента, игр и соцсетей без задержек."
    },
    "family": {
        "name": "👨‍👩‍👧‍👦 Family (Групповой)",
        "price": 400,
        "devices": 8,
        "speed": "до 25 Гбит/с",
        "locations": "🚀 Все локации + Приоритетный канал",
        "desc": "Максимальная мощность для всей семьи или компании друзей. Автономное управление подпиской."
    }
}

# --- [ ИНИЦИАЛИЗАЦИЯ ] ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SteasHub_Bot")


async def main():
    # Настройка пробивного соединения через прокси (опционально)
    # Если прокси не нужен (Railway), создаем обычную сессию
    if PROXY_URL and PROXY_URL != "":
        try:
            connector = ProxyConnector.from_url(PROXY_URL)
            session = AiohttpSession(connector=connector)
            logger.info(f"✅ Подключение через прокси: {PROXY_URL}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться через прокси: {e}. Используем прямое соединение.")
            session = AiohttpSession()
    else:
        session = AiohttpSession()
        logger.info("✅ Прямое соединение (без прокси)")
    
    bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # --- [ ЛОГИКА И ОБРАБОТЧИКИ ] ---

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        user = message.from_user
        logger.info(f"👤 НОВЫЙ ЮЗЕР: {user.full_name} (@{user.username}) [ID: {user.id}]")
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🚀 Выбрать тариф", callback_data="plans"))
        builder.row(types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"))
        builder.row(types.InlineKeyboardButton(text="🛠 Поддержка", url="https://t.me/your_admin_link"))

        welcome_text = (
            f"<b>🔥 SteasHub | VPN — Свобода без границ</b>\n\n"
            f"Привет, <b>{user.first_name}</b>! Ты на связи с самым быстрым VPN на протоколе <b>VLESS + Reality</b>.\n\n"
            f"⚡️ Скорость: до <b>25 Гбит/с</b>\n"
            f"🌍 Локации: Вена, Сингапур, Амстердам и др.\n"
            f"🔞 Полный доступ ко всем ресурсам 24/7\n\n"
            f"<i>Выбирай тариф и летай на сверхзвуке!</i>"
        )
        await message.answer(welcome_text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "plans")
    async def show_plans(callback: types.CallbackQuery):
        logger.info(f"🖱 Юзер @{callback.from_user.username} смотрит тарифы")
        builder = InlineKeyboardBuilder()
        for key, data in PLANS.items():
            builder.row(types.InlineKeyboardButton(
                text=f"{data['name']} — {data['price']}₽", 
                callback_data=f"buy_{key}"
            ))
        builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_home"))
        
        await callback.message.edit_text(
            "<b>📊 Доступные тарифы SteasHub:</b>\n\n"
            "Выбери подходящий план. Доступ предоставляется мгновенно после оплаты.",
            reply_markup=builder.as_markup()
        )

    @dp.callback_query(F.data.startswith("buy_"))
    async def plan_details(callback: types.CallbackQuery):
        plan_id = callback.data.split("_")[1]
        plan = PLANS[plan_id]
        logger.info(f"🛒 Юзер @{callback.from_user.username} выбрал тариф {plan['name']}")
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="💳 Оплатить (СБП/Карта)", callback_data="pay_stub"))
        builder.row(types.InlineKeyboardButton(text="⬅️ К тарифам", callback_data="plans"))
        
        detail_text = (
            f"<b>Тариф: {plan['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Стоимость: <b>{plan['price']} руб/мес</b>\n"
            f"📱 Устройств: <b>{plan['devices']}</b>\n"
            f"⚡️ Скорость: <b>{plan['speed']}</b>\n"
            f"🌍 Локации: <code>{plan['locations']}</code>\n\n"
            f"📝 <i>{plan['desc']}</i>"
        )
        await callback.message.edit_text(detail_text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "pay_stub")
    async def pay_stub(callback: types.CallbackQuery):
        logger.warning(f"⚠️ Юзер @{callback.from_user.username} пытался оплатить (модуль в разработке)")
        await callback.answer(
            "🛠 Платежный шлюз SteasHub на техобслуживании.\nАвтоматическая оплата будет доступна в версии 1.1!", 
            show_alert=True
        )

    @dp.callback_query(F.data == "back_home")
    async def back_home(callback: types.CallbackQuery):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🚀 Выбрать тариф", callback_data="plans"))
        builder.row(types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"))
        await callback.message.edit_text("<b>Главное меню SteasHub | VPN</b>", reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "profile")
    async def profile_stub(callback: types.CallbackQuery):
        await callback.answer("⚙️ Личный кабинет в разработке.", show_alert=True)

    # Запуск
    print("\n" + "="*40)
    print("🚀 SteasHub | VPN БОТ УСПЕШНО ЗАПУЩЕН!")
    print(f"📡 Соединение: {PROXY_URL if PROXY_URL else 'Прямое (без прокси)'}")
    print(f"⏰ Время запуска: {datetime.datetime.now().strftime('%H:%M:%S')}")
    print("="*40 + "\n")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен вручную")
