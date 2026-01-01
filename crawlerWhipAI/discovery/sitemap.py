"""Sitemap parsing for fast URL discovery."""

import logging
import asyncio
import aiohttp
from typing import Optional, List, Set
from urllib.parse import urlparse, urljoin
from lxml import etree

logger = logging.getLogger(__name__)

# XML namespaces used in sitemaps
SITEMAP_NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'xhtml': 'http://www.w3.org/1999/xhtml'
}


class SitemapParser:
    """Parse sitemap.xml to get all URLs instantly."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_sitemaps: int = 10,
        max_urls: int = 1000,
        same_host_only: bool = True,
    ):
        """Initialize parser.

        Args:
            timeout_seconds: Timeout for HTTP requests.
            max_sitemaps: Maximum number of sub-sitemaps to process.
            max_urls: Maximum URLs to return.
            same_host_only: Only return URLs from the same host.
        """
        self.timeout_seconds = timeout_seconds
        self.max_sitemaps = max_sitemaps
        self.max_urls = max_urls
        self.same_host_only = same_host_only

    async def get_urls(self, base_url: str) -> Optional[List[str]]:
        """Get all URLs from sitemap.

        Args:
            base_url: The base URL to find sitemap for.

        Returns:
            List of URLs if sitemap found, None otherwise.
        """
        parsed = urlparse(base_url)
        base_host = parsed.netloc
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        # Try to find sitemap locations
        sitemap_urls = await self._find_sitemap_urls(base_domain)

        if not sitemap_urls:
            logger.debug(f"No sitemap found for {base_domain}")
            return None

        # Parse all sitemaps
        all_urls: Set[str] = set()

        for sitemap_url in sitemap_urls[:self.max_sitemaps]:
            if len(all_urls) >= self.max_urls:
                break

            urls = await self._parse_sitemap(sitemap_url, base_host)
            all_urls.update(urls)

        if not all_urls:
            logger.debug(f"Sitemap found but no URLs extracted for {base_domain}")
            return None

        # Filter and limit
        result = list(all_urls)[:self.max_urls]
        logger.info(f"Found {len(result)} URLs from sitemap for {base_domain}")
        return result

    async def _find_sitemap_urls(self, base_domain: str) -> List[str]:
        """Find sitemap URLs from robots.txt or common locations.

        Args:
            base_domain: Base domain URL.

        Returns:
            List of sitemap URLs to try.
        """
        sitemap_urls = []

        # Check robots.txt first
        robots_url = f"{base_domain}/robots.txt"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    robots_url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; SitemapParser/1.0)'}
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        # Extract sitemap URLs from robots.txt
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.lower().startswith('sitemap:'):
                                sitemap_url = line.split(':', 1)[1].strip()
                                if sitemap_url:
                                    sitemap_urls.append(sitemap_url)
                                    logger.debug(f"Found sitemap in robots.txt: {sitemap_url}")
        except Exception as e:
            logger.debug(f"Error fetching robots.txt: {e}")

        # Add common sitemap locations if none found in robots.txt
        if not sitemap_urls:
            common_locations = [
                f"{base_domain}/sitemap.xml",
                f"{base_domain}/sitemap_index.xml",
                f"{base_domain}/sitemap/sitemap.xml",
            ]
            sitemap_urls.extend(common_locations)

        return sitemap_urls

    async def _parse_sitemap(self, sitemap_url: str, base_host: str) -> Set[str]:
        """Parse a sitemap XML file.

        Args:
            sitemap_url: URL of the sitemap.
            base_host: Base hostname for filtering.

        Returns:
            Set of URLs found in the sitemap.
        """
        urls: Set[str] = set()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    sitemap_url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; SitemapParser/1.0)'}
                ) as response:
                    if response.status != 200:
                        logger.debug(f"Sitemap not found: {sitemap_url} (status {response.status})")
                        return urls

                    content = await response.read()

        except Exception as e:
            logger.debug(f"Error fetching sitemap {sitemap_url}: {e}")
            return urls

        # Parse XML
        try:
            root = etree.fromstring(content)
        except etree.XMLSyntaxError as e:
            logger.debug(f"Invalid XML in sitemap {sitemap_url}: {e}")
            return urls

        # Check if this is a sitemap index
        sitemapindex = root.xpath('//sm:sitemapindex', namespaces=SITEMAP_NS)
        if sitemapindex or root.tag.endswith('sitemapindex'):
            # This is a sitemap index - extract sub-sitemap URLs
            sub_sitemaps = root.xpath('//sm:sitemap/sm:loc/text()', namespaces=SITEMAP_NS)
            if not sub_sitemaps:
                # Try without namespace
                sub_sitemaps = root.xpath('//sitemap/loc/text()')

            logger.debug(f"Found sitemap index with {len(sub_sitemaps)} sub-sitemaps")

            # Parse each sub-sitemap (limit to max_sitemaps)
            tasks = []
            for sub_url in sub_sitemaps[:self.max_sitemaps]:
                if len(urls) >= self.max_urls:
                    break
                tasks.append(self._parse_sitemap(str(sub_url).strip(), base_host))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, set):
                        urls.update(result)
                        if len(urls) >= self.max_urls:
                            break

        else:
            # This is a regular sitemap - extract URLs
            url_locs = root.xpath('//sm:url/sm:loc/text()', namespaces=SITEMAP_NS)
            if not url_locs:
                # Try without namespace
                url_locs = root.xpath('//url/loc/text()')

            for url in url_locs:
                url = str(url).strip()
                if not url:
                    continue

                # Filter by host if enabled
                if self.same_host_only:
                    url_host = urlparse(url).netloc
                    if url_host != base_host:
                        continue

                urls.add(url)

                if len(urls) >= self.max_urls:
                    break

            logger.debug(f"Extracted {len(urls)} URLs from {sitemap_url}")

        return urls

    async def has_sitemap(self, base_url: str) -> bool:
        """Quick check if a sitemap exists.

        Args:
            base_url: Base URL to check.

        Returns:
            True if sitemap exists.
        """
        parsed = urlparse(base_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        sitemap_urls = await self._find_sitemap_urls(base_domain)

        for sitemap_url in sitemap_urls[:3]:  # Check first 3 locations
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(
                        sitemap_url,
                        timeout=aiohttp.ClientTimeout(total=2.0),
                        headers={'User-Agent': 'Mozilla/5.0 (compatible; SitemapParser/1.0)'},
                        allow_redirects=True
                    ) as response:
                        if response.status == 200:
                            content_type = response.headers.get('Content-Type', '')
                            if 'xml' in content_type or sitemap_url.endswith('.xml'):
                                return True
            except Exception:
                continue

        return False
