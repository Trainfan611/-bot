"""
Модуль для автоматической загрузки бесплатных VLESS ключей с GitHub.
Репозиторий: https://github.com/duckray-client/free-vless-keys
"""

import aiohttp
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger("VLESSKeys")

# URL репозитория с ключами
GITHUB_REPO = "https://raw.githubusercontent.com/duckray-client/free-vless-keys/refs/heads/main/README.md"

# Паттерн для извлечения VLESS ключей
VLESS_PATTERN = re.compile(r'vless://[^\s`]+')


@dataclass
class VLESSKey:
    """Класс для хранения VLESS ключа."""
    key: str
    location: str
    updated_at: str
    traffic_limit: str = "500GB"
    
    @property
    def is_valid(self) -> bool:
        """Проверка валидности ключа."""
        return self.key.startswith("vless://")
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя ключа."""
        return f"{self.location} | {self.updated_at}"


class VLESSKeysManager:
    """Менеджер для управления VLESS ключами."""
    
    def __init__(self):
        self._current_key: Optional[VLESSKey] = None
        self._last_update: Optional[datetime] = None
        self._update_interval = timedelta(hours=12)  # Обновление раз в 12 часов
        self._keys_history: List[VLESSKey] = []
    
    async def fetch_keys(self) -> List[VLESSKey]:
        """
        Загрузка ключей с GitHub.
        Возвращает список найденных VLESS ключей.
        """
        keys = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GITHUB_REPO, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка загрузки README: {response.status}")
                        return keys
                    
                    content = await response.text()
                    
                    # Извлекаем все VLESS ключи
                    vless_matches = VLESS_PATTERN.findall(content)
                    
                    # Извлекаем информацию о локациях и датах обновления
                    # Ищем паттерны типа "🇫🇷 FRANCE" или "France"
                    location_pattern = re.compile(r'(?:🇺🇳|🇫🇷|🇩🇪|🇳🇱|🇬🇧|🇺🇸|🇸🇬|🇯🇵|🇰🇷|🇮🇳|🇷🇺|🇺🇦|🇦🇹|🇷🇴|🇫🇮)\s*([A-Za-zА-Яа-я]+)')
                    
                    # Ищем дату обновления
                    date_pattern = re.compile(r'Обновлено:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})')
                    
                    for vless_key in vless_matches:
                        # Пытаемся определить локацию из контекста
                        location = "Unknown"
                        updated = "Unknown"
                        
                        # Находим позицию ключа в контенте
                        key_pos = content.find(vless_key)
                        if key_pos != -1:
                            # Ищем локацию вблизи ключа (за 200 символов до)
                            context_before = content[max(0, key_pos - 200):key_pos]
                            location_match = location_pattern.search(context_before)
                            if location_match:
                                location = location_match.group(1)
                            
                            # Ищем дату обновления
                            date_match = date_pattern.search(context_before)
                            if date_match:
                                updated = date_match.group(1)
                        
                        key = VLESSKey(
                            key=vless_key,
                            location=location,
                            updated_at=updated
                        )
                        keys.append(key)
                        logger.info(f"Найден ключ: {location} | {updated}")
                    
                    logger.info(f"Всего найдено ключей: {len(keys)}")
                    
        except Exception as e:
            logger.error(f"Ошибка при загрузке ключей: {e}")
        
        return keys
    
    async def update_current_key(self, force: bool = False) -> bool:
        """
        Обновление текущего ключа.
        
        Args:
            force: Принудительное обновление (игнорируя интервал)
        
        Returns:
            True если ключ успешно обновлён
        """
        # Проверяем, нужно ли обновление
        if not force and self._current_key and self._last_update:
            if datetime.now() - self._last_update < self._update_interval:
                logger.info("Ключ ещё актуален, обновление не требуется")
                return True
        
        keys = await self.fetch_keys()
        
        if not keys:
            logger.warning("Не найдено действительных ключей")
            return False
        
        # Выбираем первый ключ (обычно это Франция или основной)
        # Можно добавить логику выбора по пингу/локации
        self._current_key = keys[0]
        self._last_update = datetime.now()
        self._keys_history = keys  # Сохраняем все ключи для выбора
        
        logger.info(f"Ключ обновлён: {self._current_key.location}")
        return True
    
    @property
    def current_key(self) -> Optional[VLESSKey]:
        """Получение текущего ключа."""
        return self._current_key
    
    @property
    def available_keys(self) -> List[VLESSKey]:
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
    
    def get_key_by_location(self, location: str) -> Optional[VLESSKey]:
        """Получение ключа по названию локации."""
        for key in self._keys_history:
            if location.lower() in key.location.lower():
                return key
        return None
    
    def get_connection_info(self, key: Optional[VLESSKey] = None) -> Dict:
        """
        Получение информации о подключении для клиента.
        
        Returns:
            Dict с информацией для подключения
        """
        if key is None:
            key = self._current_key
        
        if not key:
            return {
                "status": "no_key",
                "message": "Ключ не найден. Попробуйте обновить."
            }
        
        # Парсим VLESS ключ для получения деталей
        # vless://uuid@host:port?params#name
        try:
            from urllib.parse import urlparse, parse_qs, unquote
            
            parsed = urlparse(key.key)
            query_params = parse_qs(parsed.query)
            
            # Извлекаем UUID и хост
            uuid_host = parsed.netloc.split('@')
            if len(uuid_host) != 2:
                raise ValueError("Неверный формат ключа")
            
            uuid = uuid_host[0]
            host_port = uuid_host[1]
            host_port_split = host_port.rsplit(':', 1)
            host = host_port_split[0]
            port = int(host_port_split[1]) if len(host_port_split) > 1 else 443
            
            # Извлекаем параметры
            security = query_params.get('security', ['none'])[0]
            protocol_type = query_params.get('type', ['tcp'])[0]
            sni = query_params.get('sni', [''])[0]
            pbk = query_params.get('pbk', [''])[0]
            sid = query_params.get('sid', [''])[0]
            fp = query_params.get('fp', ['chrome'])[0]
            
            return {
                "status": "ok",
                "key": key.key,
                "location": key.location,
                "updated_at": key.updated_at,
                "uuid": uuid,
                "host": host,
                "port": port,
                "security": security,
                "type": protocol_type,
                "sni": sni,
                "pbk": pbk,
                "sid": sid,
                "fingerprint": fp,
                "traffic_limit": key.traffic_limit
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга ключа: {e}")
            return {
                "status": "parse_error",
                "message": f"Ошибка парсинга: {e}",
                "key": key.key if key else None
            }


# Глобальный экземпляр менеджера
keys_manager = VLESSKeysManager()


async def init_keys_manager() -> bool:
    """Инициализация менеджера и загрузка первого ключа."""
    logger.info("Инициализация менеджера ключей...")
    success = await keys_manager.update_current_key(force=True)
    if success:
        logger.info("✅ Менеджер ключей инициализирован")
    else:
        logger.warning("⚠️ Не удалось загрузить ключи при инициализации")
    return success


async def scheduled_keys_update():
    """
    Фоновая задача для периодического обновления ключей.
    Запускается каждые 12 часов (в 00:00 и 12:00 UTC).
    """
    import asyncio

    while True:
        now = datetime.now()
        # Обновляем каждые 12 часов: в 00:00 и 12:00
        if now.hour < 12:
            next_update = now.replace(hour=12, minute=0, second=0, microsecond=0)
        elif now.hour < 24:
            next_update = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_update = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        sleep_seconds = (next_update - now).total_seconds()

        logger.info(f"Следующее обновление ключей через {sleep_seconds / 3600:.1f} часов")
        await asyncio.sleep(sleep_seconds)

        logger.info("🔄 Автоматическое обновление ключей (каждые 12 часов)...")
        await keys_manager.update_current_key(force=True)
