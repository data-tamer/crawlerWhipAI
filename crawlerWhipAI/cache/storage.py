"""Cache storage backend."""

import logging
import hashlib
import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CacheStorage:
    """SQLite-based cache storage."""

    def __init__(self, db_path: str = ".crawl_cache.db"):
        """Initialize cache storage.

        Args:
            db_path: Path to SQLite database.
        """
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        """Initialize database connection and create tables."""
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL")

        # Create cache table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                url TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP NOT NULL,
                accessed_at TIMESTAMP NOT NULL,
                ttl_hours INTEGER DEFAULT 24
            )
        """)

        await self.db.commit()
        logger.info(f"Cache storage initialized: {self.db_path}")

    async def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached content.

        Args:
            url: URL to retrieve.

        Returns:
            Cached data or None if not found or expired.
        """
        if not self.db:
            return None

        cursor = await self.db.execute(
            "SELECT content, content_hash, metadata, created_at, ttl_hours FROM cache WHERE url = ?",
            (url,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        content, content_hash, metadata_json, created_at, ttl_hours = row

        # Check if expired
        created = datetime.fromisoformat(created_at)
        if datetime.utcnow() - created > timedelta(hours=ttl_hours):
            await self.delete(url)
            return None

        # Update accessed time
        await self.db.execute(
            "UPDATE cache SET accessed_at = ? WHERE url = ?",
            (datetime.utcnow().isoformat(), url)
        )
        await self.db.commit()

        metadata = json.loads(metadata_json) if metadata_json else {}

        return {
            "url": url,
            "content": content,
            "content_hash": content_hash,
            "metadata": metadata,
            "created_at": created_at,
        }

    async def set(
        self,
        url: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_hours: int = 24,
    ) -> None:
        """Set cached content.

        Args:
            url: URL to cache.
            content: Content to cache.
            metadata: Optional metadata.
            ttl_hours: Time-to-live in hours.
        """
        if not self.db:
            return

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        metadata_json = json.dumps(metadata) if metadata else None
        now = datetime.utcnow().isoformat()

        await self.db.execute(
            """
            INSERT OR REPLACE INTO cache
            (url, content_hash, content, metadata, created_at, accessed_at, ttl_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (url, content_hash, content, metadata_json, now, now, ttl_hours)
        )
        await self.db.commit()
        logger.debug(f"Cached: {url} (hash: {content_hash[:8]}...)")

    async def delete(self, url: str) -> None:
        """Delete cached content.

        Args:
            url: URL to delete from cache.
        """
        if not self.db:
            return

        await self.db.execute("DELETE FROM cache WHERE url = ?", (url,))
        await self.db.commit()
        logger.debug(f"Deleted from cache: {url}")

    async def clear(self) -> None:
        """Clear entire cache."""
        if not self.db:
            return

        await self.db.execute("DELETE FROM cache")
        await self.db.commit()
        logger.info("Cache cleared")

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed.
        """
        if not self.db:
            return 0

        cursor = await self.db.execute(
            "SELECT url, created_at, ttl_hours FROM cache"
        )
        rows = await cursor.fetchall()

        removed = 0
        for url, created_at, ttl_hours in rows:
            created = datetime.fromisoformat(created_at)
            if datetime.utcnow() - created > timedelta(hours=ttl_hours):
                await self.delete(url)
                removed += 1

        logger.info(f"Cleanup removed {removed} expired entries")
        return removed

    async def close(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None
            logger.info("Cache storage closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
