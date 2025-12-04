"""Robots.txt parsing and compliance."""

import logging
import aiohttp
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger(__name__)


class RobotsParser:
    """Parses and checks robots.txt compliance."""

    def __init__(self, timeout_seconds: float = 2.0):
        """Initialize parser.

        Args:
            timeout_seconds: Timeout for fetching robots.txt.
        """
        self.timeout_seconds = timeout_seconds
        self._cache = {}

    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """Check if URL is allowed by robots.txt.

        Args:
            url: URL to check.
            user_agent: User agent string.

        Returns:
            True if allowed, False if explicitly blocked.
        """
        # Parse URL
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or "/"

        # Get robots.txt
        robots_content = await self._fetch_robots_txt(domain)
        if not robots_content:
            # If can't fetch, assume allowed
            return True

        # Check rules
        return self._check_rules(robots_content, path, user_agent)

    async def _fetch_robots_txt(self, domain: str) -> Optional[str]:
        """Fetch robots.txt from domain.

        Args:
            domain: Domain URL.

        Returns:
            Robots.txt content or None if not found.
        """
        # Check cache
        if domain in self._cache:
            return self._cache[domain]

        robots_url = f"{domain}/robots.txt"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    robots_url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        self._cache[domain] = content
                        logger.debug(f"Fetched robots.txt from {domain}")
                        return content
                    else:
                        self._cache[domain] = None
                        return None
        except Exception as e:
            logger.debug(f"Error fetching robots.txt: {str(e)}")
            self._cache[domain] = None
            return None

    def _check_rules(self, robots_content: str, path: str, user_agent: str) -> bool:
        """Check if path is allowed by robots rules.

        Args:
            robots_content: robots.txt content.
            path: Path to check.
            user_agent: User agent string.

        Returns:
            True if allowed.
        """
        lines = robots_content.split("\n")
        current_user_agent = None
        disallow_rules = []

        for line in lines:
            # Remove comments
            if "#" in line:
                line = line[:line.index("#")]

            line = line.strip()
            if not line:
                continue

            if line.lower().startswith("user-agent:"):
                current_user_agent = line.split(":", 1)[1].strip().lower()
            elif line.lower().startswith("disallow:"):
                disallow_path = line.split(":", 1)[1].strip()

                # Check if rule applies to this user agent
                if current_user_agent in (user_agent.lower(), "*"):
                    disallow_rules.append(disallow_path)

        # Check path against disallow rules
        for disallow in disallow_rules:
            if not disallow:
                # Empty disallow means allow all
                continue
            if path.startswith(disallow):
                logger.warning(f"Path {path} blocked by robots.txt: {disallow}")
                return False

        return True

    def clear_cache(self) -> None:
        """Clear robots.txt cache."""
        self._cache.clear()
        logger.debug("Robots.txt cache cleared")
