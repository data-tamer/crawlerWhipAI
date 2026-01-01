"""Nodriver fallback for heavily protected sites (Cloudflare, etc.)."""

import asyncio
import logging
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Check for nodriver availability
try:
    import nodriver as uc
    HAS_NODRIVER = True
    logger.debug("nodriver available for Cloudflare bypass")
except ImportError:
    HAS_NODRIVER = False
    logger.debug("nodriver not available - install with: pip install nodriver")


async def fetch_with_nodriver(
    url: str,
    timeout: int = 30000,
    wait_for_cf: bool = True,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Fetch a URL using nodriver (undetected Chrome).

    This is used as a fallback for sites with heavy bot protection
    that Playwright cannot bypass.

    Args:
        url: URL to fetch.
        timeout: Page load timeout in milliseconds.
        wait_for_cf: Wait for Cloudflare challenge to complete.

    Returns:
        Tuple of (html, title, description, error).
        On success: (html, title, description, None)
        On error: (None, None, None, error_message)
    """
    if not HAS_NODRIVER:
        return None, None, None, "nodriver not installed"

    browser = None
    try:
        logger.info(f"Using nodriver fallback for: {url}")

        # Launch undetected Chrome
        browser = await uc.start(
            headless=True,
            browser_args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
        )

        # Navigate to URL
        page = await browser.get(url)

        # Wait for Cloudflare challenge if enabled
        if wait_for_cf:
            # Wait for page to stabilize (Cloudflare typically takes 2-5 seconds)
            await asyncio.sleep(3)

            # Check if we're still on a challenge page
            for attempt in range(10):
                title = await page.evaluate("document.title")
                if title and "just a moment" not in title.lower():
                    break
                await asyncio.sleep(1)

        # Wait for page to fully load
        await asyncio.sleep(1)

        # Extract content
        html = await page.evaluate("document.documentElement.outerHTML")
        title = await page.evaluate("document.title")

        # Try to get description
        description = ""
        try:
            desc_result = await page.evaluate(
                "document.querySelector('meta[name=\"description\"]')?.content || ''"
            )
            description = desc_result or ""
        except Exception:
            pass

        logger.info(f"nodriver successfully fetched: {url}")
        return html, title, description, None

    except asyncio.TimeoutError:
        error = f"nodriver timeout after {timeout}ms"
        logger.warning(error)
        return None, None, None, error

    except Exception as e:
        error = f"nodriver error: {str(e)}"
        logger.warning(error)
        return None, None, None, error

    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


async def test_nodriver_available() -> bool:
    """Test if nodriver is available and working."""
    if not HAS_NODRIVER:
        return False

    try:
        browser = await uc.start(headless=True)
        await browser.get("https://example.com")
        browser.stop()
        return True
    except Exception as e:
        logger.warning(f"nodriver test failed: {e}")
        return False
