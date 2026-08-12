import sqlite3
import json
import threading
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

class Database:
    """Thread-safe SQLite database manager for the userbot, providing asynchronous APIs."""

    def __init__(self, db_path: str = "userbot.db") -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 1. settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    btc_address TEXT,
                    eth_address TEXT,
                    ltc_address TEXT,
                    fee_percentage TEXT DEFAULT '3.0',
                    min_fee TEXT DEFAULT '0.0',
                    tos_text TEXT,
                    group_naming_template TEXT DEFAULT 'MM • Deal #{deal_id}',
                    owner_id INTEGER,
                    daily_group_id INTEGER,
                    daily_group_date TEXT
                )
            """)
            
            # Migration: check and add daily_group columns if they don't exist in older databases
            cursor.execute("PRAGMA table_info(settings)")
            columns = [col[1] for col in cursor.fetchall()]
            if "daily_group_id" not in columns:
                cursor.execute("ALTER TABLE settings ADD COLUMN daily_group_id INTEGER")
            if "daily_group_date" not in columns:
                cursor.execute("ALTER TABLE settings ADD COLUMN daily_group_date TEXT")
            
            # 2. deals table (not UNIQUE on chat_id to allow reuse of group chats for subsequent deals)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    amount TEXT DEFAULT '0.00',
                    fee TEXT DEFAULT '0.00',
                    participants TEXT, -- Stored as JSON string
                    funds_received INTEGER DEFAULT 0,
                    closed_at TEXT
                )
            """)
            
            # Database migration: remove UNIQUE constraint from chat_id if it exists in older databases
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='deals'")
            row = cursor.fetchone()
            if row and "UNIQUE" in row[0]:
                cursor.execute("ALTER TABLE deals RENAME TO deals_old")
                cursor.execute("""
                    CREATE TABLE deals (
                        deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        amount TEXT DEFAULT '0.00',
                        fee TEXT DEFAULT '0.00',
                        participants TEXT,
                        funds_received INTEGER DEFAULT 0,
                        closed_at TEXT
                    )
                """)
                cursor.execute("""
                    INSERT INTO deals (deal_id, chat_id, created_at, status, amount, fee, participants, funds_received, closed_at)
                    SELECT deal_id, chat_id, created_at, status, amount, fee, participants, funds_received, closed_at FROM deals_old
                """)
                cursor.execute("DROP TABLE deals_old")
            
            # 3. blocked_users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    blocked_at TEXT NOT NULL
                )
            """)
            
            # 4. deal_events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deal_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
                )
            """)
            
            conn.commit()
            conn.close()

    def _seed_settings(self, default_owner_id: int) -> None:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM settings WHERE id = 1")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO settings (id, fee_percentage, min_fee, tos_text, group_naming_template, owner_id)
                    VALUES (1, '3.0', '0.0', 'Default Terms of Service. Configure using .settos <text>', 'MM • Deal #{deal_id}', ?)
                """, (default_owner_id,))
                conn.commit()
            conn.close()

    async def seed_settings(self, default_owner_id: int) -> None:
        await asyncio.to_thread(self._seed_settings, default_owner_id)

    # --- Settings Methods ---

    def _get_settings(self) -> Dict[str, Any]:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM settings WHERE id = 1")
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else {}

    async def get_settings(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self._get_settings)

    def _update_settings(self, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(1)  # for the id = 1 condition
        query = f"UPDATE settings SET {', '.join(fields)} WHERE id = ?"
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            conn.close()

    async def update_settings(self, **kwargs: Any) -> None:
        await asyncio.to_thread(self._update_settings, kwargs)

    # --- Deals Methods ---

    def _create_deal(self, chat_id: int, participants: List[str]) -> int:
        utc_now = datetime.now(timezone.utc).isoformat()
        participants_json = json.dumps(participants)
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deals (chat_id, created_at, status, amount, fee, participants, funds_received)
                VALUES (?, ?, 'active', '0.00', '0.00', ?, 0)
            """, (chat_id, utc_now, participants_json))
            deal_id = cursor.lastrowid
            
            # Log initial creation event
            cursor.execute("""
                INSERT INTO deal_events (deal_id, event_type, event_data, created_at)
                VALUES (?, 'created', ?, ?)
            """, (deal_id, f"Deal created for chat {chat_id} with participants: {', '.join(participants)}", utc_now))
            
            conn.commit()
            conn.close()
            return deal_id or 0

    async def create_deal(self, chat_id: int, participants: List[str]) -> int:
        return await asyncio.to_thread(self._create_deal, chat_id, participants)

    def _get_deal(self, chat_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM deals WHERE chat_id = ? AND status = 'active' ORDER BY deal_id DESC LIMIT 1", (chat_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None

    async def get_deal(self, chat_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_deal, chat_id)

    def _get_deal_by_id(self, deal_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None

    async def get_deal_by_id(self, deal_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_deal_by_id, deal_id)

    def _update_deal(self, deal_id: int, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(deal_id)
        query = f"UPDATE deals SET {', '.join(fields)} WHERE deal_id = ?"
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            conn.close()

    async def update_deal(self, deal_id: int, **kwargs: Any) -> None:
        await asyncio.to_thread(self._update_deal, deal_id, kwargs)

    def _close_deal(self, deal_id: int) -> None:
        utc_now = datetime.now(timezone.utc).isoformat()
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE deals SET status = 'closed', closed_at = ? WHERE deal_id = ?
            """, (utc_now, deal_id))
            
            # Log closure event
            cursor.execute("""
                INSERT INTO deal_events (deal_id, event_type, event_data, created_at)
                VALUES (?, 'closed', 'Deal safely closed.', ?)
            """, (deal_id, utc_now))
            
            conn.commit()
            conn.close()

    async def close_deal(self, deal_id: int) -> None:
        await asyncio.to_thread(self._close_deal, deal_id)

    # --- Blocked Users Methods ---

    def _add_blocked_user(self, user_id: int, username: Optional[str]) -> None:
        utc_now = datetime.now(timezone.utc).isoformat()
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO blocked_users (user_id, username, blocked_at)
                VALUES (?, ?, ?)
            """, (user_id, username, utc_now))
            conn.commit()
            conn.close()

    async def add_blocked_user(self, user_id: int, username: Optional[str]) -> None:
        await asyncio.to_thread(self._add_blocked_user, user_id, username)

    def _is_user_blocked(self, user_id: int) -> bool:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            return row is not None

    async def is_user_blocked(self, user_id: int) -> bool:
        return await asyncio.to_thread(self._is_user_blocked, user_id)

    # --- Event Logging Methods ---

    def _log_deal_event(self, deal_id: int, event_type: str, event_data: str) -> None:
        utc_now = datetime.now(timezone.utc).isoformat()
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deal_events (deal_id, event_type, event_data, created_at)
                VALUES (?, ?, ?, ?)
            """, (deal_id, event_type, event_data, utc_now))
            conn.commit()
            conn.close()

    async def log_deal_event(self, deal_id: int, event_type: str, event_data: str) -> None:
        await asyncio.to_thread(self._log_deal_event, deal_id, event_type, event_data)

    # --- Stats Methods ---

    def _get_stats(self) -> Tuple[int, int]:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM deals")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM deals WHERE status = 'active'")
            active = cursor.fetchone()[0]
            conn.close()
            return total, active

    async def get_stats(self) -> Tuple[int, int]:
        return await asyncio.to_thread(self._get_stats)

    def _get_all_deals(self) -> List[Dict[str, Any]]:
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM deals ORDER BY deal_id DESC")
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    async def get_all_deals(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_all_deals)

