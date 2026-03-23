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

# Импорт модулей
import database as db
import vless_keys as vless

# --- [ КОНФИГ SteasHub ] ---
TOKEN = os.getenv("BOT_TOKEN", "8406451825:AAHC7BXCcUMjagrhisEsND9H0h6EU6V2ZfI")
PROXY_URL = os.getenv("PROXY_URL", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

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

# Регионы серверов для репортов
SERVER_REGIONS = {
    "nl": "🇳🇱 Нидерланды",
    "at": "🇦🇹 Австрия",
    "ro": "🇷🇴 Румыния",
    "fi": "🇫🇮 Финляндия",
    "sg": "🇸🇬 Сингапур"
}

# Типы проблем для репортов
ISSUE_TYPES = {
    "no_connect": "❌ Не подключается",
    "low_speed": "🐌 Низкая скорость",
    "high_ping": "⏱ Высокий пинг",
    "disconnect": "📡 Постоянные обрывы",
    "other": "🔧 Другое"
}

# --- [ ИНИЦИАЛИЗАЦИЯ ] ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SteasHub_Bot")


async def main():
    # Инициализация БД
    db.init_db()
    logger.info("✅ База данных инициализирована")
    
    # Инициализация менеджера ключей
    await vless.init_keys_manager()
    
    # Запуск фоновой задачи автообновления ключей
    asyncio.create_task(vless.scheduled_keys_update())
    logger.info("✅ Запланировано автообновление ключей (каждый день в 00:00)")
    
    # Настройка пробивного соединения через прокси (опционально)
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

    # --- [ КЛАВИАТУРЫ ] ---

    def get_main_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🚀 Пробная версия VPN (Бесплатно)", callback_data="start_trial_vpn"))
        builder.row(types.InlineKeyboardButton(text="🌐 Обычный интернет (без белых списков)", callback_data="blacklist_vpn"))
        builder.row(types.InlineKeyboardButton(text="💎 Выбрать тариф", callback_data="plans"))
        builder.row(types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"))
        builder.row(types.InlineKeyboardButton(text="🛠 Поддержка", url="https://t.me/your_admin_link"))
        return builder.as_markup()
    
    def get_plans_keyboard():
        builder = InlineKeyboardBuilder()
        for key, data in PLANS.items():
            builder.row(types.InlineKeyboardButton(
                text=f"{data['name']} — {data['price']}₽",
                callback_data=f"buy_{key}"
            ))
        builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_home"))
        return builder.as_markup()
    
    def get_plan_detail_keyboard(plan_id: str):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="💳 Оплатить (СБП/Карта)", callback_data="pay_stub"))
        builder.row(types.InlineKeyboardButton(text="⬅️ К тарифам", callback_data="plans"))
        return builder.as_markup()
    
    def get_admin_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
        builder.row(types.InlineKeyboardButton(text="💰 Доходы", callback_data="admin_revenue"))
        builder.row(types.InlineKeyboardButton(text="👥 Подписчики", callback_data="admin_subscribers"))
        builder.row(types.InlineKeyboardButton(text="⚠️ Репорты серверов", callback_data="admin_reports"))
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_home"))
        return builder.as_markup()
    
    def get_stats_period_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="1 день", callback_data="revenue_day"),
            types.InlineKeyboardButton(text="Неделя", callback_data="revenue_week")
        )
        builder.row(
            types.InlineKeyboardButton(text="Месяц", callback_data="revenue_month"),
            types.InlineKeyboardButton(text="Год", callback_data="revenue_year")
        )
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu"))
        return builder.as_markup()
    
    def get_report_region_keyboard():
        builder = InlineKeyboardBuilder()
        for code, name in SERVER_REGIONS.items():
            builder.row(types.InlineKeyboardButton(text=name, callback_data=f"report_region_{code}"))
        builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="back_profile"))
        return builder.as_markup()
    
    def get_report_issue_keyboard(region_code: str):
        builder = InlineKeyboardBuilder()
        for code, name in ISSUE_TYPES.items():
            builder.row(types.InlineKeyboardButton(text=name, callback_data=f"report_issue_{region_code}_{code}"))
        builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="back_profile"))
        return builder.as_markup()
    
    def get_profile_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📡 Сообщить о проблеме", callback_data="report_server"))
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_home"))
        return builder.as_markup()

    # --- [ ЛОГИКА И ОБРАБОТЧИКИ ] ---

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        user = message.from_user
        logger.info(f"👤 НОВЫЙ ЮЗЕР: {user.full_name} (@{user.username}) [ID: {user.id}]")
        
        # Сохраняем пользователя в БД
        db.add_user(user.id, user.username or "", user.first_name, user.last_name)
        
        # Если это админ - добавляем кнопку админки
        if user.id in ADMIN_IDS:
            db.set_admin(user.id, True)
        
        welcome_text = (
            f"<b>🔥 SteasHub | VPN — Свобода без границ</b>\n\n"
            f"Привет, <b>{user.first_name}</b>! Ты на связи с самым быстрым VPN на протоколе <b>VLESS + Reality</b>.\n\n"
            f"⚡️ Скорость: до <b>25 Гбит/с</b>\n"
            f"🌍 Локации: Вена, Сингапур, Амстердам и др.\n"
            f"🔞 Полный доступ ко всем ресурсам 24/7\n\n"
            f"<i>Выбирай тариф и летай на сверхзвуке!</i>"
        )
        await message.answer(welcome_text, reply_markup=get_main_keyboard())

    @dp.message(Command("admin"))
    async def cmd_admin(message: types.Message):
        """Команда для доступа к админ-панели."""
        user_id = message.from_user.id
        
        if user_id not in ADMIN_IDS:
            await message.answer("⛔️ Доступ запрещён")
            return
        
        await message.answer(
            "<b>🛠 Админ-панель SteasHub</b>\n\n"
            "Выберите раздел:",
            reply_markup=get_admin_keyboard()
        )

    @dp.message(Command("root"))
    async def cmd_root(message: types.Message):
        """Расширенная админ-панель с доходами и статистикой."""
        user_id = message.from_user.id
        
        if user_id not in ADMIN_IDS:
            await message.answer("⛔️ Доступ запрещён. Команда только для администраторов.")
            return
        
        stats = db.get_all_stats()
        
        # Формируем отчёт
        report = (
            f"<b>📊 ПАНЕЛЬ АДМИНИСТРАТОРА | SteasHub</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>👥 Пользователи:</b>\n"
            f"├ Всего: {stats['total_users']} чел.\n"
            f"└ Активных подписчиков: {stats['active_subscribers']} чел.\n\n"
            f"<b>💰 Доходы (в рублях):</b>\n"
            f"├ За сегодня: {stats['revenue']['day']:.0f}₽\n"
            f"├ За неделю: {stats['revenue']['week']:.0f}₽\n"
            f"├ За месяц: {stats['revenue']['month']:.0f}₽\n"
            f"├ За год: {stats['revenue']['year']:.0f}₽\n"
            f"└ За всё время: {stats['revenue']['all']:.0f}₽\n\n"
            f"<b>📌 Подписки по тарифам:</b>\n"
        )
        
        for plan_key, count in stats['subscribers_by_plan'].items():
            plan_name = PLANS.get(plan_key, {}).get('name', plan_key)
            report += f"├ {plan_name}: <b>{count}</b> чел.\n"
        
        # Конверсия
        conversion = (stats['active_subscribers'] / max(stats['total_users'], 1)) * 100
        report += f"\n<b>📈 Конверсия:</b> {conversion:.1f}%\n"
        
        # Последние платежи
        recent_payments = db.get_payments_by_period(7)
        if recent_payments:
            report += f"\n<b>💳 Последние платежи (7 дней):</b>\n"
            for p in recent_payments[:5]:
                username = p['username'] or f"ID:{p['user_id']}"
                report += f"├ {p['amount']:.0f}₽ — @{username} [{p['plan_type']}]\n"
        
        # Статистика серверов (будущий функционал)
        report += f"\n<i>⚡️ Проверка скорости серверов — в разработке</i>"
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Обновить", callback_data="root_refresh"))
        builder.row(types.InlineKeyboardButton(text="💰 Детализация доходов", callback_data="root_revenue"))
        builder.row(types.InlineKeyboardButton(text="👥 Подписчики", callback_data="root_subscribers"))
        builder.row(types.InlineKeyboardButton(text="📡 Серверы (скоро)", callback_data="root_servers_stub"))
        
        await message.answer(report, reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "root_refresh")
    async def root_refresh(callback: types.CallbackQuery):
        """Обновление панели администратора."""
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        
        await callback.answer("🔄 Данные обновлены", show_alert=False)
        # Закрываем кнопку, пользователь может вызвать /root снова

    @dp.callback_query(F.data == "plans")
    async def show_plans(callback: types.CallbackQuery):
        logger.info(f"🖱 Юзер @{callback.from_user.username} смотрит тарифы")
        await callback.message.edit_text(
            "<b>📊 Доступные тарифы SteasHub:</b>\n\n"
            "Выбери подходящий план. Доступ предоставляется мгновенно после оплаты.",
            reply_markup=get_plans_keyboard()
        )

    @dp.callback_query(F.data == "start_trial_vpn")
    async def start_trial_vpn(callback: types.CallbackQuery):
        """Запуск пробной версии VPN - выдача бесплатного ключа."""
        user = callback.from_user
        logger.info(f"🚀 {user.full_name} запустил пробную версию VPN")
        
        await callback.answer("🔄 Загрузка VPN ключа...")
        
        # Проверяем наличие ключа
        current_key = vless.keys_manager.current_key
        
        if not current_key:
            # Пытаемся обновить ключ
            await callback.message.edit_text("🔄 Загрузка ключа...")
            success = await vless.keys_manager.update_current_key(force=True)
            if not success:
                await callback.message.edit_text(
                    "❌ <b>Не удалось загрузить ключ</b>\n\n"
                    "Попробуйте позже или свяжитесь с поддержкой."
                )
                return
            current_key = vless.keys_manager.current_key
        
        # Формируем сообщение с ключом
        connection_info = vless.keys_manager.get_connection_info(current_key)
        
        if connection_info["status"] != "ok":
            await callback.message.edit_text("❌ Ошибка парсинга ключа. Попробуйте ещё раз.")
            return
        
        key_text = (
            f"<b>🚀 Пробная версия VPN активирована!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ <b>Ваш бесплатный ключ подключён</b>\n\n"
            f"📍 <b>Локация:</b> {connection_info['location']}\n"
            f"🕒 <b>Обновлено:</b> {connection_info['updated_at']}\n"
            f"📊 <b>Лимит трафика:</b> {connection_info['traffic_limit']}\n\n"
            f"<b>🔑 VLESS ключ:</b>\n"
            f"<code>{connection_info['key']}</code>\n\n"
            f"<b>📲 Как подключить:</b>\n"
            f"1️⃣ Скопируйте ключ выше\n"
            f"2️⃣ Откройте VPN приложение (Hiddify, V2Ray, NekoBox)\n"
            f"3️⃣ Нажмите 'Добавить профиль' → 'Импортировать из буфера'\n"
            f"4️⃣ Нажмите 'Подключиться'\n\n"
            f"<i>⚡️ Ключ обновляется автоматически каждый день!</i>"
        )
        
        # Кнопки
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Обновить ключ", callback_data="vless_refresh"))
        builder.row(types.InlineKeyboardButton(text="📍 Другие локации", callback_data="vless_locations"))
        builder.row(types.InlineKeyboardButton(text="💎 Премиум тарифы", callback_data="plans"))
        builder.row(types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_home"))

        await callback.message.edit_text(key_text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "blacklist_vpn")
    async def blacklist_vpn(callback: types.CallbackQuery):
        """
        Обычный интернет через черные списки.
        Ключи обновляются каждые 12 часов для обхода блокировок.
        """
        user = callback.from_user
        logger.info(f"🌐 {user.full_name} использует обычный интернет (без белых списков)")
        
        await callback.answer("🔄 Загрузка ключа для обхода блокировок...")
        
        # Проверяем наличие ключа
        current_key = vless.keys_manager.current_key
        
        if not current_key:
            await callback.message.edit_text("🔄 Загрузка актуального ключа обхода...")
            success = await vless.keys_manager.update_current_key(force=True)
            if not success:
                await callback.message.edit_text(
                    "❌ <b>Не удалось загрузить ключ</b>\n\n"
                    "Попробуйте позже или свяжитесь с поддержкой."
                )
                return
            current_key = vless.keys_manager.current_key
        
        # Проверяем, нужно ли обновить ключ (каждые 12 часов)
        time_since_update = datetime.datetime.now() - vless.keys_manager.last_update
        hours_left = 12 - time_since_update.total_seconds() / 3600
        
        connection_info = vless.keys_manager.get_connection_info(current_key)
        
        if connection_info["status"] != "ok":
            await callback.message.edit_text("❌ Ошибка парсинга ключа. Попробуйте ещё раз.")
            return
        
        key_text = (
            f"<b>🌐 Обычный интернет (без белых списков)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ <b>Доступ ко всем сайтам активирован!</b>\n\n"
            f"🔑 <b>Ключ для обхода блокировок:</b>\n"
            f"<code>{connection_info['key']}</code>\n\n"
            f"<b>📊 Информация:</b>\n"
            f"├ Локация: {connection_info['location']}\n"
            f"├ Лимит трафика: {connection_info['traffic_limit']}\n"
            f"├ Обновление ключа: каждые 12 часов\n"
            f"└ До следующего обновления: ~{hours_left:.1f} ч.\n\n"
            f"<b>📲 Как использовать:</b>\n"
            f"1️⃣ Скопируйте ключ выше\n"
            f"2️⃣ Откройте VPN приложение\n"
            f"   • Hiddify / V2Ray / NekoBox / Streisand\n"
            f"3️⃣ Импортируйте ключ из буфера обмена\n"
            f"4️⃣ Подключитесь и пользуйтесь интернетом без блокировок!\n\n"
            f"<i>⚡️ Ключ автоматически обновляется каждые 12 часов\n"
            f"для обеспечения стабильного обхода блокировок</i>"
        )
        
        # Кнопки
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Обновить ключ сейчас", callback_data="vless_refresh"))
        builder.row(types.InlineKeyboardButton(text="📍 Выбрать локацию", callback_data="vless_locations"))
        builder.row(
            types.InlineKeyboardButton(text="💎 Премиум (без лимитов)", callback_data="plans"),
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_home")
        )
        
        await callback.message.edit_text(key_text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data.startswith("buy_"))
    async def plan_details(callback: types.CallbackQuery):
        plan_id = callback.data.split("_")[1]
        plan = PLANS[plan_id]
        logger.info(f"🛒 Юзер @{callback.from_user.username} выбрал тариф {plan['name']}")

        detail_text = (
            f"<b>Тариф: {plan['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Стоимость: <b>{plan['price']} руб/мес</b>\n"
            f"📱 Устройств: <b>{plan['devices']}</b>\n"
            f"⚡️ Скорость: <b>{plan['speed']}</b>\n"
            f"🌍 Локации: <code>{plan['locations']}</code>\n\n"
            f"📝 <i>{plan['desc']}</i>"
        )
        await callback.message.edit_text(detail_text, reply_markup=get_plan_detail_keyboard(plan_id))

    @dp.callback_query(F.data == "pay_stub")
    async def pay_stub(callback: types.CallbackQuery):
        logger.warning(f"⚠️ Юзер @{callback.from_user.username} пытался оплатить (модуль в разработке)")
        await callback.answer(
            "🛠 Платежный шлюз SteasHub на техобслуживании.\nАвтоматическая оплата будет доступна в версии 1.1!",
            show_alert=True
        )

    @dp.callback_query(F.data == "back_home")
    async def back_home(callback: types.CallbackQuery):
        await callback.message.edit_text(
            f"<b>Главное меню SteasHub | VPN</b>\n\n"
            f"Привет, {callback.from_user.first_name}!",
            reply_markup=get_main_keyboard()
        )

    # ==================== ПРОФИЛЬ ====================
    
    @dp.callback_query(F.data == "profile")
    async def profile(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        
        # Получаем данные о подписке
        subscription = db.get_active_subscription(user_id)
        
        if subscription:
            plan = PLANS.get(subscription['plan_type'], {})
            expires = datetime.datetime.fromisoformat(subscription['expires_at'])
            days_left = (expires - datetime.datetime.now()).days
            
            profile_text = (
                f"<b>👤 Личный кабинет</b>\n\n"
                f"📛 Имя: <b>{callback.from_user.first_name}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                f"<b>📌 Активная подписка:</b>\n"
                f"├ Тариф: {plan.get('name', subscription['plan_type'])}\n"
                f"├ Устройств: {subscription['devices_count']}\n"
                f"└ Истекает: через {days_left} дн. ({expires.strftime('%d.%m.%Y')})\n\n"
            )
        else:
            profile_text = (
                f"<b>👤 Личный кабинет</b>\n\n"
                f"📛 Имя: <b>{callback.from_user.first_name}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                f"⚠️ <i>Нет активной подписки</i>\n"
                f"Выберите тариф для подключения!\n\n"
            )
        
        await callback.message.edit_text(profile_text, reply_markup=get_profile_keyboard())

    @dp.callback_query(F.data == "back_profile")
    async def back_profile(callback: types.CallbackQuery):
        await profile(callback)

    # ==================== СИСТЕМА РЕПОРТОВ ====================
    
    @dp.callback_query(F.data == "report_server")
    async def start_report(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        
        # Проверка возможности репорта
        can_report, reason = db.can_report_server(user_id)
        
        if not can_report:
            await callback.answer(f"⚠️ {reason}", show_alert=True)
            return
        
        await callback.message.edit_text(
            "<b>📡 Сообщить о проблеме с сервером</b>\n\n"
            "Выберите регион, где возникла проблема:",
            reply_markup=get_report_region_keyboard()
        )

    @dp.callback_query(F.data.startswith("report_region_"))
    async def select_report_region(callback: types.CallbackQuery):
        region_code = callback.data.split("_")[2]
        region_name = SERVER_REGIONS.get(region_code, region_code)
        
        # Сохраняем регион в состоянии (через callback_data)
        await callback.message.edit_text(
            f"<b>📡 Проблема с сервером: {region_name}</b>\n\n"
            "Выберите тип проблемы:",
            reply_markup=get_report_issue_keyboard(region_code)
        )

    @dp.callback_query(F.data.startswith("report_issue_"))
    async def submit_report(callback: types.CallbackQuery):
        parts = callback.data.split("_")
        region_code = parts[2]
        issue_code = parts[3]
        
        region_name = SERVER_REGIONS.get(region_code, region_code)
        issue_name = ISSUE_TYPES.get(issue_code, issue_code)
        
        # Создаём репорт
        db.add_server_report(
            user_id=callback.from_user.id,
            server_region=region_name,
            issue_type=issue_name,
            description=""
        )
        
        logger.info(f"⚠️ НОВЫЙ РЕПОРТ: {callback.from_user.username} | {region_name} | {issue_name}")
        
        await callback.message.edit_text(
            "<b>✅ Репорт отправлен!</b>\n\n"
            f"📍 Регион: {region_name}\n"
            f"🔧 Проблема: {issue_name}\n\n"
            "Администраторы уведомлены. Проблема будет решена в ближайшее время."
        )
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ <b>Новый репорт сервера!</b>\n\n"
                    f"👤 От: @{callback.from_user.username} ({callback.from_user.first_name})\n"
                    f"📍 Регион: {region_name}\n"
                    f"🔧 Проблема: {issue_name}"
                )
            except:
                pass

    # ==================== АДМИН ПАНЕЛЬ ====================
    
    @dp.callback_query(F.data == "admin_stats")
    async def admin_stats(callback: types.CallbackQuery):
        stats = db.get_all_stats()
        
        text = (
            "<b>📊 Общая статистика SteasHub</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
            f"⭐ Активных подписчиков: <b>{stats['active_subscribers']}</b>\n\n"
            f"<b>💰 Доходы:</b>\n"
            f"├ За день: {stats['revenue']['day']:.0f}₽\n"
            f"├ За неделю: {stats['revenue']['week']:.0f}₽\n"
            f"├ За месяц: {stats['revenue']['month']:.0f}₽\n"
            f"└ За всё время: {stats['revenue']['all']:.0f}₽\n\n"
            f"<b>📌 По тарифам:</b>\n"
        )
        
        for plan_key, count in stats['subscribers_by_plan'].items():
            plan_name = PLANS.get(plan_key, {}).get('name', plan_key)
            text += f"├ {plan_name}: {count} чел.\n"
        
        await callback.message.edit_text(text, reply_markup=get_stats_period_keyboard())

    @dp.callback_query(F.data == "admin_revenue")
    async def admin_revenue_menu(callback: types.CallbackQuery):
        await callback.message.edit_text(
            "<b>💰 Детализация доходов</b>\n\n"
            "Выберите период:",
            reply_markup=get_stats_period_keyboard()
        )

    @dp.callback_query(F.data.startswith("revenue_"))
    async def admin_revenue_detail(callback: types.CallbackQuery):
        period = callback.data.split("_")[1]
        period_days = {"day": 1, "week": 7, "month": 30, "year": 365}.get(period, 30)
        period_name = {"day": "день", "week": "неделю", "month": "месяц", "year": "год"}.get(period, "месяц")
        
        revenue = db.get_revenue_by_period(period_days)
        payments = db.get_payments_by_period(period_days)
        
        text = (
            f"<b>💰 Доходы за {period_name}</b>\n\n"
            f"💵 Сумма: <b>{revenue:.0f}₽</b>\n"
            f"📊 Платежей: {len(payments)}\n\n"
        )
        
        if payments:
            text += "<b>Последние платежи:</b>\n"
            for p in payments[:10]:
                username = p['username'] or f"ID:{p['user_id']}"
                text += f"├ {p['amount']:.0f}₽ — @{username} ({p['plan_type']})\n"
        
        text += "\nВыберите другой период:"
        
        await callback.message.edit_text(text, reply_markup=get_stats_period_keyboard())

    @dp.callback_query(F.data == "admin_subscribers")
    async def admin_subscribers(callback: types.CallbackQuery):
        stats = db.get_all_stats()
        
        text = (
            "<b>👥 Подписчики</b>\n\n"
            f"📊 Активных: <b>{stats['active_subscribers']}</b>\n"
            f"📈 Конверсия: {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%\n\n"
            f"<b>По тарифам:</b>\n"
        )
        
        for plan_key, count in stats['subscribers_by_plan'].items():
            plan_name = PLANS.get(plan_key, {}).get('name', plan_key)
            text += f"├ {plan_name}: {count} чел.\n"
        
        # Топ пользователей по количеству подписок
        text += "\n<i>Детальная информация в разработке...</i>"
        
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard())

    @dp.callback_query(F.data == "admin_reports")
    async def admin_reports(callback: types.CallbackQuery):
        reports = db.get_server_reports(20)
        
        if not reports:
            await callback.message.edit_text(
                "<b>⚠️ Репорты серверов</b>\n\n"
                "Нет активных репортов. Все серверы работают нормально.",
                reply_markup=get_admin_keyboard()
            )
            return
        
        text = "<b>⚠️ Репорты серверов (последние 20)</b>\n\n"
        
        for r in reports:
            status_emoji = {"new": "🆕", "in_progress": "🔧", "resolved": "✅"}.get(r['status'], "📝")
            username = r['username'] or f"ID:{r['user_id']}"
            text += (
                f"{status_emoji} <code>{r['server_region']}</code> — {r['issue_type']}\n"
                f"   От: @{username} | {r['created_at'][:16]}\n"
            )
        
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard())

    @dp.callback_query(F.data == "admin_menu")
    async def admin_menu(callback: types.CallbackQuery):
        await callback.message.edit_text(
            "<b>🛠 Админ-панель SteasHub</b>\n\nВыберите раздел:",
            reply_markup=get_admin_keyboard()
        )

    # ==================== ROOT PANEL ====================
    
    @dp.callback_query(F.data == "root_revenue")
    async def root_revenue(callback: types.CallbackQuery):
        """Детализация доходов из /root."""
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        
        stats = db.get_revenue_stats()
        
        text = (
            f"<b>💰 Детализация доходов SteasHub</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Периоды:</b>\n"
            f"├ Сегодня: {stats['day']:.0f}₽\n"
            f"├ Неделя: {stats['week']:.0f}₽\n"
            f"├ Месяц: {stats['month']:.0f}₽\n"
            f"├ Год: {stats['year']:.0f}₽\n"
            f"└ Всё время: {stats['all']:.0f}₽\n\n"
        )
        
        # Топ платежей за месяц
        payments = db.get_payments_by_period(30)
        if payments:
            text += f"<b>Топ платежей (30 дней):</b>\n"
            # Сортируем по сумме
            sorted_payments = sorted(payments, key=lambda x: x['amount'], reverse=True)[:10]
            for i, p in enumerate(sorted_payments, 1):
                username = p['username'] or f"ID:{p['user_id']}"
                text += f"{i}. {p['amount']:.0f}₽ — @{username}\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="📊 За месяц", callback_data="revenue_month"),
            types.InlineKeyboardButton(text="📊 За год", callback_data="revenue_year")
        )
        builder.row(types.InlineKeyboardButton(text="🔙 Назад к панели", callback_data="root_back"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "root_subscribers")
    async def root_subscribers(callback: types.CallbackQuery):
        """Информация о подписчиках из /root."""
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        
        stats = db.get_all_stats()
        
        # Получаем всех активных подписчиков
        with db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, s.plan_type, s.expires_at
                FROM subscriptions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'active' AND s.expires_at > CURRENT_TIMESTAMP
                ORDER BY s.expires_at DESC
                LIMIT 50
            """)
            subscribers = cursor.fetchall()
        
        text = (
            f"<b>👥 Подписчики SteasHub</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Всего активных:</b> {stats['active_subscribers']} чел.\n"
            f"<b>Конверсия:</b> {(stats['active_subscribers'] / max(stats['total_users'], 1) * 100):.1f}%\n\n"
            f"<b>По тарифам:</b>\n"
        )
        
        for plan_key, count in stats['subscribers_by_plan'].items():
            plan_name = PLANS.get(plan_key, {}).get('name', plan_key)
            text += f"├ {plan_name}: <b>{count}</b> чел.\n"
        
        if subscribers:
            text += f"\n<b>📋 Последние (50):</b>\n"
            for sub in subscribers[:20]:
                username = sub['username'] or f"ID:{sub['user_id']}"
                plan_name = PLANS.get(sub['plan_type'], {}).get('name', sub['plan_type'])
                expires = sub['expires_at'][:10]
                text += f"├ @{username} — {plan_name} (до {expires})\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔙 Назад к панели", callback_data="root_back"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data == "root_servers_stub")
    async def root_servers_stub(callback: types.CallbackQuery):
        """Заглушка для статистики серверов."""
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("⛔️ Доступ запрещён", show_alert=True)
            return

        await callback.answer("🔜 Проверка пинга и скорости серверов в разработке", show_alert=True)

    # ==================== VLESS КЛЮЧИ ====================

    @dp.message(Command("fastvpn"))
    async def cmd_fastvpn(message: types.Message):
        """Команда для быстрого подключения к бесплатному VPN."""
        user = message.from_user
        logger.info(f"🚀 {user.full_name} использует /fastvpn")
        
        # Проверяем наличие ключа
        current_key = vless.keys_manager.current_key
        
        if not current_key:
            # Пытаемся обновить ключ
            await message.answer("🔄 Загрузка ключа...")
            success = await vless.keys_manager.update_current_key(force=True)
            if not success:
                await message.answer(
                    "❌ <b>Не удалось загрузить ключ</b>\n\n"
                    "Попробуйте позже или свяжитесь с поддержкой."
                )
                return
            current_key = vless.keys_manager.current_key
        
        # Формируем сообщение с ключом
        connection_info = vless.keys_manager.get_connection_info(current_key)
        
        if connection_info["status"] != "ok":
            await message.answer("❌ Ошибка парсинга ключа. Попробуйте /keys для обновления.")
            return
        
        key_text = (
            f"<b>🚀 Быстрый VPN | Бесплатный ключ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 <b>Локация:</b> {connection_info['location']}\n"
            f"🕒 <b>Обновлено:</b> {connection_info['updated_at']}\n"
            f"📊 <b>Лимит трафика:</b> {connection_info['traffic_limit']}</\n\n"
            f"<b>⚙️ Параметры подключения:</b>\n"
            f"├ Хост: <code>{connection_info['host']}</code>\n"
            f"├ Порт: <code>{connection_info['port']}</code>\n"
            f"├ Security: <code>{connection_info['security']}</code>\n"
            f"├ Type: <code>{connection_info['type']}</code>\n"
            f"├ SNI: <code>{connection_info['sni']}</code>\n"
            f"├ PBK: <code>{connection_info['pbk']}</code>\n"
            f"└ SID: <code>{connection_info['sid']}</code>\n\n"
            f"<b>🔑 VLESS ключ:</b>\n"
            f"<code>{connection_info['key']}</code>\n\n"
            f"<i>💡 Скопируйте ключ и импортируйте в ваш VPN клиент "
            f"(V2Ray, Hiddify, NekoBox, Streisand и др.)</i>"
        )
        
        # Кнопки
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Обновить ключ", callback_data="vless_refresh"))
        builder.row(types.InlineKeyboardButton(text="📍 Другие локации", callback_data="vless_locations"))
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_home"))
        
        await message.answer(key_text, reply_markup=builder.as_markup())

    @dp.message(Command("keys"))
    async def cmd_keys(message: types.Message):
        """Ручное обновление ключей."""
        user = message.from_user
        logger.info(f"🔄 {user.full_name} использует /keys")
        
        await message.answer("🔄 Обновление ключей...")
        
        success = await vless.keys_manager.update_current_key(force=True)
        
        if success:
            current_key = vless.keys_manager.current_key
            await message.answer(
                f"✅ <b>Ключи обновлены!</b>\n\n"
                f"📍 Актуальная локация: <b>{current_key.location}</b>\n"
                f"🕒 Обновлено: {current_key.updated_at}\n\n"
                f"Используйте /fastvpn для подключения."
            )
        else:
            await message.answer(
                "❌ <b>Не удалось обновить ключи</b>\n\n"
                "Попробуйте позже или проверьте соединение с интернетом."
            )

    @dp.callback_query(F.data == "vless_refresh")
    async def vless_refresh(callback: types.CallbackQuery):
        """Обновление VLESS ключа."""
        await callback.answer("🔄 Обновление...")
        
        success = await vless.keys_manager.update_current_key(force=True)
        
        if success:
            current_key = vless.keys_manager.current_key
            await callback.message.edit_text(
                f"✅ <b>Ключ обновлён!</b>\n\n"
                f"📍 Локация: {current_key.location}\n"
                f"🕒 Обновлено: {current_key.updated_at}\n\n"
                f"Используйте /fastvpn для получения ключа."
            )
        else:
            await callback.answer("❌ Не удалось обновить", show_alert=True)

    @dp.callback_query(F.data == "vless_locations")
    async def vless_locations(callback: types.CallbackQuery):
        """Показ доступных локаций."""
        available_keys = vless.keys_manager.available_keys
        
        if not available_keys:
            await callback.answer("🔄 Загрузка доступных локаций...")
            success = await vless.keys_manager.update_current_key(force=True)
            if not success:
                await callback.answer("❌ Не удалось загрузить локации", show_alert=True)
                return
            available_keys = vless.keys_manager.available_keys
        
        if len(available_keys) <= 1:
            await callback.answer("Доступна только одна локация", show_alert=True)
            return
        
        text = "<b>📍 Доступные локации:</b>\n\n"
        
        builder = InlineKeyboardBuilder()
        for i, key in enumerate(available_keys[:10], 1):  # Показываем до 10 локаций
            text += f"{i}. {key.location} | {key.updated_at}\n"
            builder.row(types.InlineKeyboardButton(
                text=f"📍 {key.location}",
                callback_data=f"vless_select_{i}"
            ))
        
        builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="vless_refresh"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    @dp.callback_query(F.data.startswith("vless_select_"))
    async def vless_select_location(callback: types.CallbackQuery):
        """Выбор конкретной локации."""
        try:
            index = int(callback.data.split("_")[-1]) - 1
            available_keys = vless.keys_manager.available_keys
            
            if 0 <= index < len(available_keys):
                selected_key = available_keys[index]
                vless.keys_manager._current_key = selected_key  # Устанавливаем как текущий
                
                connection_info = vless.keys_manager.get_connection_info(selected_key)
                
                key_text = (
                    f"<b>✅ Выбрана локация: {selected_key.location}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🕒 <b>Обновлено:</b> {selected_key.updated_at}\n"
                    f"📊 <b>Лимит трафика:</b> {selected_key.traffic_limit}\n\n"
                    f"<b>🔑 VLESS ключ:</b>\n"
                    f"<code>{connection_info['key']}</code>\n\n"
                    f"<i>💡 Скопируйте ключ и импортируйте в ваш VPN клиент</i>"
                )
                
                builder = InlineKeyboardBuilder()
                builder.row(types.InlineKeyboardButton(text="🔄 Обновить", callback_data="vless_refresh"))
                builder.row(types.InlineKeyboardButton(text="📍 Другие локации", callback_data="vless_locations"))
                builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_home"))
                
                await callback.message.edit_text(key_text, reply_markup=builder.as_markup())
            else:
                await callback.answer("❌ Локация не найдена", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка выбора локации: {e}")
            await callback.answer("❌ Ошибка", show_alert=True)

    @dp.callback_query(F.data == "root_back")
    async def root_back(callback: types.CallbackQuery):
        """Возврат к главной панели /root."""
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        
        # Отправляем то же сообщение что и /root
        stats = db.get_all_stats()
        
        report = (
            f"<b>📊 ПАНЕЛЬ АДМИНИСТРАТОРА | SteasHub</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>👥 Пользователи:</b>\n"
            f"├ Всего: {stats['total_users']} чел.\n"
            f"└ Активных подписчиков: {stats['active_subscribers']} чел.\n\n"
            f"<b>💰 Доходы (в рублях):</b>\n"
            f"├ За сегодня: {stats['revenue']['day']:.0f}₽\n"
            f"├ За неделю: {stats['revenue']['week']:.0f}₽\n"
            f"├ За месяц: {stats['revenue']['month']:.0f}₽\n"
            f"├ За год: {stats['revenue']['year']:.0f}₽\n"
            f"└ За всё время: {stats['revenue']['all']:.0f}₽\n\n"
            f"<b>📌 Подписки по тарифам:</b>\n"
        )
        
        for plan_key, count in stats['subscribers_by_plan'].items():
            plan_name = PLANS.get(plan_key, {}).get('name', plan_key)
            report += f"├ {plan_name}: <b>{count}</b> чел.\n"
        
        conversion = (stats['active_subscribers'] / max(stats['total_users'], 1)) * 100
        report += f"\n<b>📈 Конверсия:</b> {conversion:.1f}%\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Обновить", callback_data="root_refresh"))
        builder.row(types.InlineKeyboardButton(text="💰 Детализация доходов", callback_data="root_revenue"))
        builder.row(types.InlineKeyboardButton(text="👥 Подписчики", callback_data="root_subscribers"))
        builder.row(types.InlineKeyboardButton(text="📡 Серверы (скоро)", callback_data="root_servers_stub"))
        
        await callback.message.edit_text(report, reply_markup=builder.as_markup())

    # Запуск
    print("\n" + "="*40)
    print("🚀 SteasHub | VPN БОТ УСПЕШНО ЗАПУЩЕН!")
    print(f"📡 Соединение: {PROXY_URL if PROXY_URL else 'Прямое (без прокси)'}")
    print(f"⏰ Время запуска: {datetime.datetime.now().strftime('%H:%M:%S')}")
    print(f"👥 Админы: {ADMIN_IDS if ADMIN_IDS else 'Не настроены'}")
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
