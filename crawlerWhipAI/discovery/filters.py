"""URL filtering for deep crawling."""

import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


class URLFilter(ABC):
    """Base class for URL filtering."""

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Check if URL matches filter.

        Args:
            url: URL to check.

        Returns:
            True if URL passes filter.
        """
        pass


class PatternFilter(URLFilter):
    """Filters URLs by glob or regex patterns."""

    def __init__(self, patterns: List[str], regex: bool = False):
        """Initialize pattern filter.

        Args:
            patterns: List of patterns to match.
            regex: Whether patterns are regex (True) or glob (False).
        """
        self.patterns = patterns
        self.regex = regex
        if regex:
            self.compiled = [re.compile(p) for p in patterns]

    def matches(self, url: str) -> bool:
        """Check if URL matches any pattern.

        Args:
            url: URL to check.

        Returns:
            True if matches.
        """
        if self.regex:
            return any(p.search(url) for p in self.compiled)
        else:
            # Glob-style matching
            return any(self._glob_match(url, p) for p in self.patterns)

    def _glob_match(self, url: str, pattern: str) -> bool:
        """Simple glob-style matching.

        Args:
            url: URL to match.
            pattern: Glob pattern.

        Returns:
            True if matches.
        """
        # Convert glob to regex
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
        return re.match(regex_pattern, url) is not None


class DomainFilter(URLFilter):
    """Filters URLs by domain."""

    def __init__(self, allowed_domains: List[str] = None, blocked_domains: List[str] = None):
        """Initialize domain filter.

        Args:
            allowed_domains: List of allowed domains (if set, only these are allowed).
            blocked_domains: List of blocked domains.
        """
        self.allowed_domains = allowed_domains or []
        self.blocked_domains = blocked_domains or []

    def matches(self, url: str) -> bool:
        """Check if URL domain is allowed.

        Args:
            url: URL to check.

        Returns:
            True if allowed.
        """
        # Extract domain
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()

        # Check blocked
        if self.blocked_domains:
            for blocked in self.blocked_domains:
                if domain.endswith(blocked):
                    return False

        # Check allowed
        if self.allowed_domains:
            for allowed in self.allowed_domains:
                if domain.endswith(allowed):
                    return True
            return False

        return True


class ExtensionFilter(URLFilter):
    """Filters URLs by file extension."""

    # Extensions to skip
    SKIP_EXTENSIONS = {
        ".pdf", ".zip", ".exe", ".dmg", ".iso", ".tar", ".gz",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
        ".mp4", ".avi", ".mov", ".mkv", ".flv",
        ".mp3", ".wav", ".flac", ".aac",
    }

    def __init__(self, allowed_extensions: List[str] = None, skip_extensions: List[str] = None):
        """Initialize extension filter.

        Args:
            allowed_extensions: List of allowed extensions (if set, only these).
            skip_extensions: List of extensions to skip.
        """
        self.allowed_extensions = set(e.lower() for e in allowed_extensions or [])
        self.skip_extensions = set(e.lower() for e in skip_extensions or self.SKIP_EXTENSIONS)

    def matches(self, url: str) -> bool:
        """Check if URL extension is allowed.

        Args:
            url: URL to check.

        Returns:
            True if allowed.
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.lower()

        # Get extension
        ext = ""
        if "." in path.split("/")[-1]:
            ext = "." + path.split(".")[-1]

        # Check if in skip list
        if ext in self.skip_extensions:
            return False

        # Check if in allowed list (if set)
        if self.allowed_extensions:
            return ext in self.allowed_extensions

        return True


class DepthFilter(URLFilter):
    """Filters URLs by path depth."""

    def __init__(self, max_depth: int = 5):
        """Initialize depth filter.

        Args:
            max_depth: Maximum path depth.
        """
        self.max_depth = max_depth

    def matches(self, url: str) -> bool:
        """Check if URL depth is within limit.

        Args:
            url: URL to check.

        Returns:
            True if within limit.
        """
        from urllib.parse import urlparse
        path = urlparse(url).path
        depth = len([p for p in path.split("/") if p])
        return depth <= self.max_depth


class FilterChain(URLFilter):
    """Applies multiple URL filters."""

    def __init__(self, filters: List[URLFilter]):
        """Initialize filter chain.

        Args:
            filters: List of filters to apply.
        """
        self.filters = filters

    def matches(self, url: str) -> bool:
        """Check if URL passes all filters.

        Args:
            url: URL to check.

        Returns:
            True if passes all filters.
        """
        return all(f.matches(url) for f in self.filters)
