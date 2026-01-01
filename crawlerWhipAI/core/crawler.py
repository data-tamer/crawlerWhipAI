"""Main AsyncWebCrawler class."""

import logging
import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urljoin

from playwright.async_api import Page
from lxml import html as lxml_html

from ..browser.manager import BrowserManager
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
                    html=None,  # Not stored in cache
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
            page = await self.browser_manager.new_page()
            result = await self._crawl_page(page, url, config)
            result.execution_time = time.time() - start_time
            await page.close()

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

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
