"""Browser utilities for Playwright management."""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def get_playwright_browsers_path() -> str:
    """Get the Playwright browsers path.

    Returns:
        Path where Playwright browsers are installed.
    """
    return os.environ.get('PLAYWRIGHT_BROWSERS_PATH',
                          str(Path.home() / '.cache' / 'ms-playwright'))


def check_browser_installed(browser: str = 'chromium') -> Tuple[bool, str]:
    """Check if a Playwright browser is installed.

    Args:
        browser: Browser name ('chromium', 'firefox', 'webkit').

    Returns:
        Tuple of (is_installed, message).
    """
    browsers_path = get_playwright_browsers_path()

    # Check if browsers directory exists
    if not os.path.exists(browsers_path):
        return False, f"Playwright browsers directory not found: {browsers_path}"

    # Look for browser directories
    browser_dirs = list(Path(browsers_path).glob(f'{browser}*'))

    if not browser_dirs:
        return False, f"Browser '{browser}' not found in {browsers_path}"

    # Check if executable exists
    for browser_dir in browser_dirs:
        if browser == 'chromium':
            # Check for chromium executable
            executables = list(browser_dir.glob('**/chrome')) + \
                         list(browser_dir.glob('**/chromium')) + \
                         list(browser_dir.glob('**/headless_shell'))
            if executables:
                return True, f"Browser '{browser}' found at {browser_dir}"

    return False, f"Browser '{browser}' directory exists but executable not found"


def install_browser(browser: str = 'chromium') -> Tuple[bool, str]:
    """Install a Playwright browser.

    Args:
        browser: Browser name ('chromium', 'firefox', 'webkit').

    Returns:
        Tuple of (success, message).
    """
    try:
        logger.info(f"Installing Playwright browser: {browser}")
        result = subprocess.run(
            ['python', '-m', 'playwright', 'install', browser],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            return True, f"Successfully installed {browser}"
        else:
            return False, f"Failed to install {browser}: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, f"Timeout installing {browser}"
    except Exception as e:
        return False, f"Error installing {browser}: {str(e)}"


def ensure_browser_installed(browser: str = 'chromium') -> Tuple[bool, str]:
    """Ensure a browser is installed, installing if necessary.

    Args:
        browser: Browser name ('chromium', 'firefox', 'webkit').

    Returns:
        Tuple of (success, message).
    """
    is_installed, msg = check_browser_installed(browser)

    if is_installed:
        logger.info(msg)
        return True, msg

    logger.warning(f"Browser not found: {msg}")
    logger.info(f"Attempting to install {browser}...")

    return install_browser(browser)


def get_browser_info() -> dict:
    """Get information about installed Playwright browsers.

    Returns:
        Dictionary with browser installation info.
    """
    browsers_path = get_playwright_browsers_path()

    info = {
        'browsers_path': browsers_path,
        'path_exists': os.path.exists(browsers_path),
        'browsers': {}
    }

    for browser in ['chromium', 'firefox', 'webkit']:
        is_installed, msg = check_browser_installed(browser)
        info['browsers'][browser] = {
            'installed': is_installed,
            'message': msg
        }

    return info
