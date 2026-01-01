"""Cloudflare detection and bypass utilities."""

import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Cloudflare challenge indicators
CF_CHALLENGE_SELECTORS = [
    "#cf-spinner-please-wait",
    "#cf-spinner-redirecting",
    ".cf-browser-verification",
    "#challenge-running",
    "#challenge-stage",
    "#turnstile-wrapper",
    'iframe[src*="challenges.cloudflare.com"]',
]

CF_CHALLENGE_TITLES = [
    "just a moment",
    "checking your browser",
    "please wait",
    "ddos protection",
    "attention required",
    "cloudflare",
]

CF_CHALLENGE_TEXT = [
    "checking your browser before accessing",
    "please wait while we verify",
    "this process is automatic",
    "ray id:",
    "ddos protection by cloudflare",
    "enable javascript and cookies",
]


async def is_cloudflare_challenge(page: Page) -> bool:
    """
    Detect if the current page is a Cloudflare challenge.

    Args:
        page: Playwright page object.

    Returns:
        True if Cloudflare challenge detected.
    """
    try:
        # Check title
        title = await page.title()
        if title:
            title_lower = title.lower()
            for cf_title in CF_CHALLENGE_TITLES:
                if cf_title in title_lower:
                    logger.debug(f"Cloudflare detected via title: {title}")
                    return True

        # Check for challenge selectors
        for selector in CF_CHALLENGE_SELECTORS:
            try:
                element = await page.query_selector(selector)
                if element:
                    logger.debug(f"Cloudflare detected via selector: {selector}")
                    return True
            except Exception:
                pass

        # Check page content
        content = await page.content()
        content_lower = content.lower()
        for cf_text in CF_CHALLENGE_TEXT:
            if cf_text in content_lower:
                logger.debug(f"Cloudflare detected via content: {cf_text}")
                return True

        return False

    except Exception as e:
        logger.debug(f"Error checking for Cloudflare: {e}")
        return False


async def wait_for_cloudflare(
    page: Page,
    timeout: int = 15000,
    check_interval: float = 0.5,
) -> Tuple[bool, str]:
    """
    Wait for Cloudflare challenge to complete.

    Args:
        page: Playwright page object.
        timeout: Maximum wait time in milliseconds.
        check_interval: Time between checks in seconds.

    Returns:
        Tuple of (success, message).
    """
    start_time = asyncio.get_event_loop().time()
    timeout_seconds = timeout / 1000

    logger.info("Waiting for Cloudflare challenge to complete...")

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time

        if elapsed > timeout_seconds:
            return False, f"Cloudflare challenge timeout after {timeout}ms"

        # Check if challenge is still present
        is_challenge = await is_cloudflare_challenge(page)

        if not is_challenge:
            # Challenge completed, wait a bit for page to stabilize
            await asyncio.sleep(0.5)
            logger.info(f"Cloudflare challenge passed in {elapsed:.1f}s")
            return True, "Challenge completed"

        # Wait before next check
        await asyncio.sleep(check_interval)


async def detect_and_handle_cloudflare(
    page: Page,
    timeout: int = 15000,
    quick_detect: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Detect and handle Cloudflare challenge if present.

    Args:
        page: Playwright page object.
        timeout: Maximum wait time in milliseconds.
        quick_detect: If True, return immediately when Cloudflare is detected
                     without waiting (for fast fallback to nodriver).

    Returns:
        Tuple of (is_blocked, error_message).
        - (False, None) = No Cloudflare or challenge passed
        - (True, "error") = Challenge detected/failed
    """
    # First check if this is a Cloudflare challenge
    is_challenge = await is_cloudflare_challenge(page)

    if not is_challenge:
        return False, None

    # Quick detect mode: return immediately when CF is detected
    # This allows fast fallback to nodriver without waiting 15-20 seconds
    if quick_detect:
        logger.info("Cloudflare challenge detected - skipping wait for fast nodriver fallback")
        return True, "Cloudflare challenge detected (quick mode)"

    # Try to wait for challenge to complete (slow path)
    success, message = await wait_for_cloudflare(page, timeout)

    if success:
        return False, None
    else:
        return True, message


def is_cloudflare_blocked_response(status_code: int, headers: dict) -> bool:
    """
    Check if HTTP response indicates Cloudflare blocking.

    Args:
        status_code: HTTP status code.
        headers: Response headers.

    Returns:
        True if blocked by Cloudflare.
    """
    # Check for Cloudflare challenge status
    if status_code == 403:
        # Check for Cloudflare headers
        cf_mitigated = headers.get("cf-mitigated", "")
        if cf_mitigated == "challenge":
            return True

    if status_code == 503:
        server = headers.get("server", "").lower()
        if "cloudflare" in server:
            return True

    return False


async def quick_cloudflare_check(url: str, timeout: float = 5.0) -> bool:
    """
    Quickly check if a URL is protected by Cloudflare using HTTP HEAD request.

    This is MUCH faster than starting a browser to detect Cloudflare.

    Args:
        url: URL to check.
        timeout: Request timeout in seconds.

    Returns:
        True if Cloudflare protection is detected.
    """
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
            ) as response:
                headers = dict(response.headers)

                # Check for Cloudflare headers
                if is_cloudflare_blocked_response(response.status, headers):
                    logger.info(f"Cloudflare detected via HTTP check: {url}")
                    return True

                # Check for Cloudflare server header
                server = headers.get("server", "").lower()
                if "cloudflare" in server:
                    # Site uses Cloudflare but might not be blocking
                    # Check for challenge cookie
                    cf_ray = headers.get("cf-ray")
                    if cf_ray and response.status in (403, 503):
                        logger.info(f"Cloudflare challenge detected: {url}")
                        return True

        return False

    except Exception as e:
        logger.debug(f"HTTP check failed for {url}: {e}")
        return False
