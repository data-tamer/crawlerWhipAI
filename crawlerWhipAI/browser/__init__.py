"""Browser management components."""

from .manager import BrowserManager
from .stealth import get_stealth_scripts, get_realistic_user_agent, get_stealth_headers
from .cloudflare import (
    is_cloudflare_challenge,
    wait_for_cloudflare,
    detect_and_handle_cloudflare,
    is_cloudflare_blocked_response,
    quick_cloudflare_check,
)
from .nodriver_fallback import fetch_with_nodriver, HAS_NODRIVER
from .binary_download import (
    download_binary_with_nodriver,
    download_pdf_with_cloudflare_bypass,
)

__all__ = [
    "BrowserManager",
    "get_stealth_scripts",
    "get_realistic_user_agent",
    "get_stealth_headers",
    "is_cloudflare_challenge",
    "wait_for_cloudflare",
    "detect_and_handle_cloudflare",
    "is_cloudflare_blocked_response",
    "quick_cloudflare_check",
    "fetch_with_nodriver",
    "HAS_NODRIVER",
    "download_binary_with_nodriver",
    "download_pdf_with_cloudflare_bypass",
]
