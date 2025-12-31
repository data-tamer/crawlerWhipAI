"""Hierarchical link mapping for deep crawling."""

import logging
import asyncio
from typing import Optional, Set, Dict
from datetime import datetime

from ..models import LinkNode
from ..core import AsyncWebCrawler, CrawlerConfig
from ..utils import normalize_url, get_base_domain, is_internal_url, get_full_host, is_same_host

logger = logging.getLogger(__name__)


class LinkMapper:
    """Maps links hierarchically using BFS crawling."""

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 100,
        include_external: bool = False,
        same_host_only: bool = False,
        use_crawler: Optional[AsyncWebCrawler] = None,
        max_concurrent: int = 5,
    ):
        """Initialize LinkMapper.

        Args:
            max_depth: Maximum crawl depth.
            max_pages: Maximum pages to crawl.
            include_external: Whether to include external links (different root domains).
            same_host_only: If True, only crawl URLs with exact same hostname.
                           This is stricter than include_external=False, which allows
                           subdomains (e.g., docs.example.com and blog.example.com).
                           When same_host_only=True, only the exact host is crawled.
            use_crawler: Optional AsyncWebCrawler to use (will create one if not provided).
            max_concurrent: Maximum concurrent requests per depth level.
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.include_external = include_external
        self.same_host_only = same_host_only
        self.crawler = use_crawler
        self.max_concurrent = max_concurrent
        self.pages_crawled = 0

    async def map_links(
        self,
        start_url: str,
        crawler_config: Optional[CrawlerConfig] = None,
    ) -> LinkNode:
        """Map links starting from a URL using BFS.

        Args:
            start_url: Starting URL for link mapping.
            crawler_config: Optional crawler configuration.

        Returns:
            Root LinkNode with hierarchical structure.
        """
        logger.info(f"Starting link mapping from {start_url} (max_depth={self.max_depth}, max_pages={self.max_pages}, same_host_only={self.same_host_only})")

        # Initialize crawler if not provided
        if not self.crawler:
            self.crawler = AsyncWebCrawler()
            await self.crawler.start()

        config = crawler_config or CrawlerConfig()
        base_domain = get_base_domain(start_url)

        # Store config and start_url for use in child methods
        self.config = config
        self.start_url = start_url
        self.start_host = get_full_host(start_url)

        # Initialize root node
        root = LinkNode(
            url=start_url,
            depth=0,
            parent_url=None,
            is_internal=True,
        )

        # BFS traversal with concurrent crawling per depth level
        # Preserve fragments if configured (for PWA support)
        visited: Set[str] = {normalize_url(start_url, preserve_fragment=config.preserve_url_fragment)}
        current_depth_nodes = [root]
        self.pages_crawled = 0

        for current_depth in range(self.max_depth + 1):
            if not current_depth_nodes or self.pages_crawled >= self.max_pages:
                break

            logger.info(f"Processing depth {current_depth} with {len(current_depth_nodes)} nodes")

            # Crawl all nodes at current depth concurrently
            await self._crawl_depth_level(
                current_depth_nodes, config, visited, base_domain, current_depth
            )

            # Collect all child nodes for next depth level
            next_depth_nodes = []
            for node in current_depth_nodes:
                next_depth_nodes.extend(node.children)

            current_depth_nodes = next_depth_nodes

        logger.info(
            f"Link mapping complete: {self.pages_crawled} pages crawled, "
            f"{root.count_nodes()} total nodes"
        )
        return root

    async def _crawl_depth_level(
        self,
        nodes: list,
        config: CrawlerConfig,
        visited: Set[str],
        base_domain: str,
        current_depth: int,
    ) -> None:
        """Crawl all nodes at a specific depth level concurrently.

        Args:
            nodes: List of LinkNode objects to crawl.
            config: Crawler configuration.
            visited: Set of already visited URLs.
            base_domain: Base domain for internal link detection.
            current_depth: Current depth level.
        """
        # Create crawl tasks with semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def crawl_with_sem(node: LinkNode):
            async with semaphore:
                if self.pages_crawled >= self.max_pages:
                    return

                logger.info(f"[Depth {current_depth}] Crawling {node.url}")
                result = await self.crawler.arun(node.url, config)

                # Update node with crawl result
                node.status_code = result.status_code
                node.crawled_at = result.crawled_at.isoformat() if result.crawled_at else None

                if not result.success:
                    node.error = result.error
                    self.pages_crawled += 1
                    return

                # Extract metadata
                node.title = result.title or ""
                node.description = result.description or ""
                node.meta_tags = result.meta_tags.copy() if result.meta_tags else {}

                self.pages_crawled += 1

                # Discover links for next depth
                if current_depth < self.max_depth and self.pages_crawled < self.max_pages:
                    await self._discover_child_links(
                        node, result, visited, base_domain, current_depth
                    )

        # Execute all crawls concurrently
        await asyncio.gather(*[crawl_with_sem(node) for node in nodes], return_exceptions=True)

    async def _discover_child_links(
        self,
        parent_node: LinkNode,
        result,
        visited: Set[str],
        base_domain: str,
        current_depth: int,
    ) -> None:
        """Discover and create child link nodes.

        Args:
            parent_node: Parent LinkNode.
            result: Crawl result containing links.
            visited: Set of visited URLs.
            base_domain: Base domain for internal link detection.
            current_depth: Current depth level.
        """
        next_depth = current_depth + 1
        internal_links = result.links.get("internal", [])
        external_links = result.links.get("external", [])

        links_to_process = internal_links
        if self.include_external:
            links_to_process.extend(external_links)

        for link_data in links_to_process:
            link_url = link_data.get("href", "")
            if not link_url:
                continue

            # Preserve fragments if configured (for PWA support)
            normalized_url = normalize_url(link_url, preserve_fragment=self.config.preserve_url_fragment)

            # Skip if already visited
            if normalized_url in visited:
                continue

            # Check capacity
            if len(visited) >= self.max_pages:
                break

            # Check same_host_only filter - skip URLs from different hosts
            if self.same_host_only:
                url_host = get_full_host(normalized_url)
                if url_host != self.start_host:
                    logger.debug(f"Skipping different host: {normalized_url} (host {url_host} != {self.start_host})")
                    continue

            # Create child node
            child_node = LinkNode(
                url=normalized_url,
                depth=next_depth,
                parent_url=parent_node.url,
                is_internal=is_internal_url(normalized_url, base_domain),
            )

            parent_node.children.append(child_node)
            visited.add(normalized_url)

            logger.debug(
                f"Discovered link: {normalized_url} (depth={next_depth}, "
                f"internal={child_node.is_internal})"
            )

    def get_all_urls(self, root: LinkNode, max_depth: Optional[int] = None) -> list:
        """Get all discovered URLs from root node.

        Args:
            root: Root LinkNode.
            max_depth: Optional maximum depth to retrieve.

        Returns:
            List of all URLs.
        """
        return root.get_all_urls(max_depth)

    def get_urls_by_depth(self, root: LinkNode) -> Dict[int, list]:
        """Organize URLs by depth level.

        Args:
            root: Root LinkNode.

        Returns:
            Dictionary mapping depth to list of URLs.
        """
        result = {}

        def traverse(node: LinkNode):
            if node.depth not in result:
                result[node.depth] = []
            result[node.depth].append(node.url)

            for child in node.children:
                traverse(child)

        traverse(root)
        return result

    async def close(self) -> None:
        """Close the crawler if it was created by this mapper."""
        if self.crawler:
            await self.crawler.close()

    async def __aenter__(self):
        """Async context manager entry."""
        if not self.crawler:
            self.crawler = AsyncWebCrawler()
            await self.crawler.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
