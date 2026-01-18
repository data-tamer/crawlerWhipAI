"""Binary file download with Cloudflare bypass using nodriver."""

import asyncio
import logging
import base64
from pathlib import Path
from typing import Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# Check for nodriver availability
try:
    import nodriver as uc
    HAS_NODRIVER = True
except ImportError:
    HAS_NODRIVER = False


async def download_binary_with_nodriver(
    url: str,
    output_path: str,
    timeout: int = 300,
    headless: bool = False,  # Default to headed mode for better Cloudflare bypass
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Download a binary file (PDF, etc.) using nodriver to bypass Cloudflare.

    Uses nodriver's undetected Chrome to navigate to the URL, bypass any
    Cloudflare challenges, then fetch the binary content via JavaScript.

    Args:
        url: URL to download from.
        output_path: Local file path to save the downloaded file.
        timeout: Download timeout in seconds.
        headless: Run browser in headless mode (False recommended for Cloudflare).
        progress_callback: Optional async/sync callback for progress updates.

    Returns:
        Tuple of (success: bool, error_message: Optional[str]).
    """
    if not HAS_NODRIVER:
        return False, "nodriver not installed - install with: pip install nodriver"

    browser = None

    async def report_progress(message: str) -> None:
        """Report progress via callback if provided."""
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(message)
            else:
                progress_callback(message)

    try:
        await report_progress("Starting browser for Cloudflare bypass...")
        logger.info(f"Using nodriver to download: {url}")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Launch undetected Chrome with new headless mode for better Cloudflare bypass
        # The new headless mode (--headless=new) is more like headed mode
        browser_args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-software-rasterizer",
        ]

        # Use new headless mode if running headless (better Cloudflare bypass)
        if headless:
            browser_args.append("--headless=new")

        browser = await uc.start(
            headless=False,  # We handle headless via args for new mode
            browser_args=browser_args,
        )

        await report_progress("Navigating to URL...")

        # Navigate to URL
        page = await browser.get(url)

        # Wait for Cloudflare challenge to complete
        await report_progress("Waiting for Cloudflare challenge...")
        await asyncio.sleep(8)  # Give more time for initial challenge

        # Check if we're still on a challenge page
        cf_passed = False
        for attempt in range(45):  # Extended wait time
            try:
                title = await page.evaluate("document.title")
                current_url = await page.evaluate("window.location.href")

                # Check if we're past Cloudflare
                if title and "just a moment" not in title.lower() and "checking" not in title.lower():
                    logger.info(f"Cloudflare challenge passed after {attempt + 8}s, title: {title}")
                    cf_passed = True
                    break

                # Also check if we've been redirected to the actual content
                if current_url and url in current_url:
                    # Try to detect if content is loaded
                    content_type = await page.evaluate("document.contentType || ''")
                    if content_type and 'pdf' in content_type.lower():
                        logger.info(f"PDF content detected, challenge likely passed")
                        cf_passed = True
                        break

            except Exception as e:
                logger.debug(f"Error checking page state: {e}")

            logger.debug(f"Waiting for Cloudflare challenge... attempt {attempt + 1}/45")
            await asyncio.sleep(1)

        if not cf_passed:
            logger.warning("Cloudflare challenge may still be active, attempting download anyway")

        await report_progress("Fetching binary content...")

        # Add small delay to ensure page is stable
        await asyncio.sleep(2)

        # Fetch the binary content using JavaScript fetch API
        # This uses the browser's cookies/session after Cloudflare bypass
        binary_content = await page.evaluate('''
            async () => {
                try {
                    // First check if this is a PDF viewer page
                    const embedPdf = document.querySelector('embed[type="application/pdf"]');
                    const objectPdf = document.querySelector('object[type="application/pdf"]');

                    // Get the actual URL to fetch
                    let fetchUrl = window.location.href;
                    if (embedPdf && embedPdf.src) {
                        fetchUrl = embedPdf.src;
                    } else if (objectPdf && objectPdf.data) {
                        fetchUrl = objectPdf.data;
                    }

                    const response = await fetch(fetchUrl, {
                        method: 'GET',
                        credentials: 'include',
                        cache: 'no-cache',
                        headers: {
                            'Accept': 'application/pdf,*/*'
                        }
                    });

                    if (!response.ok) {
                        return { error: `HTTP ${response.status}: ${response.statusText}` };
                    }

                    const contentType = response.headers.get('content-type') || '';
                    const blob = await response.blob();

                    if (blob.size === 0) {
                        return { error: 'Empty response body' };
                    }

                    const reader = new FileReader();

                    return new Promise((resolve) => {
                        reader.onloadend = () => {
                            const base64 = reader.result.split(',')[1] || reader.result;
                            resolve({
                                success: true,
                                data: base64,
                                contentType: contentType,
                                size: blob.size
                            });
                        };
                        reader.onerror = () => {
                            resolve({ error: 'Failed to read blob' });
                        };
                        reader.readAsDataURL(blob);
                    });
                } catch (e) {
                    return { error: e.message || 'Unknown fetch error' };
                }
            }
        ''')

        if not binary_content:
            return False, "No response from page"

        if 'error' in binary_content:
            return False, binary_content['error']

        if not binary_content.get('success') or not binary_content.get('data'):
            return False, "Failed to fetch binary content"

        await report_progress("Saving file...")

        # Decode base64 and save to file
        content = base64.b64decode(binary_content['data'])

        with open(output_path, 'wb') as f:
            f.write(content)

        size_mb = len(content) / (1024 * 1024)
        await report_progress(f"Downloaded: {size_mb:.1f} MB")

        logger.info(f"Successfully downloaded {url} to {output_path} ({len(content)} bytes)")
        return True, None

    except asyncio.TimeoutError:
        error = f"Timeout after {timeout}s"
        logger.warning(error)
        return False, error

    except Exception as e:
        error = f"Download error: {str(e)}"
        logger.error(error)
        return False, error

    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


async def download_pdf_with_cloudflare_bypass(
    url: str,
    output_path: str,
    timeout: int = 300,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Download a PDF file with Cloudflare bypass.

    This is a convenience wrapper around download_binary_with_nodriver
    that also validates the downloaded file is a valid PDF.

    Args:
        url: URL to download from.
        output_path: Local file path to save the PDF.
        timeout: Download timeout in seconds.
        progress_callback: Optional callback for progress updates.

    Returns:
        Tuple of (success: bool, error_message: Optional[str]).
    """
    success, error = await download_binary_with_nodriver(
        url=url,
        output_path=output_path,
        timeout=timeout,
        headless=True,
        progress_callback=progress_callback,
    )

    if not success:
        return False, error

    # Verify it's a valid PDF (check magic bytes)
    try:
        with open(output_path, 'rb') as f:
            magic = f.read(5)
            if magic != b'%PDF-':
                Path(output_path).unlink(missing_ok=True)
                return False, "Downloaded file is not a valid PDF"
    except Exception as e:
        return False, f"Failed to verify PDF: {str(e)}"

    return True, None
