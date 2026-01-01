"""Browser lifecycle management."""

import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..core.config import BrowserConfig, BrowserType
from .stealth import get_stealth_scripts, get_realistic_user_agent, get_stealth_headers

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser instances and lifecycle."""

    def __init__(self, config: BrowserConfig):
        """Initialize BrowserManager.

        Args:
            config: Browser configuration.
        """
        self.config = config
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def init(self) -> None:
        """Initialize and launch browser."""
        logger.info(f"Launching {self.config.browser_type.value} browser in headless={self.config.headless}")

        self._playwright = await async_playwright().start()

        browser_launcher = {
            BrowserType.CHROMIUM: self._playwright.chromium,
            BrowserType.FIREFOX: self._playwright.firefox,
            BrowserType.WEBKIT: self._playwright.webkit,
        }[self.config.browser_type]

        launch_args = {
            "headless": self.config.headless,
            "args": self._build_launch_args(),
        }

        if self.config.proxy:
            launch_args["proxy"] = self._parse_proxy()

        self._browser = await browser_launcher.launch(**launch_args)
        logger.info("Browser launched successfully")

    async def create_context(self) -> BrowserContext:
        """Create a new browser context.

        Returns:
            New BrowserContext instance.
        """
        if not self._browser:
            await self.init()

        context_args = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        }

        # Use realistic user agent for stealth/cloudflare bypass
        if self.config.cloudflare_bypass or self.config.enable_stealth:
            context_args["user_agent"] = self.config.user_agent or get_realistic_user_agent()
            # Add stealth headers
            context_args["extra_http_headers"] = get_stealth_headers()
            logger.debug("Stealth mode enabled with realistic user agent")
        elif self.config.user_agent:
            context_args["user_agent"] = self.config.user_agent

        if self.config.timezone_id:
            context_args["timezone_id"] = self.config.timezone_id
        elif self.config.cloudflare_bypass:
            # Set realistic timezone for Cloudflare bypass
            context_args["timezone_id"] = "America/New_York"

        if self.config.geolocation:
            context_args["geolocation"] = self.config.geolocation
            context_args["permissions"] = ["geolocation"]

        if self.config.locale:
            context_args["locale"] = self.config.locale
        elif self.config.cloudflare_bypass:
            context_args["locale"] = "en-US"

        if self.config.cookies:
            # Cookies will be added after context creation
            pass

        # Disable JavaScript if configured
        if self.config.disable_javascript:
            context_args["java_script_enabled"] = False
            logger.debug("JavaScript disabled for faster crawling")

        self._context = await self._browser.new_context(**context_args)

        if self.config.cookies:
            await self._context.add_cookies(self.config.cookies)

        # Apply stealth scripts on context creation
        if self.config.cloudflare_bypass or self.config.enable_stealth:
            stealth_script = get_stealth_scripts(include_cloudflare=self.config.cloudflare_bypass)
            await self._context.add_init_script(stealth_script)
            logger.debug("Stealth scripts injected into context")

        logger.debug("Browser context created")
        return self._context

    async def new_page(self) -> Page:
        """Create a new page in the current context.

        Returns:
            New Page instance.
        """
        if not self._context:
            await self.create_context()

        page = await self._context.new_page()

        # Apply resource blocking if configured
        await self._setup_resource_blocking(page)

        logger.debug("New page created")
        return page

    async def _setup_resource_blocking(self, page: Page) -> None:
        """Set up resource blocking for faster page loads.

        Args:
            page: Playwright page object.
        """
        blocked_types = []

        if self.config.disable_images:
            blocked_types.extend(['image', 'imageset'])

        if self.config.disable_css:
            blocked_types.extend(['stylesheet', 'font'])

        # Block additional resource types for faster crawling
        # These are typically not needed for content extraction
        blocked_types.extend(['media'])  # video, audio

        if blocked_types:
            async def block_resources(route):
                if route.request.resource_type in blocked_types:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_resources)
            logger.debug(f"Resource blocking enabled for: {', '.join(blocked_types)}")

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._context:
            await self._context.close()
            self._context = None
            logger.debug("Browser context closed")

        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.debug("Browser closed")

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            logger.info("Playwright stopped")

    def _build_launch_args(self) -> list:
        """Build browser launch arguments.

        Returns:
            List of launch arguments.
        """
        args = []

        if self.config.disable_images:
            args.append("--blink-settings=imagesEnabled=false")

        # Stealth/Cloudflare bypass arguments
        if self.config.cloudflare_bypass or self.config.enable_stealth:
            args.extend([
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--disable-web-security",
                "--disable-features=BlockInsecurePrivateNetworkRequests",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--start-maximized",
                "--disable-extensions",
            ])
            logger.debug("Stealth launch args enabled")
        elif self.config.disable_css:
            args.append("--disable-blink-features=AutomationControlled")

        return args

    def _parse_proxy(self) -> dict:
        """Parse proxy URL into components.

        Returns:
            Proxy configuration dict.

        Raises:
            ValueError: If proxy URL is invalid.
        """
        proxy_str = self.config.proxy
        if not proxy_str:
            return {}

        # Handle proxy formats: http://host:port or http://user:pass@host:port
        if "://" in proxy_str:
            scheme, rest = proxy_str.split("://", 1)
        else:
            scheme = "http"
            rest = proxy_str

        proxy_dict = {"server": f"{scheme}://{rest}"}

        if "@" in rest:
            auth, host = rest.rsplit("@", 1)
            user, password = auth.split(":", 1)
            proxy_dict["username"] = user
            proxy_dict["password"] = password

        return proxy_dict

    async def __aenter__(self):
        """Async context manager entry."""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
