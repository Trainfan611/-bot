"""
Модуль для загрузки VPN конфигов из репозитория:
https://github.com/igareck/vpn-configs-for-russia
Файл: BLACK_VLESS_RUS_mobile.txt
"""

import aiohttp
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger("BlackVLESSKeys")

# URL с конфигами
GITHUB_RAW_URL = "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"

# Паттерн для VLESS конфигов
VLESS_PATTERN = r'vless://[^\s\r\n]+'


@dataclass
class VLESSConfig:
    """Класс для хранения VLESS конфига."""
    config: str
    index: int
    loaded_at: datetime

    @property
    def is_valid(self) -> bool:
        """Проверка валидности конфига."""
        return self.config.startswith("vless://")


class BlackVLESSKeysManager:
    """Менеджер для управления пулом VLESS конфигов."""

    def __init__(self):
        self._configs: List[VLESSConfig] = []
        self._current_config: Optional[VLESSConfig] = None
        self._last_update: Optional[datetime] = None
        self._update_interval = timedelta(hours=12)
        self._total_configs: int = 0

    async def fetch_configs(self) -> List[str]:
        """
        Загрузка конфигов из GitHub.
        Возвращает список VLESS строк.
        """
        configs = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GITHUB_RAW_URL, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка загрузки файла: {response.status}")
                        return configs

                    content = await response.text()

                    # Извлекаем все VLESS конфиги
                    import re
                    vless_matches = re.findall(VLESS_PATTERN, content)

                    # Очищаем от лишних символов
                    for config in vless_matches:
                        clean_config = config.strip().rstrip('\r\n')
                        if clean_config.startswith('vless://'):
                            configs.append(clean_config)

                    logger.info(f"Загружено конфигов: {len(configs)}")
                    self._total_configs = len(configs)

        except Exception as e:
            logger.error(f"Ошибка при загрузке конфигов: {e}")

        return configs

    async def update_configs(self, force: bool = False) -> bool:
        """
        Обновление пула конфигов.

        Args:
            force: Принудительное обновление

        Returns:
            True если успешно обновлено
        """
        # Проверяем необходимость обновления
        if not force and self._configs and self._last_update:
            if datetime.now() - self._last_update < self._update_interval:
                logger.info("Конфиги ещё актуальны, обновление не требуется")
                return True

        raw_configs = await self.fetch_configs()

        if not raw_configs:
            logger.warning("Не найдено действительных конфигов")
            return False

        # Создаём объекты конфигов
        self._configs = [
            VLESSConfig(config=cfg, index=i, loaded_at=datetime.now())
            for i, cfg in enumerate(raw_configs, 1)
        ]
        self._last_update = datetime.now()

        # Выбираем случайный конфиг как текущий
        self._current_config = random.choice(self._configs)

        logger.info(f"✅ Загружено {len(self._configs)} конфигов, выбран индекс {self._current_config.index}")
        return True

    def get_random_config(self) -> Optional[VLESSConfig]:
        """Получение случайного конфига из пула."""
        if not self._configs:
            return None

        new_config = random.choice(self._configs)
        # Убедимся, что это не тот же самый конфиг (если есть выбор)
        if len(self._configs) > 1 and self._current_config:
            attempts = 0
            while new_config.config == self._current_config.config and attempts < 10:
                new_config = random.choice(self._configs)
                attempts += 1

        self._current_config = new_config
        return new_config

    def get_current_config(self) -> Optional[VLESSConfig]:
        """Получение текущего конфига."""
        return self._current_config

    @property
    def configs_count(self) -> int:
        """Общее количество загруженных конфигов."""
        return len(self._configs)

    @property
    def total_available(self) -> int:
        """Общее количество доступных конфигов (из файла)."""
        return self._total_configs

    @property
    def last_update(self) -> Optional[datetime]:
        """Время последнего обновления."""
        return self._last_update

    @property
    def is_expired(self) -> bool:
        """Проверка, устарели ли конфиги."""
        if not self._configs or not self._last_update:
            return True
        return datetime.now() - self._last_update >= self._update_interval

    def parse_config(self, config: Optional[VLESSConfig] = None) -> Dict:
        """
        Парсинг VLESS конфига для получения деталей.

        Returns:
            Dict с информацией о подключении
        """
        if config is None:
            config = self._current_config

        if not config:
            return {
                "status": "no_config",
                "message": "Конфиг не найден. Нажмите 'Обновить'."
            }

        try:
            from urllib.parse import urlparse, parse_qs, unquote

            parsed = urlparse(config.config)
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

            # Извлекаем имя конфига (фрагмент после #)
            config_name = unquote(parsed.fragment) if parsed.fragment else f"Config #{config.index}"

            return {
                "status": "ok",
                "config": config.config,
                "index": config.index,
                "total": self._total_configs,
                "name": config_name,
                "uuid": uuid,
                "host": host,
                "port": port,
                "security": security,
                "type": protocol_type,
                "sni": sni,
                "pbk": pbk,
                "sid": sid,
                "fingerprint": fp,
                "loaded_at": config.loaded_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Ошибка парсинга конфига: {e}")
            return {
                "status": "parse_error",
                "message": f"Ошибка парсинга: {e}",
                "config": config.config if config else None,
                "index": config.index if config else 0
            }


# Глобальный экземпляр
keys_manager = BlackVLESSKeysManager()


async def init_keys_manager() -> bool:
    """Инициализация менеджера и загрузка конфигов."""
    logger.info("Инициализация BlackVLESS менеджера конфигов...")
    success = await keys_manager.update_configs(force=True)
    if success:
        logger.info(f"✅ BlackVLESS менеджер инициализирован ({keys_manager.configs_count} конфигов)")
    else:
        logger.warning("⚠️ Не удалось загрузить конфиги при инициализации")
    return success


async def scheduled_keys_update():
    """
    Фоновая задача для периодического обновления конфигов.
    Запускается каждые 12 часов.
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

        logger.info(f"Следующее обновление BlackVLESS конфигов через {sleep_seconds / 3600:.1f} часов")
        await asyncio.sleep(sleep_seconds)

        logger.info("🔄 Автоматическое обновление BlackVLESS конфигов...")
        await keys_manager.update_configs(force=True)
