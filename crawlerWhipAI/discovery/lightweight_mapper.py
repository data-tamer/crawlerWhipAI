"""Lightweight link mapper using sitemap and HTTP-first approach."""

import logging
import asyncio
import aiohttp
from typing import Optional, Set, List, Dict
from urllib.parse import urlparse, urljoin
from lxml import html as lxml_html

from ..models import LinkNode
from ..core import AsyncWebCrawler, CrawlerConfig, BrowserConfig
from ..utils import normalize_url, get_base_domain, is_internal_url, get_full_host
from .sitemap import SitemapParser

logger = logging.getLogger(__name__)


class LightweightLinkMapper:
    """Fast link discovery: sitemap → HTTP + lxml → browser fallback.

    This mapper prioritizes speed by:
    1. Checking sitemap.xml first (instant if available)
    2. Using lightweight HTTP requests + lxml parsing
    3. Falling back to browser only when JavaScript is detected
    """

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 100,
        include_external: bool = False,
        same_host_only: bool = True,
        max_concurrent: int = 10,
        http_timeout: float = 10.0,
        use_sitemap: bool = True,
    ):
        """Initialize LightweightLinkMapper.

        Args:
            max_depth: Maximum crawl depth.
            max_pages: Maximum pages to discover.
            include_external: Whether to include external links.
            same_host_only: Only crawl exact same hostname.
            max_concurrent: Maximum concurrent requests.
            http_timeout: Timeout for HTTP requests in seconds.
            use_sitemap: Whether to try sitemap.xml first.
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.include_external = include_external
        self.same_host_only = same_host_only
        self.max_concurrent = max_concurrent
        self.http_timeout = http_timeout
        self.use_sitemap = use_sitemap

        self.sitemap_parser = SitemapParser(
            timeout_seconds=http_timeout,
            max_urls=max_pages,
            same_host_only=same_host_only,
        )
        self.pages_crawled = 0
        self._js_required_urls: Set[str] = set()

    async def map_links(
        self,
        start_url: str,
        crawler_config: Optional[CrawlerConfig] = None,
    ) -> LinkNode:
        """Map links starting from a URL.

        Priority:
        1. Try sitemap.xml (instant)
        2. Use HTTP + lxml crawling (fast)
        3. Fall back to browser for JS-heavy pages

        Args:
            start_url: Starting URL for link mapping.
            crawler_config: Optional crawler configuration.

        Returns:
            Root LinkNode with hierarchical structure.
        """
        logger.info(
            f"Starting lightweight link mapping from {start_url} "
            f"(max_depth={self.max_depth}, max_pages={self.max_pages})"
        )

        self.pages_crawled = 0
        self._js_required_urls.clear()

        parsed = urlparse(start_url)
        self.start_host = parsed.netloc
        self.base_domain = f"{parsed.scheme}://{parsed.netloc}"

        # 1. Try sitemap first (instant)
        if self.use_sitemap:
            sitemap_urls = await self.sitemap_parser.get_urls(start_url)
            if sitemap_urls:
                logger.info(f"Using sitemap: found {len(sitemap_urls)} URLs")
                return self._urls_to_link_tree(sitemap_urls, start_url)

        # 2. Use HTTP + lxml crawling (fast)
        root = await self._http_crawl(start_url, crawler_config)

        # 3. Check if we need browser fallback for JS-heavy pages
        if self._js_required_urls:
            logger.info(
                f"Detected {len(self._js_required_urls)} JS-heavy pages, "
                f"using browser fallback"
            )
            await self._browser_fallback(root, crawler_config)

        logger.info(
            f"Link mapping complete: {self.pages_crawled} pages discovered, "
            f"{root.count_nodes()} total nodes"
        )
        return root

    def _urls_to_link_tree(self, urls: List[str], start_url: str) -> LinkNode:
        """Convert a flat list of URLs to a LinkNode tree.

        Args:
            urls: List of discovered URLs.
            start_url: The starting URL (root).

        Returns:
            Root LinkNode with all URLs as children.
        """
        # Find or create root
        root_url = start_url
        if start_url not in urls:
            urls = [start_url] + urls

        root = LinkNode(
            url=root_url,
            depth=0,
            parent_url=None,
            is_internal=True,
        )

        # Add all other URLs as depth=1 children
        for url in urls[:self.max_pages]:
            if url == root_url:
                continue

            child = LinkNode(
                url=url,
                depth=1,
                parent_url=root_url,
                is_internal=True,
            )
            root.children.append(child)

        self.pages_crawled = len(root.children) + 1
        return root

    async def _http_crawl(
        self,
        start_url: str,
        crawler_config: Optional[CrawlerConfig] = None,
    ) -> LinkNode:
        """Crawl using lightweight HTTP requests + lxml.

        Args:
            start_url: Starting URL.
            crawler_config: Optional config (for preserve_url_fragment).

        Returns:
            Root LinkNode with discovered links.
        """
        preserve_fragment = (
            crawler_config.preserve_url_fragment
            if crawler_config else False
        )

        root = LinkNode(
            url=start_url,
            depth=0,
            parent_url=None,
            is_internal=True,
        )

        visited: Set[str] = {normalize_url(start_url, preserve_fragment=preserve_fragment)}
        current_depth_nodes = [root]
        self.pages_crawled = 0

        semaphore = asyncio.Semaphore(self.max_concurrent)

        for current_depth in range(self.max_depth + 1):
            if not current_depth_nodes or self.pages_crawled >= self.max_pages:
                break

            logger.debug(
                f"Processing depth {current_depth} with {len(current_depth_nodes)} nodes"
            )

            # Crawl all nodes at current depth concurrently
            tasks = [
                self._fetch_and_extract_links(
                    node, semaphore, visited, preserve_fragment, current_depth
                )
                for node in current_depth_nodes
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Collect children for next depth
            next_depth_nodes = []
            for node in current_depth_nodes:
                next_depth_nodes.extend(node.children)

            current_depth_nodes = next_depth_nodes

        return root

    async def _fetch_and_extract_links(
        self,
        node: LinkNode,
        semaphore: asyncio.Semaphore,
        visited: Set[str],
        preserve_fragment: bool,
        current_depth: int,
    ) -> None:
        """Fetch a page with HTTP and extract links using lxml.

        Args:
            node: LinkNode to populate.
            semaphore: Concurrency limiter.
            visited: Set of visited URLs.
            preserve_fragment: Whether to preserve URL fragments.
            current_depth: Current depth level.
        """
        async with semaphore:
            if self.pages_crawled >= self.max_pages:
                return

            logger.debug(f"[Depth {current_depth}] Fetching {node.url}")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        node.url,
                        timeout=aiohttp.ClientTimeout(total=self.http_timeout),
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                                         'Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                        },
                        allow_redirects=True,
                        ssl=False,  # Skip SSL verification for speed
                    ) as response:
                        node.status_code = response.status

                        if response.status != 200:
                            node.error = f"HTTP {response.status}"
                            self.pages_crawled += 1
                            return

                        html = await response.text()

            except asyncio.TimeoutError:
                node.error = "Timeout"
                self.pages_crawled += 1
                return
            except Exception as e:
                node.error = str(e)
                self.pages_crawled += 1
                return

            self.pages_crawled += 1

            # Check if page needs JavaScript
            if self._needs_javascript(html):
                logger.debug(f"Page needs JavaScript: {node.url}")
                self._js_required_urls.add(node.url)
                # Still try to extract links - some might work
                # but mark for browser fallback

            # Extract links and metadata
            try:
                tree = lxml_html.fromstring(html)

                # Extract title
                title_elem = tree.xpath('//title/text()')
                if title_elem:
                    node.title = str(title_elem[0]).strip()

                # Extract meta description
                desc_elem = tree.xpath('//meta[@name="description"]/@content')
                if desc_elem:
                    node.description = str(desc_elem[0]).strip()

                # Extract og:title as fallback
                og_title = tree.xpath('//meta[@property="og:title"]/@content')
                if og_title:
                    node.meta_tags['og:title'] = str(og_title[0]).strip()
                    if not node.title:
                        node.title = node.meta_tags['og:title']

                # Extract links if we can go deeper
                if current_depth < self.max_depth and self.pages_crawled < self.max_pages:
                    self._extract_and_add_links(
                        node, tree, visited, preserve_fragment, current_depth
                    )

            except Exception as e:
                logger.debug(f"Error parsing HTML from {node.url}: {e}")

    def _extract_and_add_links(
        self,
        parent_node: LinkNode,
        tree,
        visited: Set[str],
        preserve_fragment: bool,
        current_depth: int,
    ) -> None:
        """Extract links from HTML and add as child nodes.

        Args:
            parent_node: Parent LinkNode.
            tree: lxml HTML tree.
            visited: Set of visited URLs.
            preserve_fragment: Whether to preserve URL fragments.
            current_depth: Current depth level.
        """
        next_depth = current_depth + 1

        for link in tree.xpath('//a[@href]'):
            if len(visited) >= self.max_pages:
                break

            href = link.get('href', '').strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            # Resolve relative URLs
            try:
                full_url = urljoin(parent_node.url, href)
                normalized = normalize_url(full_url, preserve_fragment=preserve_fragment)
            except Exception:
                continue

            # Skip if already visited
            if normalized in visited:
                continue

            # Filter by host
            url_host = urlparse(normalized).netloc
            if self.same_host_only and url_host != self.start_host:
                continue

            if not self.include_external:
                if not is_internal_url(normalized, get_base_domain(parent_node.url)):
                    continue

            # Add to visited and create child node
            visited.add(normalized)

            child = LinkNode(
                url=normalized,
                depth=next_depth,
                parent_url=parent_node.url,
                is_internal=url_host == self.start_host,
            )
            parent_node.children.append(child)

    def _needs_javascript(self, html: str) -> bool:
        """Check if page likely needs JavaScript to render content.

        Args:
            html: Raw HTML content.

        Returns:
            True if JavaScript is likely needed.
        """
        try:
            tree = lxml_html.fromstring(html)

            # Check for empty/minimal body
            body = tree.xpath('//body')
            if body:
                body_text = body[0].text_content().strip()
                # Very little content suggests JS rendering
                if len(body_text) < 100:
                    return True

            # Check for SPA framework indicators
            spa_indicators = [
                'id="root"', 'id="app"', 'id="__next"',
                'ng-app', 'data-reactroot', 'data-v-',
                '__NUXT__', '__NEXT_DATA__',
            ]
            html_lower = html.lower()
            for indicator in spa_indicators:
                if indicator.lower() in html_lower:
                    # Check if there's actual content despite the indicator
                    if body:
                        body_text = body[0].text_content().strip()
                        if len(body_text) < 200:
                            return True

            # Check for meaningful noscript content
            noscript = tree.xpath('//noscript')
            for ns in noscript:
                ns_text = ns.text_content().strip()
                if len(ns_text) > 50 and ('javascript' in ns_text.lower() or 'enable' in ns_text.lower()):
                    return True

        except Exception:
            pass

        return False

    async def _browser_fallback(
        self,
        root: LinkNode,
        crawler_config: Optional[CrawlerConfig] = None,
    ) -> None:
        """Use browser to crawl JS-heavy pages.

        Args:
            root: Root LinkNode to update.
            crawler_config: Optional crawler configuration.
        """
        if not self._js_required_urls:
            return

        config = crawler_config or CrawlerConfig()
        browser_config = BrowserConfig(
            headless=True,
            disable_images=True,
            disable_css=True,
        )

        try:
            async with AsyncWebCrawler(
                browser_config=browser_config,
                crawler_config=config,
            ) as crawler:
                for url in list(self._js_required_urls)[:10]:  # Limit browser usage
                    try:
                        result = await crawler.arun(url)
                        if result.success and result.links:
                            # Find the node and update it
                            node = self._find_node(root, url)
                            if node:
                                node.title = result.title or node.title
                                node.description = result.description or node.description

                                # Add newly discovered links
                                for link_data in result.links.get('internal', []):
                                    link_url = link_data.get('href', '')
                                    if link_url and not self._find_node(root, link_url):
                                        child = LinkNode(
                                            url=link_url,
                                            depth=node.depth + 1,
                                            parent_url=url,
                                            is_internal=True,
                                        )
                                        node.children.append(child)

                    except Exception as e:
                        logger.debug(f"Browser fallback failed for {url}: {e}")

        except Exception as e:
            logger.warning(f"Browser fallback initialization failed: {e}")

    def _find_node(self, root: LinkNode, url: str) -> Optional[LinkNode]:
        """Find a node by URL in the tree.

        Args:
            root: Root node to search from.
            url: URL to find.

        Returns:
            LinkNode if found, None otherwise.
        """
        if root.url == url:
            return root

        for child in root.children:
            found = self._find_node(child, url)
            if found:
                return found

        return None

    def get_all_urls(self, root: LinkNode, max_depth: Optional[int] = None) -> List[str]:
        """Get all discovered URLs from root node.

        Args:
            root: Root LinkNode.
            max_depth: Optional maximum depth to retrieve.

        Returns:
            List of all URLs.
        """
        return root.get_all_urls(max_depth)

    def get_js_required_urls(self) -> Set[str]:
        """Get URLs that required JavaScript rendering.

        Returns:
            Set of URLs that needed browser fallback.
        """
        return self._js_required_urls.copy()
