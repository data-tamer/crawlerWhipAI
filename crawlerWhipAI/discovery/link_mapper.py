"""Hierarchical link mapping for deep crawling."""

import logging
import asyncio
from typing import Optional, Set, Dict
from datetime import datetime

from ..models import LinkNode
from ..core import AsyncWebCrawler, CrawlerConfig
from ..utils import normalize_url, get_base_domain, is_internal_url

logger = logging.getLogger(__name__)


class LinkMapper:
    """Maps links hierarchically using BFS crawling."""

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 100,
        include_external: bool = False,
        use_crawler: Optional[AsyncWebCrawler] = None,
    ):
        """Initialize LinkMapper.

        Args:
            max_depth: Maximum crawl depth.
            max_pages: Maximum pages to crawl.
            include_external: Whether to include external links.
            use_crawler: Optional AsyncWebCrawler to use (will create one if not provided).
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.include_external = include_external
        self.crawler = use_crawler
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
        logger.info(f"Starting link mapping from {start_url} (max_depth={self.max_depth}, max_pages={self.max_pages})")

        # Initialize crawler if not provided
        if not self.crawler:
            self.crawler = AsyncWebCrawler()
            await self.crawler.start()

        config = crawler_config or CrawlerConfig()
        base_domain = get_base_domain(start_url)

        # Initialize root node
        root = LinkNode(
            url=start_url,
            depth=0,
            parent_url=None,
            is_internal=True,
        )

        # BFS traversal
        visited: Set[str] = {normalize_url(start_url)}
        queue: list = [(root, 0)]
        self.pages_crawled = 0

        while queue and self.pages_crawled < self.max_pages:
            current_node, current_depth = queue.pop(0)

            # Check depth limit
            if current_depth > self.max_depth:
                logger.debug(f"Skipping {current_node.url} (exceeds max_depth)")
                continue

            # Crawl current page
            logger.info(f"[Depth {current_depth}] Crawling {current_node.url}")
            result = await self.crawler.arun(current_node.url, config)

            # Update node with crawl result
            current_node.status_code = result.status_code
            current_node.crawled_at = result.crawled_at.isoformat() if result.crawled_at else None
            if not result.success:
                current_node.error = result.error
                self.pages_crawled += 1
                continue

            # Extract metadata
            current_node.title = result.title or ""
            current_node.description = result.description or ""
            current_node.meta_tags = result.meta_tags.copy() if result.meta_tags else {}

            self.pages_crawled += 1

            # Discover links from current page
            if current_depth < self.max_depth and self.pages_crawled < self.max_pages:
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

                    normalized_url = normalize_url(link_url)

                    # Skip if already visited
                    if normalized_url in visited:
                        continue

                    # Check capacity
                    if self.pages_crawled >= self.max_pages:
                        break

                    # Create child node
                    child_node = LinkNode(
                        url=normalized_url,
                        depth=next_depth,
                        parent_url=current_node.url,
                        is_internal=is_internal_url(normalized_url, base_domain),
                    )

                    current_node.children.append(child_node)
                    visited.add(normalized_url)
                    queue.append((child_node, next_depth))

                    logger.debug(
                        f"Discovered link: {normalized_url} (depth={next_depth}, "
                        f"internal={child_node.is_internal})"
                    )

        logger.info(
            f"Link mapping complete: {self.pages_crawled} pages crawled, "
            f"{root.count_nodes()} total nodes"
        )
        return root

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
