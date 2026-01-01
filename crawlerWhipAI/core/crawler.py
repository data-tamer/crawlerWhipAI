"""Main AsyncWebCrawler class."""

import logging
import time
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from urllib.parse import urljoin

import aiohttp
from playwright.async_api import Page
from lxml import html as lxml_html

from ..browser.manager import BrowserManager
from ..browser.cloudflare import (
    is_cloudflare_challenge,
    wait_for_cloudflare,
    detect_and_handle_cloudflare,
    quick_cloudflare_check,
)
from ..browser.nodriver_fallback import fetch_with_nodriver, HAS_NODRIVER
from ..browser.stealth import get_realistic_user_agent, get_stealth_headers
from ..models import CrawlResult, MarkdownGenerationResult
from ..utils import normalize_url, validate_url, get_base_domain, is_internal_url
from ..cache import CacheStorage
from .config import BrowserConfig, CrawlerConfig, CacheMode

logger = logging.getLogger(__name__)


class AsyncWebCrawler:
    """Main async web crawler."""

    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        crawler_config: Optional[CrawlerConfig] = None,
        cache_db_path: str = ".crawl_cache.db",
    ):
        """Initialize crawler.

        Args:
            browser_config: Browser configuration.
            crawler_config: Crawler configuration.
            cache_db_path: Path to cache database file.
        """
        self.browser_config = browser_config or BrowserConfig()
        self.crawler_config = crawler_config or CrawlerConfig()
        self.browser_manager = BrowserManager(self.browser_config)
        self.cache = CacheStorage(cache_db_path) if crawler_config and crawler_config.cache_mode != CacheMode.BYPASS else None
        self._initialized = False

    async def start(self) -> None:
        """Start the crawler (launch browser and cache)."""
        await self.browser_manager.init()

        # Initialize cache if enabled
        if self.cache and self.crawler_config.cache_mode != CacheMode.BYPASS:
            await self.cache.init()
            logger.info(f"Cache enabled: mode={self.crawler_config.cache_mode.value}, ttl={self.crawler_config.cache_ttl_hours}h")
        else:
            logger.info("Cache disabled (BYPASS mode)")

        self._initialized = True
        logger.info("Crawler started")

    async def arun(
        self,
        url: str,
        config: Optional[CrawlerConfig] = None,
    ) -> CrawlResult:
        """Crawl a single URL.

        Args:
            url: URL to crawl.
            config: Optional crawler config (overrides default).

        Returns:
            CrawlResult with page content and metadata.
        """
        if not self._initialized:
            await self.start()

        if not validate_url(url):
            return CrawlResult(
                url=url,
                success=False,
                error=f"Invalid URL: {url}",
                error_type="ValidationError",
            )

        config = config or self.crawler_config
        start_time = time.time()

        # Check cache if enabled and mode allows reading
        if self.cache and config.cache_mode in [CacheMode.CACHED, CacheMode.READ_ONLY]:
            cached = await self.cache.get(url)
            if cached:
                logger.info(f"Cache hit: {url}")
                # Return cached result
                return CrawlResult(
                    url=url,
                    success=True,
                    html="",  # Not stored in cache
                    markdown=cached.get("content"),
                    title=cached.get("metadata", {}).get("title"),
                    description=cached.get("metadata", {}).get("description"),
                    status_code=200,
                    crawled_at=datetime.fromisoformat(cached.get("created_at")),
                    execution_time=time.time() - start_time,
                    links=cached.get("metadata", {}).get("links", {"internal": [], "external": []}),
                    cached=True,
                )

        # Not in cache or cache mode doesn't allow reading - crawl the page
        try:
            result = None

            # Try HTTP-first if enabled (faster for static pages)
            if config.http_first:
                result = await self._http_fetch(url, config)
                if result and result.success:
                    # Check if page needs browser rendering
                    if self._needs_browser(result.html or ""):
                        logger.info(f"HTTP fetch succeeded but page needs browser: {url}")
                        result = None  # Fall through to browser
                    else:
                        logger.info(f"HTTP fetch successful (no browser needed): {url}")

            # Fall back to browser if HTTP-first disabled or failed/needs JS
            if result is None:
                # Quick Cloudflare check before starting browser (saves ~3+ seconds)
                if self.browser_config.cloudflare_bypass and config.use_nodriver_fallback and HAS_NODRIVER:
                    is_cf = await quick_cloudflare_check(url, timeout=3.0)
                    if is_cf:
                        logger.info(f"Cloudflare detected via HTTP - skipping Playwright, using nodriver: {url}")
                        return await self._nodriver_fallback(url, config)

                page = await self.browser_manager.new_page()
                result = await self._crawl_page(page, url, config)
                await page.close()

            result.execution_time = time.time() - start_time

            # Save to cache if enabled and mode allows writing
            if self.cache and result.success and config.cache_mode in [CacheMode.CACHED, CacheMode.WRITE_ONLY]:
                await self.cache.set(
                    url,
                    result.markdown or "",
                    metadata={
                        "title": result.title,
                        "description": result.description,
                        "status_code": result.status_code,
                        "links": result.links,
                    },
                    ttl_hours=config.cache_ttl_hours,
                )
                logger.info(f"Cached: {url} (TTL: {config.cache_ttl_hours}h)")

            return result
        except Exception as e:
            logger.error(f"Error crawling {url}: {str(e)}")
            return CrawlResult(
                url=url,
                success=False,
                error=str(e),
                error_type=type(e).__name__,
                execution_time=time.time() - start_time,
            )

    async def arun_many(
        self,
        urls: List[str],
        config: Optional[CrawlerConfig] = None,
        max_concurrent: int = 5,
    ) -> List[CrawlResult]:
        """Crawl multiple URLs concurrently.

        Args:
            urls: List of URLs to crawl.
            config: Optional crawler config.
            max_concurrent: Maximum concurrent requests.

        Returns:
            List of CrawlResult objects.
        """
        if not self._initialized:
            await self.start()

        semaphore = asyncio.Semaphore(max_concurrent)

        async def sem_run(url):
            async with semaphore:
                return await self.arun(url, config)

        tasks = [sem_run(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def close(self) -> None:
        """Close the crawler and cleanup resources."""
        await self.browser_manager.close()
        self._initialized = False
        logger.info("Crawler closed")

    async def _http_fetch(self, url: str, config: CrawlerConfig) -> Optional[CrawlResult]:
        """Lightweight HTTP fetch without browser.

        Args:
            url: URL to fetch.
            config: Crawler configuration.

        Returns:
            CrawlResult if successful, None if failed.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=config.http_timeout)
            # Use stealth headers for better Cloudflare bypass
            stealth_headers = get_stealth_headers()
            stealth_headers["User-Agent"] = self.browser_config.user_agent or get_realistic_user_agent()
            headers = {
                **stealth_headers,
                **config.headers,
            }

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, ssl=False) as response:
                    if response.status != 200:
                        logger.debug(f"HTTP fetch failed with status {response.status}: {url}")
                        return None

                    html_content = await response.text()

                    # Build result
                    result = CrawlResult(
                        url=url,
                        success=True,
                        status_code=response.status,
                        html=html_content,
                        crawled_at=datetime.utcnow(),
                    )

                    # Extract metadata from HTML
                    self._extract_metadata_from_html(html_content, result)

                    # Extract links from HTML
                    self._extract_links_from_html(html_content, result, url)

                    # Generate markdown
                    if html_content:
                        result.markdown = self._html_to_markdown(html_content)

                    result.content_length = len(html_content)
                    result.user_agent = headers.get("User-Agent")

                    return result

        except asyncio.TimeoutError:
            logger.debug(f"HTTP fetch timeout: {url}")
            return None
        except Exception as e:
            logger.debug(f"HTTP fetch error: {url} - {str(e)}")
            return None

    def _needs_browser(self, html: str) -> bool:
        """Detect if page needs browser rendering (JS-heavy).

        Args:
            html: HTML content.

        Returns:
            True if page needs browser, False otherwise.
        """
        if not html:
            return True

        try:
            tree = lxml_html.fromstring(html)
            body = tree.find(".//body")

            if body is None:
                return True

            # Get text content length
            text_content = body.text_content().strip()
            if len(text_content) < 100:
                # Very little content - likely JS-rendered
                return True

            # Check for SPA indicators
            html_lower = html.lower()
            spa_indicators = [
                'id="root"',
                'id="app"',
                'id="__next"',
                'ng-app',
                'data-reactroot',
                'data-v-',  # Vue
                '__nuxt',
            ]
            for indicator in spa_indicators:
                if indicator in html_lower:
                    # Check if there's meaningful content despite SPA framework
                    # Some pre-rendered SPAs have content
                    if len(text_content) > 500:
                        return False
                    return True

            # Check for noscript with meaningful content
            noscript = tree.find(".//noscript")
            if noscript is not None:
                noscript_text = noscript.text_content().strip()
                if len(noscript_text) > 50 and "javascript" in noscript_text.lower():
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error detecting JS need: {str(e)}")
            return True  # Default to browser on error

    def _extract_metadata_from_html(self, html: str, result: CrawlResult) -> None:
        """Extract metadata from HTML without browser.

        Args:
            html: HTML content.
            result: CrawlResult to populate.
        """
        try:
            tree = lxml_html.fromstring(html)

            # Title
            title_elem = tree.find(".//title")
            if title_elem is not None and title_elem.text:
                result.title = title_elem.text.strip()

            # og:title fallback
            og_title = tree.find(".//meta[@property='og:title']")
            if og_title is not None:
                og_title_content = og_title.get("content")
                if og_title_content:
                    result.meta_tags["og:title"] = og_title_content
                    if not result.title:
                        result.title = og_title_content

            # og:image
            og_image = tree.find(".//meta[@property='og:image']")
            if og_image is not None:
                og_image_content = og_image.get("content")
                if og_image_content:
                    result.meta_tags["og:image"] = og_image_content

            # Meta description
            desc = tree.find(".//meta[@name='description']")
            if desc is not None:
                result.description = desc.get("content")
            else:
                og_desc = tree.find(".//meta[@property='og:description']")
                if og_desc is not None:
                    result.description = og_desc.get("content")

        except Exception as e:
            logger.debug(f"Error extracting metadata from HTML: {str(e)}")

    def _extract_links_from_html(self, html: str, result: CrawlResult, base_url: str) -> None:
        """Extract links from HTML without browser.

        Args:
            html: HTML content.
            result: CrawlResult to populate.
            base_url: Base URL for relative link resolution.
        """
        try:
            tree = lxml_html.fromstring(html)
            base_domain = get_base_domain(base_url)
            internal_links = []
            external_links = []

            for link in tree.xpath(".//a[@href]"):
                try:
                    href = link.get("href")
                    text = link.text_content()

                    if not href:
                        continue

                    # Normalize URL
                    normalized = normalize_url(
                        href,
                        base_url,
                        preserve_fragment=self.crawler_config.preserve_url_fragment
                    )

                    # Categorize
                    is_internal = is_internal_url(normalized, base_domain)

                    link_data = {
                        "href": normalized,
                        "text": text.strip() if text else "",
                    }

                    if is_internal:
                        internal_links.append(link_data)
                    else:
                        external_links.append(link_data)
                except Exception:
                    pass

            result.links["internal"] = internal_links
            result.links["external"] = external_links

        except Exception as e:
            logger.debug(f"Error extracting links from HTML: {str(e)}")

    async def _crawl_page(
        self,
        page: Page,
        url: str,
        config: CrawlerConfig,
    ) -> CrawlResult:
        """Internal method to crawl a page.

        Args:
            page: Playwright page object.
            url: URL to crawl.
            config: Crawler configuration.

        Returns:
            CrawlResult.
        """
        logger.info(f"Crawling {url}")

        # Navigate to page
        try:
            response = await page.goto(
                url,
                wait_until=config.wait_until.value,
                timeout=config.page_timeout,
            )
            status_code = response.status if response else None
        except Exception as e:
            logger.warning(f"Navigation failed: {str(e)}")
            status_code = None

        # Handle Cloudflare challenge if cloudflare_bypass is enabled
        if self.browser_config.cloudflare_bypass and config.cloudflare_wait:
            is_blocked, error = await detect_and_handle_cloudflare(
                page,
                timeout=config.cloudflare_timeout,
            )
            if is_blocked:
                logger.warning(f"Cloudflare blocked: {error}")
                # Try nodriver fallback if enabled
                if config.use_nodriver_fallback and HAS_NODRIVER:
                    return await self._nodriver_fallback(url, config)
                else:
                    return CrawlResult(
                        url=url,
                        success=False,
                        error=f"Cloudflare challenge failed: {error}",
                        error_type="CloudflareBlocked",
                        status_code=403,
                    )

        # Execute user JavaScript if provided
        if config.js_code:
            await self._execute_js(page, config.js_code)

        # Handle page scrolling for content loading
        if config.scan_full_page:
            await self._scroll_full_page(page, config)

        # Wait for additional content if specified
        if config.wait_for:
            await self._wait_for_condition(page, config.wait_for, config.wait_for_timeout)

        # Extract HTML
        html_content = await page.content()

        # Basic content extraction
        result = CrawlResult(
            url=url,
            status_code=status_code,
            html=html_content,
            crawled_at=datetime.utcnow(),
        )

        # Extract metadata
        await self._extract_metadata(page, result)

        # Extract links
        await self._extract_links(page, result, url)

        # Generate markdown if HTML is available
        if html_content:
            result.markdown = self._html_to_markdown(html_content)

        result.content_length = len(html_content)
        result.user_agent = self.browser_config.user_agent

        logger.info(f"Successfully crawled {url} ({len(html_content)} bytes)")
        return result

    async def _execute_js(self, page: Page, js_code: any) -> None:
        """Execute JavaScript code on page.

        Args:
            page: Playwright page object.
            js_code: JavaScript code (string or list of strings).
        """
        if isinstance(js_code, list):
            for code in js_code:
                await page.evaluate(code)
        else:
            await page.evaluate(js_code)
        logger.debug("Executed JavaScript")

    async def _scroll_full_page(self, page: Page, config: CrawlerConfig) -> None:
        """Scroll page to load all content.

        Args:
            page: Playwright page object.
            config: Crawler configuration.
        """
        max_steps = config.max_scroll_steps or 100
        delay = config.scroll_delay

        for i in range(max_steps):
            # Get current scroll position
            scroll_height = await page.evaluate("() => document.body.scrollHeight")
            await page.evaluate("() => window.scrollBy(0, document.body.scrollHeight)")
            await asyncio.sleep(delay)

            # Check if we reached the bottom
            new_height = await page.evaluate("() => document.body.scrollHeight")
            if scroll_height == new_height:
                logger.debug(f"Reached bottom after {i + 1} scrolls")
                break

        logger.debug(f"Completed full-page scroll ({i + 1} steps)")

    async def _wait_for_condition(
        self,
        page: Page,
        condition: str,
        timeout: Optional[int] = None,
    ) -> None:
        """Wait for a condition (CSS selector or JS function).

        Args:
            page: Playwright page object.
            condition: CSS selector (css:) or JS function (js:).
            timeout: Timeout in milliseconds.
        """
        timeout_ms = timeout or 30000

        try:
            if condition.startswith("css:"):
                selector = condition[4:]
                await page.wait_for_selector(selector, timeout=timeout_ms)
                logger.debug(f"Wait condition met: {selector}")
            elif condition.startswith("js:"):
                js_func = condition[3:]
                await page.wait_for_function(js_func, timeout=timeout_ms)
                logger.debug("JavaScript wait condition met")
            else:
                # Default to CSS selector
                await page.wait_for_selector(condition, timeout=timeout_ms)
                logger.debug(f"Wait condition met: {condition}")
        except Exception as e:
            logger.warning(f"Wait condition timeout: {str(e)}")

    async def _extract_metadata(self, page: Page, result: CrawlResult) -> None:
        """Extract page metadata.

        Args:
            page: Playwright page object.
            result: CrawlResult to populate.
        """
        try:
            # Open Graph tags (extract first for fallback)
            og_title = await page.locator("meta[property='og:title']").get_attribute("content")
            if og_title:
                result.meta_tags["og:title"] = og_title

            og_image = await page.locator("meta[property='og:image']").get_attribute("content")
            if og_image:
                result.meta_tags["og:image"] = og_image

            # Title with og:title fallback
            title = await page.title()
            if not title:
                title = og_title
            result.title = title if title else None

            # Meta description
            description = await page.locator("meta[name='description']").get_attribute("content")
            if not description:
                description = await page.locator("meta[property='og:description']").get_attribute("content")
            result.description = description

            logger.debug(f"Extracted metadata: title='{result.title}'")
        except Exception as e:
            logger.debug(f"Error extracting metadata: {str(e)}")

    async def _extract_links(self, page: Page, result: CrawlResult, base_url: str) -> None:
        """Extract links from page.

        Args:
            page: Playwright page object.
            result: CrawlResult to populate.
            base_url: Base URL for relative link resolution.
        """
        try:
            links = await page.locator("a[href]").all()
            base_domain = get_base_domain(base_url)
            internal_links = []
            external_links = []

            for link in links:
                try:
                    href = await link.get_attribute("href")
                    text = await link.text_content()

                    if not href:
                        continue

                    # Normalize URL (preserve fragments if configured for PWA support)
                    normalized = normalize_url(
                        href,
                        base_url,
                        preserve_fragment=self.crawler_config.preserve_url_fragment
                    )

                    # Categorize as internal or external
                    is_internal = is_internal_url(normalized, base_domain)

                    link_data = {
                        "href": normalized,
                        "text": text.strip() if text else "",
                    }

                    if is_internal:
                        internal_links.append(link_data)
                    else:
                        external_links.append(link_data)
                except Exception as e:
                    logger.debug(f"Error extracting link: {str(e)}")

            result.links["internal"] = internal_links
            result.links["external"] = external_links
            logger.debug(f"Extracted {len(internal_links)} internal, {len(external_links)} external links")
        except Exception as e:
            logger.warning(f"Error extracting links: {str(e)}")

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to markdown.

        Args:
            html: HTML content.

        Returns:
            Markdown content.
        """
        try:
            # Parse HTML
            tree = lxml_html.fromstring(html)

            # Remove script and style tags
            for element in tree.xpath(".//script | .//style"):
                element.getparent().remove(element)

            # Extract text content
            text = tree.text_content()

            # Clean up whitespace
            lines = [line.strip() for line in text.split("\n")]
            text = "\n".join(line for line in lines if line)

            return text
        except Exception as e:
            logger.warning(f"Error converting HTML to markdown: {str(e)}")
            return ""

    async def _nodriver_fallback(self, url: str, config: CrawlerConfig) -> CrawlResult:
        """
        Fallback to nodriver for heavily protected sites.

        Args:
            url: URL to fetch.
            config: Crawler configuration.

        Returns:
            CrawlResult.
        """
        logger.info(f"Using nodriver fallback for: {url}")

        html, title, description, error = await fetch_with_nodriver(
            url,
            timeout=config.page_timeout,
            wait_for_cf=True,
            headless=False,  # Use headed mode for better Cloudflare bypass
        )

        if error:
            return CrawlResult(
                url=url,
                success=False,
                error=f"nodriver fallback failed: {error}",
                error_type="NodriverError",
            )

        # Build result
        result = CrawlResult(
            url=url,
            success=True,
            status_code=200,
            html=html,
            title=title,
            description=description,
            crawled_at=datetime.utcnow(),
        )

        # Extract metadata from HTML
        if html:
            self._extract_metadata_from_html(html, result)
            self._extract_links_from_html(html, result, url)
            result.markdown = self._html_to_markdown(html)
            result.content_length = len(html)

        logger.info(f"nodriver fallback successful: {url}")
        return result

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
