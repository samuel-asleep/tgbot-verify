"""SQLite database implementation (in-memory, no external DB required)

Uses SQLite for data storage - no MySQL server needed.
Data persists in memory only (resets on restart).
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class SQLiteDatabase:
    """SQLite database management class (in-memory)"""

    def __init__(self):
        """Initialize database connection"""
        # Use in-memory database (no file needed)
        self.conn = sqlite3.connect(':memory:', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        logger.info("SQLite in-memory database initialized")
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()

        try:
            # Users table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance INTEGER DEFAULT 1,
                    is_blocked INTEGER DEFAULT 0,
                    invited_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checkin TIMESTAMP NULL
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invited_by ON users(invited_by)")

            # Invitations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inviter_id INTEGER NOT NULL,
                    invitee_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (inviter_id) REFERENCES users(user_id),
                    FOREIGN KEY (invitee_id) REFERENCES users(user_id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inviter ON invitations(inviter_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invitee ON invitations(invitee_id)")

            # Verifications table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    verification_type TEXT NOT NULL,
                    verification_url TEXT,
                    verification_id TEXT,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON verifications(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON verifications(verification_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON verifications(created_at)")

            # Card keys table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS card_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_code TEXT UNIQUE NOT NULL,
                    balance INTEGER NOT NULL,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    expire_at TIMESTAMP NULL,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_key_code ON card_keys(key_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_by ON card_keys(created_by)")

            # Card key usage table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS card_key_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_code TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cku_key_code ON card_key_usage(key_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cku_user_id ON card_key_usage(user_id)")

            self.conn.commit()
            logger.info("SQLite database tables initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.conn.rollback()
            raise

    def create_user(
        self, user_id: int, username: str, full_name: str, invited_by: Optional[int] = None
    ) -> bool:
        """Create new user"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, full_name, invited_by)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, full_name, invited_by),
            )
            self.conn.commit()
            logger.info(f"User created: {user_id} ({username})")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"User already exists: {user_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            self.conn.rollback()
            return False

    def user_exists(self, user_id: int) -> bool:
        """Check if user exists"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT user_id, username, full_name, balance, is_blocked, invited_by, created_at, last_checkin FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def is_user_blocked(self, user_id: int) -> bool:
        """Check if user is blocked"""
        user = self.get_user(user_id)
        return user["is_blocked"] == 1 if user else False

    def get_balance(self, user_id: int) -> int:
        """Get user balance"""
        user = self.get_user(user_id)
        return user["balance"] if user else 0

    def add_balance(self, user_id: int, amount: int) -> bool:
        """Add balance to user"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id),
            )
            self.conn.commit()
            logger.info(f"Added {amount} credits to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add balance: {e}")
            self.conn.rollback()
            return False

    def deduct_balance(self, user_id: int, amount: int) -> bool:
        """Deduct balance from user"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                (amount, user_id, amount),
            )
            if cursor.rowcount == 0:
                logger.warning(f"Insufficient balance for user {user_id}")
                return False
            self.conn.commit()
            logger.info(f"Deducted {amount} credits from user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to deduct balance: {e}")
            self.conn.rollback()
            return False

    def checkin(self, user_id: int, reward: int) -> Optional[str]:
        """Daily check-in"""
        user = self.get_user(user_id)
        if not user:
            return "User not found"

        last_checkin = user["last_checkin"]
        if last_checkin:
            last_checkin_date = datetime.fromisoformat(last_checkin).date()
            today = datetime.now().date()
            if last_checkin_date == today:
                return "Already checked in today"

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET balance = balance + ?, last_checkin = ? WHERE user_id = ?",
                (reward, datetime.now(), user_id),
            )
            self.conn.commit()
            logger.info(f"User {user_id} checked in, received {reward} credits")
            return None
        except Exception as e:
            logger.error(f"Failed to check in: {e}")
            self.conn.rollback()
            return str(e)

    def add_verification(
        self,
        user_id: int,
        verification_type: str,
        verification_url: str,
        status: str,
        result: str,
        verification_id: str = None,
    ) -> bool:
        """Add verification record"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO verifications 
                (user_id, verification_type, verification_url, verification_id, status, result)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, verification_type, verification_url, verification_id, status, result),
            )
            self.conn.commit()
            logger.info(f"Verification record added: {user_id} - {verification_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to add verification record: {e}")
            self.conn.rollback()
            return False

    def get_invite_link(self, user_id: int) -> str:
        """Generate invite link"""
        return f"invite_{user_id}"

    def process_invite(self, inviter_id: int, invitee_id: int, reward: int) -> bool:
        """Process invitation"""
        cursor = self.conn.cursor()
        try:
            # Check if already invited
            cursor.execute(
                "SELECT 1 FROM invitations WHERE inviter_id = ? AND invitee_id = ?",
                (inviter_id, invitee_id),
            )
            if cursor.fetchone():
                return False

            # Add invitation record
            cursor.execute(
                "INSERT INTO invitations (inviter_id, invitee_id) VALUES (?, ?)",
                (inviter_id, invitee_id),
            )

            # Add reward to inviter
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (reward, inviter_id),
            )

            # Update invitee's invited_by
            cursor.execute(
                "UPDATE users SET invited_by = ? WHERE user_id = ?",
                (inviter_id, invitee_id),
            )

            self.conn.commit()
            logger.info(f"Invitation processed: {inviter_id} -> {invitee_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to process invitation: {e}")
            self.conn.rollback()
            return False

    def block_user(self, user_id: int) -> bool:
        """Block user"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            logger.info(f"User blocked: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to block user: {e}")
            self.conn.rollback()
            return False

    def unblock_user(self, user_id: int) -> bool:
        """Unblock user"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            logger.info(f"User unblocked: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unblock user: {e}")
            self.conn.rollback()
            return False

    def get_blacklist(self) -> List[Dict]:
        """Get list of blocked users"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, username, full_name FROM users WHERE is_blocked = 1")
        return [dict(row) for row in cursor.fetchall()]

    def create_card_key(
        self,
        key_code: str,
        balance: int,
        max_uses: int,
        expire_at: Optional[datetime],
        created_by: int,
    ) -> bool:
        """Create card key"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO card_keys (key_code, balance, max_uses, expire_at, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key_code, balance, max_uses, expire_at, created_by),
            )
            self.conn.commit()
            logger.info(f"Card key created: {key_code}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Card key already exists: {key_code}")
            return False
        except Exception as e:
            logger.error(f"Failed to create card key: {e}")
            self.conn.rollback()
            return False

    def use_card_key(self, key_code: str, user_id: int) -> Optional[int]:
        """Use card key"""
        cursor = self.conn.cursor()
        try:
            # Get card key info
            cursor.execute(
                """
                SELECT balance, max_uses, current_uses, expire_at
                FROM card_keys WHERE key_code = ?
                """,
                (key_code,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            key = dict(row)

            # Check expiration
            if key["expire_at"]:
                expire_at = datetime.fromisoformat(key["expire_at"])
                if datetime.now() > expire_at:
                    logger.warning(f"Card key expired: {key_code}")
                    return None

            # Check usage limit
            if key["current_uses"] >= key["max_uses"]:
                logger.warning(f"Card key usage limit reached: {key_code}")
                return None

            # Check if user already used this key
            cursor.execute(
                "SELECT 1 FROM card_key_usage WHERE key_code = ? AND user_id = ?",
                (key_code, user_id),
            )
            if cursor.fetchone():
                logger.warning(f"User already used this key: {user_id} - {key_code}")
                return None

            # Update usage count
            cursor.execute(
                "UPDATE card_keys SET current_uses = current_uses + 1 WHERE key_code = ?",
                (key_code,),
            )

            # Add usage record
            cursor.execute(
                "INSERT INTO card_key_usage (key_code, user_id) VALUES (?, ?)",
                (key_code, user_id),
            )

            # Add balance to user
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (key["balance"], user_id),
            )

            self.conn.commit()
            logger.info(f"Card key used: {key_code} by user {user_id}")
            return key["balance"]

        except Exception as e:
            logger.error(f"Failed to use card key: {e}")
            self.conn.rollback()
            return None

    def list_card_keys(self) -> List[Dict]:
        """List all card keys"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT key_code, balance, max_uses, current_uses, expire_at, created_at
            FROM card_keys ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


# Alias for compatibility
Database = SQLiteDatabase
