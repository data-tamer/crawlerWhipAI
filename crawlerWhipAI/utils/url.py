"""URL utilities and normalization."""

import logging
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """Normalize a URL.

    Resolves relative URLs, removes fragments, sorts query parameters, etc.

    Args:
        url: URL to normalize.
        base_url: Base URL for relative resolution.

    Returns:
        Normalized URL.
    """
    if not url:
        return ""

    # Resolve relative URLs
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    # Ensure scheme
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    # Remove fragment
    parsed = parsed._replace(fragment="")

    # Sort query parameters for consistency
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        # Flatten single-value lists
        flat_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        sorted_query = urlencode(sorted(flat_params.items()), doseq=True)
        parsed = parsed._replace(query=sorted_query)

    # Lowercase scheme and netloc
    parsed = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower()
    )

    return urlunparse(parsed)


def get_base_domain(url: str) -> str:
    """Extract base domain from URL.

    Handles special domains like co.uk, com.au, etc.

    Args:
        url: URL to extract domain from.

    Returns:
        Base domain.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Remove www and port
    if domain.startswith("www."):
        domain = domain[4:]
    if ":" in domain:
        domain = domain.split(":")[0]

    # Simple handling for special domains (could be more comprehensive)
    special_suffixes = [".co.uk", ".co.jp", ".com.au", ".co.nz"]
    for suffix in special_suffixes:
        if domain.endswith(suffix):
            parts = domain.replace(suffix, "").split(".")
            if len(parts) > 0:
                return f"{parts[-1]}{suffix}"

    # Regular domain: return last 2 parts
    parts = domain.split(".")
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return domain


def is_internal_url(url: str, base_domain: str) -> bool:
    """Check if URL is internal to a domain.

    Args:
        url: URL to check.
        base_domain: Base domain to compare against.

    Returns:
        True if URL is internal.
    """
    url_domain = get_base_domain(url)
    return url_domain == base_domain or url_domain.endswith(f".{base_domain}")


def get_url_path(url: str) -> str:
    """Extract path from URL.

    Args:
        url: URL to extract path from.

    Returns:
        URL path.
    """
    parsed = urlparse(url)
    return parsed.path or "/"


def validate_url(url: str) -> bool:
    """Validate URL format.

    Args:
        url: URL to validate.

    Returns:
        True if URL is valid.
    """
    try:
        parsed = urlparse(url)
        # Must have scheme and netloc, or at least netloc
        if parsed.scheme and parsed.netloc:
            return parsed.scheme in ("http", "https")
        if parsed.netloc:
            return True
        return False
    except Exception:
        return False


def extract_domain_from_url(url: str) -> str:
    """Extract full domain (with subdomain) from URL.

    Args:
        url: URL to extract domain from.

    Returns:
        Full domain.
    """
    parsed = urlparse(url)
    return parsed.netloc.lower()
