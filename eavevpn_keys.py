"""
Модуль для загрузки VLESS ключей из Telegram канала @EaveVPNbot.
Использует Telethon для парсинга сообщений канала.
"""

import asyncio
import logging
import re
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.tl.types import Message

logger = logging.getLogger("EaveVPNKeys")

# Конфигурация из переменных окружения
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")

# Каналы EaveVPN (приоритет по порядку)
# @EaveVPN - основной канал
# @EvaVPN_Free - бесплатные ключи
# @evavpn - альтернативный канал
CHANNEL_USERNAMES = ["EvaVPN_Free", "EaveVPN", "evavpn"]

# Паттерны для извлечения ключей
VLESS_PATTERN = re.compile(r'vless://[^\s\n`]+')
VMESS_PATTERN = re.compile(r'vmess://[^\s\n`]+')
TROJAN_PATTERN = re.compile(r'trojan://[^\s\n`]+')
SS_PATTERN = re.compile(r'ss://[^\s\n`]+')


@dataclass
class VPNKey:
    """Класс для хранения VPN ключа."""
    key: str
    key_type: str  # vless, vmess, trojan, ss
    message_text: str
    message_date: datetime
    message_id: int
    
    @property
    def is_valid(self) -> bool:
        """Проверка валидности ключа."""
        return any([
            self.key.startswith("vless://"),
            self.key.startswith("vmess://"),
            self.key.startswith("trojan://"),
            self.key.startswith("ss://")
        ])
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя ключа."""
        return f"{self.key_type.upper()} | {self.message_date.strftime('%Y-%m-%d %H:%M')}"


class EaveVPNKeysManager:
    """Менеджер для управления ключами из @EaveVPNbot."""
    
    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._current_key: Optional[VPNKey] = None
        self._last_update: Optional[datetime] = None
        self._update_interval = timedelta(hours=12)  # Обновление раз в 12 часов
        self._keys_history: List[VPNKey] = []
        self._is_initialized = False
    
    async def init_client(self) -> bool:
        """
        Инициализация Telegram клиента.
        Возвращает True если успешно.
        """
        if not API_ID or not API_HASH:
            logger.error("❌ TELEGRAM_API_ID и TELEGRAM_API_HASH не настроены!")
            logger.error("Получите их на https://my.telegram.org")
            return False
        
        try:
            self._client = TelegramClient(
                'eavevpn_session',
                API_ID,
                API_HASH
            )
            await self._client.start()
            
            # Проверка авторизации
            if not await self._client.is_user_authorized():
                logger.warning("⚠️ Клиент не авторизован. Требуется вход по номеру телефона.")
                if PHONE:
                    await self._client.send_code_request(PHONE)
                    logger.info(f"📱 Код отправлен на {PHONE}")
                else:
                    logger.error("❌ TELEGRAM_PHONE не настроен!")
                    return False
            
            self._is_initialized = True
            logger.info("✅ Telegram клиент инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации клиента: {e}")
            return False
    
    async def fetch_keys(self, limit: int = 50) -> List[VPNKey]:
        """
        Загрузка ключей из каналов EaveVPN.
        Проверяет несколько каналов по приоритету.

        Args:
            limit: Количество последних сообщений для проверки в каждом канале

        Returns:
            Список найденных VPN ключей
        """
        keys = []

        if not self._is_initialized:
            success = await self.init_client()
            if not success:
                return keys

        for channel_username in CHANNEL_USERNAMES:
            try:
                # Получаем последние сообщения из канала
                async for message in self._client.iter_messages(channel_username, limit=limit):
                    if not message.message:
                        continue

                    text = message.message

                    # Ищем VLESS ключи
                    vless_matches = VLESS_PATTERN.findall(text)
                    for key in vless_matches:
                        vpn_key = VPNKey(
                            key=key,
                            key_type="vless",
                            message_text=text[:100],
                            message_date=message.date,
                            message_id=message.id
                        )
                        keys.append(vpn_key)
                        logger.info(f"Найден VLESS ключ в @{channel_username}: {message.date}")

                    # Ищем VMESS ключи
                    vmess_matches = VMESS_PATTERN.findall(text)
                    for key in vmess_matches:
                        vpn_key = VPNKey(
                            key=key,
                            key_type="vmess",
                            message_text=text[:100],
                            message_date=message.date,
                            message_id=message.id
                        )
                        keys.append(vpn_key)
                        logger.info(f"Найден VMESS ключ в @{channel_username}: {message.date}")

                    # Ищем TROJAN ключи
                    trojan_matches = TROJAN_PATTERN.findall(text)
                    for key in trojan_matches:
                        vpn_key = VPNKey(
                            key=key,
                            key_type="trojan",
                            message_text=text[:100],
                            message_date=message.date,
                            message_id=message.id
                        )
                        keys.append(vpn_key)
                        logger.info(f"Найден TROJAN ключ в @{channel_username}: {message.date}")

                    # Ищем Shadowsocks ключи
                    ss_matches = SS_PATTERN.findall(text)
                    for key in ss_matches:
                        vpn_key = VPNKey(
                            key=key,
                            key_type="ss",
                            message_text=text[:100],
                            message_date=message.date,
                            message_id=message.id
                        )
                        keys.append(vpn_key)
                        logger.info(f"Найден SS ключ в @{channel_username}: {message.date}")

                # Если нашли ключи в этом канале, не проверяем остальные
                if keys:
                    logger.info(f"✅ Найдено ключей в @{channel_username}: {len(keys)}")
                    break

            except Exception as e:
                logger.warning(f"Не удалось получить ключи из @{channel_username}: {e}")
                continue

        logger.info(f"Всего найдено ключей: {len(keys)}")
        return keys
    
    async def update_current_key(self, force: bool = False) -> bool:
        """
        Обновление текущего ключа.
        
        Args:
            force: Принудительное обновление
        
        Returns:
            True если ключ успешно обновлён
        """
        # Проверяем, нужно ли обновление
        if not force and self._current_key and self._last_update:
            if datetime.now() - self._last_update < self._update_interval:
                logger.info("Ключ ещё актуален, обновление не требуется")
                return True
        
        keys = await self.fetch_keys(limit=50)
        
        if not keys:
            logger.warning("Не найдено действительных ключей")
            return False
        
        # Выбираем первый (новейший) ключ
        self._current_key = keys[0]
        self._last_update = datetime.now()
        self._keys_history = keys
        
        logger.info(f"Ключ обновлён: {self._current_key.key_type}")
        return True
    
    @property
    def current_key(self) -> Optional[VPNKey]:
        """Получение текущего ключа."""
        return self._current_key
    
    @property
    def available_keys(self) -> List[VPNKey]:
        """Получение всех доступных ключей."""
        return self._keys_history
    
    @property
    def last_update(self) -> Optional[datetime]:
        """Получение времени последнего обновления."""
        return self._last_update
    
    @property
    def is_key_expired(self) -> bool:
        """Проверка, устарел ли текущий ключ."""
        if not self._current_key or not self._last_update:
            return True
        return datetime.now() - self._last_update >= self._update_interval
    
    def get_key_by_type(self, key_type: str) -> Optional[VPNKey]:
        """Получение ключа по типу."""
        for key in self._keys_history:
            if key.key_type.lower() == key_type.lower():
                return key
        return None
    
    async def close(self):
        """Закрытие клиента."""
        if self._client:
            await self._client.disconnect()
            logger.info("Telegram клиент отключён")


# Глобальный экземпляр менеджера
keys_manager = EaveVPNKeysManager()


async def init_keys_manager() -> bool:
    """Инициализация менеджера и загрузка первого ключа."""
    logger.info("Инициализация менеджера ключей EaveVPN...")
    success = await keys_manager.init_client()
    if not success:
        logger.warning("⚠️ Не удалось инициализировать клиент EaveVPN")
        return False
    
    success = await keys_manager.update_current_key(force=True)
    if success:
        logger.info("✅ Менеджер ключей EaveVPN инициализирован")
    else:
        logger.warning("⚠️ Не удалось загрузить ключи при инициализации")
    return success


async def scheduled_keys_update():
    """
    Фоновая задача для периодического обновления ключей.
    Запускается каждые 12 часов (в 00:00 и 12:00 UTC).
    """
    while True:
        now = datetime.now()
        # Обновляем каждые 12 часов: в 00:00 и 12:00
        if now.hour < 12:
            next_update = now.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            next_update = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        sleep_seconds = (next_update - now).total_seconds()
        
        logger.info(f"Следующее обновление ключей EaveVPN через {sleep_seconds / 3600:.1f} часов")
        await asyncio.sleep(sleep_seconds)
        
        logger.info("🔄 Автоматическое обновление ключей EaveVPN (каждые 12 часов)...")
        await keys_manager.update_current_key(force=True)
