import sqlite3
import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DATABASE = "steashub.db"


@contextmanager
def get_db_connection():
    """Контекстный менеджер для подключения к БД."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Инициализация таблиц базы данных."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin INTEGER DEFAULT 0
            )
        """)
        
        # Таблица подписок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_type TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                devices_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица платежей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL NOT NULL,
                plan_type TEXT,
                status TEXT DEFAULT 'pending',
                payment_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица репортов серверов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server_region TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_report_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица статистики серверов (для будущей проверки задержки)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_region TEXT NOT NULL,
                ping_ms INTEGER,
                speed_mbps INTEGER,
                is_online INTEGER DEFAULT 1,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()


# ==================== USERS ====================

def add_user(user_id: int, username: str, first_name: str, last_name: Optional[str] = None):
    """Добавить или обновить пользователя."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, created_at)
            VALUES (?, ?, ?, ?, COALESCE(
                (SELECT created_at FROM users WHERE user_id = ?), 
                CURRENT_TIMESTAMP
            ))
        """, (user_id, username, first_name, last_name, user_id))
        conn.commit()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    """Получить пользователя по ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()


def set_admin(user_id: int, is_admin: bool = True):
    """Назначить или снять права администратора."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", 
                      (1 if is_admin else 0, user_id))
        conn.commit()


def is_admin(user_id: int) -> bool:
    """Проверить права администратора."""
    user = get_user(user_id)
    return user and user['is_admin'] == 1


# ==================== SUBSCRIPTIONS ====================

def add_subscription(user_id: int, plan_type: str, months: int = 1, devices_count: int = 0):
    """Добавить подписку пользователю."""
    expires_at = datetime.datetime.now() + datetime.timedelta(days=30 * months)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscriptions (user_id, plan_type, status, expires_at, devices_count)
            VALUES (?, ?, 'active', ?, ?)
        """, (user_id, plan_type, expires_at, devices_count))
        conn.commit()
        return cursor.lastrowid


def get_active_subscription(user_id: int) -> Optional[sqlite3.Row]:
    """Получить активную подписку пользователя."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM subscriptions 
            WHERE user_id = ? AND status = 'active' AND expires_at > CURRENT_TIMESTAMP
            ORDER BY expires_at DESC
            LIMIT 1
        """, (user_id,))
        return cursor.fetchone()


def has_active_subscription(user_id: int) -> bool:
    """Проверить наличие активной подписки."""
    return get_active_subscription(user_id) is not None


def get_user_subscriptions(user_id: int) -> List[sqlite3.Row]:
    """Получить все подписки пользователя."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM subscriptions WHERE user_id = ?
            ORDER BY started_at DESC
        """, (user_id,))
        return cursor.fetchall()


# ==================== PAYMENTS ====================

def add_payment(user_id: int, amount: float, plan_type: str, payment_method: str = "sbp"):
    """Добавить платёж."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO payments (user_id, amount, plan_type, status, payment_method)
            VALUES (?, ?, ?, 'pending', ?)
        """, (user_id, amount, plan_type, payment_method))
        conn.commit()
        return cursor.lastrowid


def confirm_payment(payment_id: int):
    """Подтвердить платёж."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE payments 
            SET status = 'paid', paid_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (payment_id,))
        conn.commit()


def get_revenue_by_period(days: int = 30) -> float:
    """Получить доход за период (в днях)."""
    date_from = datetime.datetime.now() - datetime.timedelta(days=days)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM payments
            WHERE status = 'paid' AND paid_at >= ?
        """, (date_from,))
        result = cursor.fetchone()
        return result['total'] if result else 0.0


def get_revenue_stats() -> Dict[str, float]:
    """Получить статистику доходов по периодам."""
    return {
        "day": get_revenue_by_period(1),
        "week": get_revenue_by_period(7),
        "month": get_revenue_by_period(30),
        "year": get_revenue_by_period(365),
        "all": get_revenue_by_period(99999)
    }


def get_payments_by_period(days: int = 30) -> List[sqlite3.Row]:
    """Получить все платежи за период."""
    date_from = datetime.datetime.now() - datetime.timedelta(days=days)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, u.username, u.first_name
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'paid' AND p.paid_at >= ?
            ORDER BY p.paid_at DESC
        """, (date_from,))
        return cursor.fetchall()


# ==================== SERVER REPORTS ====================

def can_report_server(user_id: int) -> tuple[bool, str]:
    """
    Проверить возможность отправки репорта.
    Возвращает (можно_ли_репортить, причина_если_нельзя).
    """
    # Проверка активной подписки
    if not has_active_subscription(user_id):
        return False, "Требуется активная подписка"
    
    # Проверка таймаута 15 минут
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT created_at FROM server_reports
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        result = cursor.fetchone()
        
        if result:
            last_report = datetime.datetime.fromisoformat(result['created_at'])
            time_diff = datetime.datetime.now() - last_report
            if time_diff < datetime.timedelta(minutes=15):
                remaining = 15 - time_diff.total_seconds() / 60
                return False, f"Подождите {int(remaining)} мин."
    
    return True, ""


def add_server_report(user_id: int, server_region: str, issue_type: str, description: str = ""):
    """Добавить репорт сервера."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_reports (user_id, server_region, issue_type, description, status)
            VALUES (?, ?, ?, ?, 'new')
        """, (user_id, server_region, issue_type, description))
        conn.commit()
        return cursor.lastrowid


def get_server_reports(limit: int = 50) -> List[sqlite3.Row]:
    """Получить последние репорты серверов."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.username, u.first_name
            FROM server_reports r
            LEFT JOIN users u ON r.user_id = u.user_id
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()


def update_report_status(report_id: int, status: str):
    """Обновить статус репорта."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE server_reports SET status = ? WHERE id = ?", (status, report_id))
        conn.commit()


# ==================== STATISTICS ====================

def get_total_users() -> int:
    """Получить общее количество пользователей."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        return cursor.fetchone()['count']


def get_active_subscribers() -> int:
    """Получить количество активных подписчиков."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM subscriptions
            WHERE status = 'active' AND expires_at > CURRENT_TIMESTAMP
        """)
        return cursor.fetchone()['count']


def get_subscribers_by_plan() -> Dict[str, int]:
    """Получить количество подписчиков по тарифам."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_type, COUNT(DISTINCT user_id) as count
            FROM subscriptions
            WHERE status = 'active' AND expires_at > CURRENT_TIMESTAMP
            GROUP BY plan_type
        """)
        return {row['plan_type']: row['count'] for row in cursor.fetchall()}


def get_all_stats() -> Dict[str, Any]:
    """Получить всю статистику для админ-панели."""
    return {
        "total_users": get_total_users(),
        "active_subscribers": get_active_subscribers(),
        "revenue": get_revenue_stats(),
        "subscribers_by_plan": get_subscribers_by_plan()
    }


# ==================== SERVER STATS (future) ====================

def add_server_stat(server_region: str, ping_ms: Optional[int] = None, 
                    speed_mbps: Optional[int] = None, is_online: bool = True):
    """Добавить статистику сервера."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO server_stats (server_region, ping_ms, speed_mbps, is_online)
            VALUES (?, ?, ?, ?)
        """, (server_region, ping_ms, speed_mbps, 1 if is_online else 0))
        conn.commit()


def get_server_avg_stats() -> List[sqlite3.Row]:
    """Получить среднюю статистику по серверам."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT server_region, 
                   AVG(ping_ms) as avg_ping,
                   AVG(speed_mbps) as avg_speed,
                   SUM(is_online) * 1.0 / COUNT(*) as online_ratio
            FROM server_stats
            WHERE checked_at >= datetime('now', '-1 hour')
            GROUP BY server_region
        """)
        return cursor.fetchall()
